"""Training offline del prior v1 (§7). Non entra nel ciclo notturno."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from neuraec.encoder import Encoder
from neuraec.estimators import rules_urgency
from neuraec.ordinal import u_star
from neuraec.prior_net import H1, H2, IN_DIM, PriorNet, pack_features

TRAIN_SOURCES = {"corr", "manual"}
MIN_DISK_ROWS = 50
MAX_EPOCHS = 50
PATIENCE = 5
ADAM_LR = 1e-3


@dataclass
class PriorSample:
    user_id: str
    features: np.ndarray
    u: float
    s: np.ndarray
    r: np.ndarray
    sim: np.ndarray


def holdout_user_ids(user_ids: list[str], k: int = 3) -> list[str]:
    """k utenti interi, posizioni fisse sulla lista ordinata. Mai una riga sola."""
    ids = sorted(set(user_ids))
    if len(ids) <= k:
        raise ValueError(f"servono almeno {k + 1} utenti per lo split, trovati {len(ids)}")
    chosen: list[str] = []
    for i in range(1, k + 1):
        idx = min(i * len(ids) // (k + 1), len(ids) - 1)
        if ids[idx] not in chosen:
            chosen.append(ids[idx])
    for uid in ids:
        if len(chosen) >= k:
            break
        if uid not in chosen:
            chosen.append(uid)
    return chosen[:k]


def user_state_dirs(data_root: Path) -> list[Path]:
    if not data_root.exists():
        return []
    base = data_root / "users" if (data_root / "users").is_dir() else data_root
    found = []
    for path in sorted(base.iterdir()):
        if path.is_dir() and (path / "state.json").exists() and (path / "memory.jsonl").exists():
            found.append(path)
    return found


def collect_disk(data_root: Path, encoder: Encoder) -> list[PriorSample]:
    from neuraec.features import ProfilePrototypes

    samples: list[PriorSample] = []
    for folder in user_state_dirs(data_root):
        meta = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        n_ranks = int(meta["N"])
        user_id = str(meta.get("user_id") or folder.name)
        profile = meta.get("profile") or {"fig": [], "fun": [], "set": []}
        vectors = np.load(folder / "memory.npy")
        items = []
        for line in (folder / "memory.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                items.append(json.loads(line))
        n = min(len(items), len(vectors))
        protos = ProfilePrototypes(encoder, profile)
        for item, e in zip(items[:n], vectors[:n]):
            if item.get("source") not in TRAIN_SOURCES:
                continue
            s = np.asarray(item.get("s") or [], dtype=np.float64)
            r = np.asarray(item.get("r") or [], dtype=np.float64)
            if s.shape[0] != 11 or r.shape[0] != 3:
                continue
            sim = np.asarray(protos.sim(e), dtype=np.float64)
            samples.append(
                PriorSample(
                    user_id=user_id,
                    features=pack_features(e, s, r, sim),
                    u=u_star(int(item["rank"]), n_ranks),
                    s=s,
                    r=r,
                    sim=sim,
                )
            )
    return samples


def collect_csv(encoder: Encoder, csv_path: Path) -> list[PriorSample]:
    from neuraec.bench.prequential import load_csv, row_to_record
    from neuraec.bench.synthetic import mailbox
    from neuraec.features import ProfilePrototypes, relazione, struttura

    by_user: dict[str, list[dict]] = defaultdict(list)
    for row in load_csv(csv_path):
        by_user[str(row["userId"])].append(row)
    samples: list[PriorSample] = []
    for user_id, urows in by_user.items():
        urows.sort(key=lambda r: float(r.get("date_received") or 0))
        _rec0, _rank0, n_ranks, order, user_email = row_to_record(urows[0])
        mb = mailbox(user_id, N=n_ranks, order=order)
        if user_email:
            mb.own_addresses = [user_email]
        protos = ProfilePrototypes(encoder, {"fig": [], "fun": [], "set": []})
        parsed = [row_to_record(row) for row in urows]
        embs = encoder.encode_many([rec.encoder_text() for rec, *_rest in parsed])
        for (rec, rank, n_row, _order, _email), e in zip(parsed, embs):
            s = np.asarray(struttura(rec, mb), dtype=np.float64)
            r = np.asarray(relazione(rec, mb, {}), dtype=np.float64)
            sim = np.asarray(protos.sim(e), dtype=np.float64)
            samples.append(
                PriorSample(
                    user_id=user_id,
                    features=pack_features(e, s, r, sim),
                    u=u_star(rank, n_row),
                    s=s,
                    r=r,
                    sim=sim,
                )
            )
    return samples


def choose_samples(
    data_root: Path | None,
    encoder: Encoder,
    csv_path: Path,
    *,
    min_disk: int = MIN_DISK_ROWS,
) -> tuple[list[PriorSample], str]:
    disk = collect_disk(data_root, encoder) if data_root is not None else []
    if len(disk) >= min_disk:
        return disk, "disk"
    return collect_csv(encoder, csv_path), "csv"


def mae_rules(samples: list[PriorSample]) -> float:
    if not samples:
        return float("nan")
    err = [abs(rules_urgency(s.s, s.r, s.sim) - s.u) for s in samples]
    return float(np.mean(err))


def mae_net(net: PriorNet, samples: list[PriorSample]) -> float:
    if not samples:
        return float("nan")
    err = []
    for sample in samples:
        e = sample.features[: IN_DIM - 11 - 3 - 3]
        err.append(abs(net.urgency(e, sample.s, sample.r, sample.sim) - sample.u))
    return float(np.mean(err))


def cascade_not_worse(base: dict, cand: dict) -> tuple[bool, list[dict]]:
    rows = []
    ok = True
    for uid, info in base["per_user"].items():
        other = cand["per_user"].get(uid)
        if other is None:
            ok = False
            rows.append({"user": uid, "v0": info["accuracy"], "v1": None, "delta": None, "n": info["n"]})
            continue
        delta = float(other["accuracy"]) - float(info["accuracy"])
        if float(other["accuracy"]) + 1e-12 < float(info["accuracy"]):
            ok = False
        rows.append(
            {
                "user": uid,
                "v0": float(info["accuracy"]),
                "v1": float(other["accuracy"]),
                "delta": delta,
                "n": int(info["n"]),
            }
        )
    return ok, rows


def accepts(mae_v1: float, mae_v0: float, base: dict, cand: dict) -> bool:
    if not (mae_v1 < mae_v0):
        return False
    ok, _rows = cascade_not_worse(base, cand)
    return ok


def _net_from_sequential(model) -> PriorNet:
    import torch.nn as nn

    linears = [layer for layer in model if isinstance(layer, nn.Linear)]
    if len(linears) != 3:
        raise ValueError("la rete deve avere 3 Linear")
    W1 = linears[0].weight.detach().cpu().numpy().T
    b1 = linears[0].bias.detach().cpu().numpy()
    W2 = linears[1].weight.detach().cpu().numpy().T
    b2 = linears[1].bias.detach().cpu().numpy()
    W3 = linears[2].weight.detach().cpu().numpy().T
    b3 = linears[2].bias.detach().cpu().numpy()
    return PriorNet(W1, b1, W2, b2, W3, b3, accepted=False)


def train_mlp(
    samples: list[PriorSample],
    holdout: list[str],
    *,
    max_epochs: int = MAX_EPOCHS,
    patience: int = PATIENCE,
    lr: float = ADAM_LR,
    seed: int = 0,
) -> tuple[PriorNet, dict]:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    held = set(holdout)
    train = [s for s in samples if s.user_id not in held]
    val = [s for s in samples if s.user_id in held]
    if not train or not val:
        raise ValueError("split di training o validazione vuoto")
    counts: dict[str, int] = defaultdict(int)
    for sample in train:
        counts[sample.user_id] += 1
    x = torch.tensor(np.stack([s.features for s in train]), dtype=torch.float32)
    y = torch.tensor([s.u for s in train], dtype=torch.float32)
    w = torch.tensor([1.0 / math.sqrt(counts[s.user_id]) for s in train], dtype=torch.float32)
    xv = torch.tensor(np.stack([s.features for s in val]), dtype=torch.float32)
    yv = torch.tensor([s.u for s in val], dtype=torch.float32)

    model = nn.Sequential(
        nn.Linear(IN_DIM, H1),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(H1, H2),
        nn.ReLU(),
        nn.Linear(H2, 1),
        nn.Sigmoid(),
    )
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    best_state = None
    best_mae = math.inf
    wait = 0
    history: list[dict] = []
    for epoch in range(1, max_epochs + 1):
        model.train()
        opt.zero_grad()
        pred = model(x).squeeze(-1)
        loss = ((pred - y) ** 2 * w).sum() / w.sum()
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            pv = model(xv).squeeze(-1)
            mae = float(torch.mean(torch.abs(pv - yv)))
        history.append({"epoch": epoch, "loss": float(loss.detach()), "val_mae": mae})
        if mae < best_mae - 1e-6:
            best_mae = mae
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break
    if best_state is None:
        raise RuntimeError("nessuna epoca di training")
    model.load_state_dict(best_state)
    return _net_from_sequential(model), {
        "best_val_mae": best_mae,
        "epochs": len(history),
        "history": history,
    }


def run_prior_train(
    encoder: Encoder,
    *,
    data_root: Path | None,
    csv_path: Path,
    out: Path,
    max_epochs: int = MAX_EPOCHS,
) -> dict:
    from neuraec.bench.prequential import run_prequential

    samples, source = choose_samples(data_root, encoder, csv_path)
    holdout = holdout_user_ids([s.user_id for s in samples])
    net, train_info = train_mlp(samples, holdout, max_epochs=max_epochs)
    val = [s for s in samples if s.user_id in set(holdout)]
    mae_v0 = mae_rules(val)
    mae_v1 = mae_net(net, val)
    net.accepted = True
    import tempfile

    base = run_prequential(
        encoder=encoder,
        csv_path=csv_path,
        workdir=Path(tempfile.mkdtemp(prefix="neura-prior-v0-")),
        prior_net=None,
    )
    cand = run_prequential(
        encoder=encoder,
        csv_path=csv_path,
        workdir=Path(tempfile.mkdtemp(prefix="neura-prior-v1-")),
        prior_net=net,
    )
    cascade_ok, per_user = cascade_not_worse(base, cand)
    mae_ok = mae_v1 < mae_v0
    net.accepted = bool(mae_ok and cascade_ok)
    net.mae_v0 = mae_v0
    net.mae_v1 = mae_v1
    net.save(out)
    report = {
        "source": source,
        "encoder": encoder.name,
        "n": len(samples),
        "n_users": len({s.user_id for s in samples}),
        "holdout": holdout,
        "epochs": train_info["epochs"],
        "mae_v0": mae_v0,
        "mae_v1": mae_v1,
        "mae_ok": mae_ok,
        "cascade_ok": cascade_ok,
        "accepted": net.accepted,
        "accuracy_v0": base["accuracy"],
        "accuracy_v1": cand["accuracy"],
        "per_user": per_user,
        "note": "I ranghi del CSV sono in gran parte del modello vecchio; il prior li usa solo come target offline.",
    }
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def format_train_report(report: dict) -> str:
    lines = [
        f"fonte: {report['source']}  encoder: {report['encoder']}  n={report['n']}  utenti={report['n_users']}",
        f"validazione (utenti interi): {', '.join(report['holdout'])}",
        f"MAE u  v0={report['mae_v0']:.4f}  v1={report['mae_v1']:.4f}  migliore={'v1' if report['mae_ok'] else 'v0'}",
        f"cascata  v0={report['accuracy_v0']:.3f}  v1={report['accuracy_v1']:.3f}  "
        f"no user worse={'yes' if report['cascade_ok'] else 'no'}",
        f"accepted={report['accepted']}",
        "per user (cascade accuracy):",
    ]
    for row in sorted(report["per_user"], key=lambda r: -(r["n"] or 0)):
        v1 = "—" if row["v1"] is None else f"{row['v1']:.3f}"
        delta = "—" if row["delta"] is None else f"{row['delta']:+.3f}"
        lines.append(f"  user {row['user']:4} n={row['n']:4d}  v0={row['v0']:.3f}  v1={v1}  Δ={delta}")
    if report["source"] == "csv":
        lines.append(report["note"])
    if not report["accepted"]:
        lines.append("criterion not met: the classifier stays on v0")
    return "\n".join(lines)
