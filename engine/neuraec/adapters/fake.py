from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from neuraec.adapters.base import Adapter, ProbeItem, label_names
from neuraec.adapters.parse import message_ids_match
from neuraec.records import EmailRecord, LabelMap


class FakeAdapter(Adapter):
    """Casella in memoria. Stessi metodi dell'IMAP, nessuna rete."""

    def __init__(
        self,
        records: Sequence[EmailRecord] | None = None,
        sent: Sequence[EmailRecord] | None = None,
    ) -> None:
        self.messages: dict[str, EmailRecord] = {}
        self.sent: list[EmailRecord] = list(sent or [])
        self.folders: set[str] = {"INBOX"}
        self.write_calls: list[tuple[str, str]] = []
        self.probe_calls = 0
        for rec in records or []:
            self.add(rec)

    def add(self, rec: EmailRecord) -> None:
        if not rec.folder:
            rec.folder = "INBOX"
        self.messages[rec.uid] = rec
        self.folders.add(rec.folder)

    def fetch_unseen(self, *, limit: int | None = None, skip_uids: set[str] | None = None) -> list[EmailRecord]:
        skip = skip_uids or set()
        out = []
        for rec in self.messages.values():
            if rec.is_seen or rec.uid in skip:
                continue
            if rec.folder in ("", "INBOX"):
                out.append(rec)
                if limit is not None and len(out) >= limit:
                    break
        return out

    def fetch_status(
        self,
        uids: Sequence[str],
        *,
        message_ids: dict[str, str] | None = None,
    ) -> dict[str, EmailRecord]:
        return {uid: self.messages[uid] for uid in uids if uid in self.messages}

    def write_label(self, uid: str, provider_label: str) -> None:
        if uid not in self.messages:
            raise KeyError(uid)
        self.messages[uid].folder = provider_label
        self.folders.add(provider_label)
        self.write_calls.append((uid, provider_label))

    def ensure_labels(self, labels: Sequence[LabelMap | str]) -> None:
        for name in label_names(labels):
            self.folders.add(name)

    def fetch_sent(self, since: datetime) -> list[EmailRecord]:
        return [rec for rec in self.sent if rec.received_at >= since]

    def fetch_by_message_id(self, message_id: str) -> EmailRecord | None:
        for rec in self.messages.values():
            if message_ids_match(rec.message_id, message_id):
                return rec
        return None

    def probe(self, items: Sequence[ProbeItem], labels: Sequence[str]) -> dict[str, EmailRecord] | None:
        self.probe_calls += 1
        wanted = set(labels)
        found: dict[str, EmailRecord] = {}
        for uid, _mid, _written in items:
            rec = self.messages.get(uid)
            if rec is not None and rec.folder in wanted:
                found[uid] = rec
        return found
