from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from neuraec.adapters.base import Adapter
from neuraec.classifier import Classifier
from neuraec.constants import OBSERVE_DELAY_HOURS, SENT_LOOKBACK_DAYS
from neuraec.learn import observe
from neuraec.records import EmailRecord, MailboxConfig, NightlyReport, Prediction, folders_match, utcnow
from neuraec.registry import Registry
from neuraec.state import UserState

LABELED_ACTIONS = {"moved", "read_unmoved", "replied", "manual"}


def median_rank(mass: np.ndarray) -> int | None:
    total = float(np.asarray(mass, dtype=np.float64).sum())
    if total <= 0:
        return None
    acc = 0.0
    half = total / 2.0
    for rank, value in enumerate(mass):
        acc += float(value)
        if acc >= half:
            return int(rank)
    return int(len(mass) - 1)


def ingest_sent(state: UserState, mailbox: MailboxConfig, records: list[EmailRecord]) -> int:
    """Increment replied_to with recipients of Sent mail. Skips the mailbox's own addresses."""
    own = mailbox.own_set
    n = 0
    for rec in records:
        for addr in rec.to_addrs + rec.cc_addrs:
            if not addr or addr in own:
                continue
            state.bump_replied(addr)
            n += 1
    return n


def compute_stats(registry: Registry) -> dict[str, Any]:
    rows = registry.rows()
    n_open = sum(1 for r in rows if r.get("status") == "open")
    n_corr = sum(1 for r in rows if _rank_changed(r))
    n_conf = sum(1 for r in rows if r.get("user_action") == "read_unmoved")
    n_replied = sum(1 for r in rows if r.get("user_action") == "replied")
    n_manual = sum(1 for r in rows if r.get("user_action") == "manual")
    n_deleted = sum(1 for r in rows if r.get("user_action") == "deleted")
    n_expired = sum(1 for r in rows if r.get("status") == "expired")
    labeled = [r for r in rows if r.get("user_action") in LABELED_ACTIONS]
    n_labeled = len(labeled)
    corr_per_100 = (100.0 * n_corr / n_labeled) if n_labeled else 0.0
    ranked = [
        r
        for r in labeled
        if r.get("pred_rank") is not None and r.get("final_rank") is not None
    ]
    if ranked:
        hits = [int(r["pred_rank"]) == int(r["final_rank"]) for r in ranked]
        maes = [abs(int(r["pred_rank"]) - int(r["final_rank"])) for r in ranked]
        accuracy = float(np.mean(hits))
        mae = float(np.mean(maes))
    else:
        accuracy = 0.0
        mae = 0.0
    open_rows = [r for r in rows if r.get("status") == "open"]
    stages = {name: 0 for name in ("thread", "sender", "domain", "memory", "prior")}
    ranks: dict[int, int] = {}
    for row in open_rows:
        stage = str(row.get("stage") or "")
        if stage in stages:
            stages[stage] += 1
        if row.get("pred_rank") is not None:
            rank = int(row["pred_rank"])
            ranks[rank] = ranks.get(rank, 0) + 1
    recent = sorted(open_rows, key=lambda row: str(row.get("written_at") or ""), reverse=True)[:6]
    return {
        "n_total": len(rows),
        "n_open": n_open,
        "n_corr": n_corr,
        "n_conf": n_conf,
        "n_replied": n_replied,
        "n_manual": n_manual,
        "n_deleted": n_deleted,
        "n_expired": n_expired,
        "n_labeled": n_labeled,
        "corrections_per_100": round(corr_per_100, 2),
        "accuracy": round(accuracy, 4),
        "mae": round(mae, 4),
        "stages": stages,
        "ranks": ranks,
        "recent": [
            {
                "from_addr": row.get("from_addr") or "",
                "pred_rank": row.get("pred_rank"),
                "stage": row.get("stage") or "",
                "pred_conf": row.get("pred_conf") or 0,
                "written_label": row.get("written_label") or "",
            }
            for row in recent
        ],
    }


