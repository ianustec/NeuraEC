from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from neuraec.bench.synthetic import mailbox
from neuraec.classifier import Classifier
from neuraec.encoder import Encoder, FakeEncoder
from neuraec.learn import observe
from neuraec.ordinal import label_to_rank
from neuraec.records import EmailRecord, LabelMap
from neuraec.registry import Registry
from neuraec.state import UserState

_ADDR = re.compile(r"[\w.+-]+@[\w.-]+")
_ANGLE = re.compile(r"<([^>]+)>")

DEFAULT_CSV = (
    Path(__file__).resolve().parents[3]
    / "tools"
    / "bec_braind_static_training"
    / "training_dataset"
    / "training_dataset.csv"
)


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    v = str(value).strip()
    if v.lower() in {"none", "nan", ""}:
        return ""
    return v


def _addrs(value: str | None) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    return [a.lower() for a in _ADDR.findall(text)]


def _from_addr(value: str | None) -> str:
    text = _clean(value)
    if not text:
        return ""
    m = _ANGLE.search(text)
    if m:
        return m.group(1).lower()
    found = _ADDR.findall(text)
    return found[0].lower() if found else text.lower()


def _ts(value: str | None) -> datetime:
    raw = _clean(value) or "0"
    try:
        n = int(float(raw))
    except ValueError:
        n = 0
    if n > 10_000_000_000:
        n = n // 1000
    return datetime.fromtimestamp(n, tz=timezone.utc)


def _order(labels_order: str) -> str:
    return "desc" if str(labels_order).strip() in {"-1", "-1.0"} else "asc"


def load_csv(path: Path | None = None) -> list[dict]:
    path = path or DEFAULT_CSV
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader)


def row_to_record(row: dict) -> tuple[EmailRecord, int, int, str, str]:
    user_id = str(row["userId"])
    user_email = _from_addr(row.get("user_email")) or _clean(row.get("user_email")).lower()
    N = int(float(row["labels_number"]))
    order = _order(row.get("labels_order", "1"))
    label = int(float(row["IdServiceLabel"]))
    rank = label_to_rank(label, N, order)
    rec = EmailRecord(
        uid=f"{user_id}-{_clean(row.get('id')) or row.get('message_id') or label}",
        message_id=_clean(row.get("message_id")),
        in_reply_to=_clean(row.get("in_reply_to")) or None,
        received_at=_ts(row.get("date_received")),
        from_addr=_from_addr(row.get("from")),
        to_addrs=_addrs(row.get("to")),
        cc_addrs=_addrs(row.get("cc")),
        subject=_clean(row.get("subject")),
        snippet=_clean(row.get("snippet")),
        has_attachment=str(row.get("attachment", "0")).strip() in {"1", "True", "true"},
    )
    return rec, rank, N, order, user_email


def run_prequential(
    encoder: Encoder | None = None,
    csv_path: Path | None = None,
    workdir: Path | None = None,
    persist: bool = False,
    prior_net=None,
) -> dict:
    encoder = encoder or FakeEncoder()
    rows = load_csv(csv_path)
    by_user: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_user[str(row["userId"])].append(row)
    for uid in by_user:
        by_user[uid].sort(key=lambda r: float(r.get("date_received") or 0))

    per_user = {}
    hits = 0
    total = 0
    stages: Counter[str] = Counter()
    workdir = workdir or Path("/tmp/neura-preq")
    workdir.mkdir(parents=True, exist_ok=True)

    for user_id, urows in by_user.items():
        rec0, _rank0, N, order, user_email = row_to_record(urows[0])
        mb = mailbox(user_id, N=N, order=order)
        mb.own_addresses = [user_email] if user_email else mb.own_addresses
        mb.labels = [LabelMap(rank=r, provider_label=f"P{r}", text=f"P{r}") for r in range(N)]
        state = UserState(
            workdir / user_id,
            user_id=user_id,
            N=N,
            order=order,
            encoder_name=encoder.name,
        )
        registry = Registry(workdir / user_id / "pred.sqlite")
        clf = Classifier(mb, state, encoder, registry, prior_net=prior_net)
        seen_mid: dict[str, int] = {}
        uhits = 0
        un = 0
        maj: Counter[int] = Counter()
        for i, row in enumerate(urows):
            rec, rank, _N, _order, _email = row_to_record(row)
            if rec.in_reply_to and rec.in_reply_to in seen_mid:
                rec.thread_id = rec.in_reply_to
            if i > 0:
                pred = clf.predict(rec, write_registry=True, now=rec.received_at)
                un += 1
                total += 1
                stages[pred.stage] += 1
                if pred.rank == rank:
                    uhits += 1
                    hits += 1
            observe(clf, rec, rank=rank, source="corr", now=rec.received_at, persist=persist)
            if rec.message_id:
                seen_mid[rec.message_id] = rank
            maj[rank] += 1
        if persist:
            state.save()
        majority = maj.most_common(1)[0][1] / len(urows) if urows else 0.0
        acc = uhits / un if un else 0.0
        per_user[user_id] = {
            "n": un,
            "accuracy": acc,
            "majority": majority,
            "delta_vs_majority": acc - majority,
        }

    return {
        "accuracy": hits / total if total else 0.0,
        "n": total,
        "stages": dict(stages),
        "per_user": per_user,
        "encoder": encoder.name,
    }


def format_report(result: dict) -> str:
    lines = [
        f"encoder: {result['encoder']}",
        f"accuracy aggregata: {result['accuracy']:.3f}  (n={result['n']})",
        "stage 1 target: ≥ 0.82 aggregate, no user more than 2 points below their own majority",
        f"stage: {result['stages']}",
        "per user:",
    ]
    for uid, info in sorted(result["per_user"].items(), key=lambda kv: -kv[1]["n"]):
        lines.append(
            f"  user {uid:4s} n={info['n']:4d}  acc={info['accuracy']:.2f}  "
            f"maj={info['majority']:.2f}  Δ={info['delta_vs_majority']:+.2f}"
        )
    return "\n".join(lines)
