"""Apprendimento senza provider: scrive lo stato (§8.3). Nessun gradiente in tappa 1."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from neuraec.classifier import Classifier
from neuraec.constants import CONF_PER_SENDER_WEEK, SNIPPET_CHARS
from neuraec.features import relazione, struttura
from neuraec.records import EmailRecord, utcnow

SOURCE_WEIGHT = {
    "corr": 1.0,
    "manual": 1.0,
    "replied": 0.5,
    "conf": 0.2,
}
CORR_SOURCES = {"corr", "manual"}

# come si chiude la riga del registro per ciascuna sorgente (§8.2)
_REGISTRY_CLOSE = {
    "corr": ("moved", "frozen"),
    "manual": ("manual", "frozen"),
    "replied": ("replied", "resolved"),
    "conf": ("read_unmoved", "resolved"),
}


def observe(
    clf: Classifier,
    rec: EmailRecord,
    rank: int,
    source: str,
    *,
    now: datetime | None = None,
    e: np.ndarray | None = None,
    persist: bool = True,
) -> bool:
    """Scrive esemplare, masse per rango, replied_to e chiude la riga del registro.

    Returns False when the observation was discarded (confirmation cap per sender).
    """
    if source not in SOURCE_WEIGHT:
        raise ValueError(f"unknown source {source}")
    with clf.state.lock():
        return _observe_locked(clf, rec, rank, source, now=now, e=e, persist=persist)


def _observe_locked(
    clf: Classifier,
    rec: EmailRecord,
    rank: int,
    source: str,
    *,
    now: datetime | None = None,
    e: np.ndarray | None = None,
    persist: bool = True,
) -> bool:
    now = now or rec.received_at or utcnow()
    state = clf.state
    weight = SOURCE_WEIGHT[source]

    if source == "conf" and state.conf_count_week(rec.from_addr, now) >= CONF_PER_SENDER_WEEK:
        return False

    if e is None:
        e = clf.encode_record(rec)
    s = struttura(rec, clf.mailbox)
    r = relazione(rec, clf.mailbox, state.replied_to)

    state.upsert_exemplar(
        uid=rec.uid,
        e=e,
        message_id=rec.message_id,
        thread_key=rec.thread_key,
        from_addr=rec.from_addr,
        rank=int(rank),
        source=source,
        weight=weight,
        s=s.tolist(),
        r=r.tolist(),
        ts=now,
        subject=rec.subject,
        snippet=rec.snippet[:SNIPPET_CHARS],
    )
    state.add_rank_mass(rec.from_addr, int(rank), weight, now, source=source)
    if source == "replied":
        state.bump_replied(rec.from_addr)
    if source in CORR_SOURCES:
        state.n_corr += 1
    if source == "conf":
        state.n_conf += 1

    if clf.registry is not None:
        action, status = _REGISTRY_CLOSE[source]
        clf.registry.resolve(rec.uid, user_action=action, final_rank=int(rank), status=status, now=now)

    if persist:
        state.save()
    return True