def predict_unseen(
    mailbox: MailboxConfig,
    adapter: Adapter,
    clf: Classifier,
    *,
    now: datetime | None = None,
) -> list[tuple[EmailRecord, Prediction]]:
    """fetch_unseen → predict (open row) → write_label. User state is not observed."""
    with clf.state.lock():
        return _predict_unseen_locked(mailbox, adapter, clf, now=now)


def _predict_unseen_locked(
    mailbox: MailboxConfig,
    adapter: Adapter,
    clf: Classifier,
    *,
    now: datetime | None = None,
) -> list[tuple[EmailRecord, Prediction]]:
    from neuraec.constants import CYCLE_MAIL_LIMIT

    now = now or utcnow()
    out: list[tuple[EmailRecord, Prediction]] = []
    known = clf.registry.uids() if clf.registry is not None else set()
    for rec in adapter.fetch_unseen(limit=CYCLE_MAIL_LIMIT, skip_uids=known):
        # Already classified: with labels it stays in the inbox, so it must not be predicted or notified again.
        if clf.registry is not None and clf.registry.get(rec.uid) is not None:
            continue
        if mailbox.is_priority_folder(rec.folder or ""):
            continue
        pred = clf.predict(rec, now=now)
        if clf.registry is not None:
            row = clf.registry.get(rec.uid)
            if row is not None and row.get("status") == "frozen":
                continue
        label = mailbox.label_for_rank(pred.rank)
        adapter.write_label(rec.uid, label)
        rec.folder = label
        out.append((rec, pred))
        if len(out) >= CYCLE_MAIL_LIMIT:
            break
    return out


NOTIFY_SNIPPET = 160


def notify_dir(data_root: Path | str) -> Path:
    """Queue read by the front end. It sits next to `data`, that is ~/.neura/notify."""
    return Path(data_root).parent / "notify"


