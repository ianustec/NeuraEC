from __future__ import annotations

import json
from pathlib import Path

from neuraec.records import LabelMap, MailboxConfig, default_priority_labels, infer_label_prefix


def load_mailbox_config(path: Path | str) -> MailboxConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_labels = data.get("labels") or []
    labels = [LabelMap(**item) if not isinstance(item, LabelMap) else item for item in raw_labels]
    n = int(data["N"])
    provider = str(data.get("provider") or "imap")
    prefix = str(data.get("label_prefix") or infer_label_prefix(labels))
    if not labels:
        labels = default_priority_labels(n, provider, prefix)
    profile = data.get("profile") or {"fig": [], "fun": [], "set": []}
    return MailboxConfig(
        mailbox_id=str(data["mailbox_id"]),
        user_id=str(data["user_id"]),
        own_addresses=list(data.get("own_addresses") or []),
        N=n,
        order=data.get("order", "desc"),
        labels=labels,
        contacts=list(data.get("contacts") or []),
        host=str(data.get("host") or ""),
        username=str(data.get("username") or ""),
        port=int(data.get("port") or 993),
        tls=str(data.get("tls") or "ssl"),
        provider=provider,
        label_prefix=prefix,
        profile=profile,
        placement=str(data.get("placement") or ""),
    )
