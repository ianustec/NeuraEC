from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from datetime import datetime

from neuraec.records import EmailRecord, LabelMap


# Open registry row as the provider sees it: written uid, Message-ID, written folder.
ProbeItem = tuple[str, str, str]


def label_names(labels: Sequence[LabelMap | str]) -> list[str]:
    out: list[str] = []
    for lab in labels:
        out.append(lab.provider_label if isinstance(lab, LabelMap) else str(lab))
    return out


class Adapter(ABC):
    """Boundary to the provider. Produces EmailRecord; does not touch user state."""

    def fetch_unseen(self, *, limit: int | None = None, skip_uids: set[str] | None = None) -> list[EmailRecord]:
        raise NotImplementedError

    def fetch_status(
        self,
        uids: Sequence[str],
        *,
        message_ids: dict[str, str] | None = None,
    ) -> dict[str, EmailRecord]:
        raise NotImplementedError

    def write_label(self, uid: str, provider_label: str) -> None:
        raise NotImplementedError

    def supports_labels(self) -> bool:
        """True when the provider can label mail and leave it in the inbox. IMAP has folders only."""
        return False

    def ensure_labels(self, labels: Sequence[LabelMap | str]) -> None:
        raise NotImplementedError

    def fetch_sent(self, since: datetime) -> list[EmailRecord]:
        raise NotImplementedError

    def fetch_by_message_id(self, message_id: str) -> EmailRecord | None:
        return None

    def probe(self, items: Sequence[ProbeItem], labels: Sequence[str]) -> dict[str, EmailRecord] | None:
        """Fast path: where open mail sits today, looking only at priority folders.

        Returns written uid → current record for mail found in one of `labels`.
        A record whose folder differs from the one written must be complete (body):
        it will be observed as a correction. Mail that is not found is omitted, not
        declared deleted: that stays on the nightly step. None when the provider cannot
        do this cheaply; the fast path then skips.
        """
        return None

    def connect(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> Adapter:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False