def _one_line(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def write_notify_queue(
    mailbox: MailboxConfig,
    labeled: list[tuple[EmailRecord, Prediction]],
    data_root: Path | str,
    *,
    now: datetime | None = None,
) -> Path | None:
    """One file per pass, only when at least one mail was just labelled.

    Write to a temporary file then rename: a reader never sees a half-written file.
    """
    if not labeled:
        return None
    now = now or utcnow()
    folder = notify_dir(data_root)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    account = mailbox.username or (mailbox.own_addresses[0] if mailbox.own_addresses else mailbox.mailbox_id)
    payload = {
        "mailbox_id": mailbox.mailbox_id,
        "account": account,
        "at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": [
            {
                "rank": int(pred.rank),
                "label": mailbox.label_for_rank(pred.rank),
                "from_addr": rec.from_addr,
                "subject": _one_line(rec.subject, 200),
                "snippet": _one_line(rec.snippet, NOTIFY_SNIPPET),
            }
            for rec, pred in labeled
        ],
    }
    dest = folder / f"{stamp}-{mailbox.mailbox_id}.json"
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(dest)
    return dest


def init_mailbox(
    mailbox: MailboxConfig,
    adapter: Adapter,
    clf: Classifier,
    *,
    now: datetime | None = None,
    progress=None,
) -> dict[str, int]:
    now = now or utcnow()

    def say(message: str) -> None:
        if progress is not None:
            progress(message)

    say("creating priority folders")
    adapter.ensure_labels(mailbox.labels)
    say(f"reading recipients of sent mail from the last {SENT_LOOKBACK_DAYS} days")
    sent = adapter.fetch_sent(now - timedelta(days=SENT_LOOKBACK_DAYS))
    n = ingest_sent(clf.state, mailbox, sent)
    clf.state.initialized_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    clf.state.save()
    return {"n_sent": len(sent), "n_recipients": n, "n_replied_keys": len(clf.state.replied_to)}


def _rank_changed(row: dict[str, Any]) -> bool:
    """A correction is a move to a different priority. The same rank is not one.

    A folder rename, or two names for the same priority, used to be stored as
    user_action=moved with final_rank == pred_rank. That made corrections/100
    look like the model was always wrong while accuracy stayed near 1.
    """
    if row.get("user_action") != "moved":
        return False
    if row.get("pred_rank") is None or row.get("final_rank") is None:
        return False
    return int(row["pred_rank"]) != int(row["final_rank"])


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _apply_observation(
    clf: Classifier,
    row: dict[str, Any],
    rec: EmailRecord | None,
    mailbox: MailboxConfig,
    now: datetime,
) -> str:
    """Classify an open row according to table §8.2. Returns the category."""
    uid = row["uid"]
    pred_rank = int(row["pred_rank"])
    written = row.get("written_label") or ""

    if rec is None:
        if clf.registry is not None:
            clf.registry.resolve(uid, user_action="deleted", final_rank=None, status="resolved", now=now)
        return "deleted"

    folder = rec.folder or ""
    folder_rank = mailbox.rank_for_label(folder)
    same_folder = folders_match(folder, written)

    if folder_rank is not None and not same_folder:
        if int(folder_rank) == pred_rank:
            if clf.registry is not None:
                clf.registry.note_written_label(uid, folder)
            return "unread"
        observe(clf, rec, int(folder_rank), "corr", now=now)
        return "corr"

    if folder_rank is None:
        if clf.registry is not None:
            clf.registry.resolve(uid, user_action="deleted", final_rank=None, status="resolved", now=now)
        return "deleted"

    if rec.is_answered:
        if _observe_replied(clf, rec, pred_rank, now):
            return "replied"
        return "unread"

    if rec.is_seen:
        if observe(clf, rec, pred_rank, "conf", now=now):
            return "conf"
        return "unread"

    return "unread"


def _observe_replied(clf: Classifier, rec: EmailRecord, pred_rank: int, now: datetime) -> bool:
    """Reply: the predicted rank, but no less urgent than the user's median."""
    med = median_rank(clf.state.rank_mass.at(now))
    rank = pred_rank if med is None else min(pred_rank, med)
    return observe(clf, rec, int(rank), "replied", now=now)


def observe_moves(
    mailbox: MailboxConfig,
    adapter: Adapter,
    clf: Classifier,
    *,
    now: datetime | None = None,
) -> NightlyReport:
    """Fast path, every cycle: moves between priority folders and replies.

    Those are explicit signals and do not wait 24 hours. Mail that was read and
    left in place, deletions, and expiry stay on the nightly step (§8.2), where
    the wait exists so a row is not closed before the user has finished.
    """
    with clf.state.lock():
        return _observe_moves_locked(mailbox, adapter, clf, now=now)


def _observe_moves_locked(
    mailbox: MailboxConfig,
    adapter: Adapter,
    clf: Classifier,
    *,
    now: datetime | None = None,
) -> NightlyReport:
    from neuraec.adapters.base import label_names

    now = now or utcnow()
    report = NightlyReport()
    if clf.registry is None:
        report.kpi = {"error": "nessun registro"}
        return report
    rows = clf.registry.open_rows(now=now)
    if not rows:
        return report
    items = [(str(r["uid"]), r.get("message_id") or "", r.get("written_label") or "") for r in rows]
    try:
        found = adapter.probe(items, label_names(mailbox.labels))
    except Exception as exc:
        report.kpi = {"error": str(exc)}
        return report
    if found is None:
        report.kpi["skipped"] = "provider"
        return report
    for row in rows:
        rec = found.get(str(row["uid"]))
        if rec is None:
            continue
        folder = rec.folder or ""
        folder_rank = mailbox.rank_for_label(folder)
        if folder_rank is None:
            continue
        pred_rank = int(row["pred_rank"])
        if not folders_match(folder, row.get("written_label") or ""):
            if int(folder_rank) == pred_rank:
                if clf.registry is not None:
                    clf.registry.note_written_label(str(row["uid"]), folder)
                continue
            observe(clf, rec, int(folder_rank), "corr", now=now)
            report.n_observed += 1
            report.n_corr += 1
        elif rec.is_answered and _observe_replied(clf, rec, pred_rank, now):
            report.n_observed += 1
            report.n_replied += 1
    return report


def nightly(
    mailbox: MailboxConfig,
    adapter: Adapter,
    clf: Classifier,
    *,
    now: datetime | None = None,
) -> NightlyReport:
    with clf.state.lock():
        return _nightly_locked(mailbox, adapter, clf, now=now)


def _nightly_locked(
    mailbox: MailboxConfig,
    adapter: Adapter,
    clf: Classifier,
    *,
    now: datetime | None = None,
) -> NightlyReport:
    now = now or utcnow()
    report = NightlyReport()
    if clf.registry is None:
        report.kpi = {"error": "nessun registro"}
        return report

    rows = clf.registry.open_rows(older_than_hours=OBSERVE_DELAY_HOURS, now=now)
    uids = [r["uid"] for r in rows]
    try:
        status = adapter.fetch_status(
            uids,
            message_ids={r["uid"]: r.get("message_id") or "" for r in rows},
        )
    except Exception as exc:
        report.kpi = {"error": str(exc)}
        return report

    for row in rows:
        rec = status.get(row["uid"])
        kind = _apply_observation(clf, row, rec, mailbox, now)
        report.n_observed += 1
        if kind == "corr":
            report.n_corr += 1
        elif kind == "conf":
            report.n_conf += 1
        elif kind == "replied":
            report.n_replied += 1
        elif kind == "deleted":
            report.n_deleted += 1
        elif kind == "unread":
            report.n_unread += 1

    since = now - timedelta(hours=OBSERVE_DELAY_HOURS)
    if clf.state.last_nightly_at:
        since = _parse_ts(clf.state.last_nightly_at)
    try:
        sent = adapter.fetch_sent(since)
        ingest_sent(clf.state, mailbox, sent)
        report.kpi["n_sent"] = len(sent)
    except Exception as exc:
        report.kpi["sent_error"] = str(exc)

    report.n_expired = clf.registry.expire_stale(now=now)
    clf.state.last_nightly_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    clf.state.save()
    report.kpi.update(compute_stats(clf.registry))
    return report


def _load_for_manual(adapter: Adapter | None, rec: EmailRecord) -> EmailRecord:
    if adapter is None:
        return rec
    if rec.uid:
        found = adapter.fetch_status(
            [rec.uid],
            message_ids={rec.uid: rec.message_id} if rec.message_id else None,
        )
        hit = found.get(rec.uid)
        if hit:
            return hit
    if rec.message_id:
        hit = adapter.fetch_by_message_id(rec.message_id)
        if hit:
            return hit
    if rec.subject or rec.snippet or rec.from_addr:
        return rec
    raise LookupError(rec.uid or rec.message_id or "messaggio")


def _registry_row_for(clf: Classifier, rec: EmailRecord) -> dict[str, Any] | None:
    if clf.registry is None:
        return None
    if rec.uid:
        row = clf.registry.get(rec.uid)
        if row:
            return row
    if rec.message_id:
        from neuraec.adapters.parse import canonical_message_id

        want = canonical_message_id(rec.message_id)
        if not want:
            return None
        for row in clf.registry.rows():
            if canonical_message_id(row.get("message_id") or "") == want:
                return row
    return None


def apply_manual(
    mailbox: MailboxConfig,
    adapter: Adapter | None,
    clf: Classifier,
    rec: EmailRecord,
    rank: int,
    *,
    now: datetime | None = None,
) -> bool:
    """Manual observation from the add-in: observe immediately, then write the label."""
    now = now or utcnow()
    rank = int(rank)
    if rank < 0 or rank >= mailbox.N:
        raise ValueError(f"rank {rank} fuori da 0..{mailbox.N - 1}")
    incoming = rec
    rec = _load_for_manual(adapter, rec)
    row = _registry_row_for(clf, rec)
    if row is not None:
        rec.uid = str(row["uid"])
    elif clf.registry is not None:
        clf.predict(rec, now=now, write_registry=True)
    ok = observe(clf, rec, rank, "manual", now=now)
    if adapter is not None and rec.uid:
        adapter.write_label(rec.uid, mailbox.label_for_rank(rank))
    incoming.uid = rec.uid
    incoming.message_id = rec.message_id
    return ok
