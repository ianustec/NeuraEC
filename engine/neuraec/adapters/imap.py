from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Any

from neuraec.adapters.base import Adapter, ProbeItem, label_names
from neuraec.adapters.parse import (
    PRECEDENCE_BULK,
    canonical_message_id,
    flags_seen_answered,
    header_first,
    parse_references,
    snippet_from_parts,
)
from neuraec.records import EmailRecord, LabelMap, folders_match, normalize_addr

SENT_FOLDER_NAMES = {
    "sent",
    "inbox.sent",
    "posta inviata",
    "sent items",
    "inbox.sent messages",
    "sent messages",
    "[gmail]/sent mail",
    "sent mail",
}


def _as_addr_list(values: Any, fallback: Any) -> tuple[list[str], str]:
    if values is None:
        items: list[Any] = []
    elif isinstance(values, (list, tuple)):
        items = list(values)
    else:
        items = [values]
    emails: list[str] = []
    name = ""
    for item in items:
        email = getattr(item, "email", None)
        if email:
            emails.append(normalize_addr(email))
            if not name:
                name = getattr(item, "name", "") or ""
        elif item:
            emails.append(normalize_addr(str(item)))
    if not emails:
        if isinstance(fallback, (list, tuple)):
            emails = [normalize_addr(str(x)) for x in fallback if x]
        elif fallback:
            emails = [normalize_addr(str(fallback))]
    return [e for e in emails if e], name


def _has_attachment(attachments: Iterable[Any] | None) -> bool:
    for att in attachments or []:
        disp = (getattr(att, "content_disposition", None) or "").lower()
        if disp == "attachment":
            return True
    return False


def message_to_record(msg: Any, folder: str) -> EmailRecord:
    headers = getattr(msg, "headers", None)
    message_id = header_first(headers, "Message-ID", "Message-Id") or (getattr(msg, "uid", None) or "")
    in_reply_to = header_first(headers, "In-Reply-To") or None
    references = parse_references(header_first(headers, "References"))
    to_addrs, _ = _as_addr_list(getattr(msg, "to_values", None), getattr(msg, "to", ()))
    cc_addrs, _ = _as_addr_list(getattr(msg, "cc_values", None), getattr(msg, "cc", ()))
    from_addrs, from_name = _as_addr_list(getattr(msg, "from_values", None), getattr(msg, "from_", ""))
    received = getattr(msg, "date", None) or datetime.now(timezone.utc)
    if isinstance(received, datetime) and received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    precedence = header_first(headers, "Precedence").lower()
    auto = header_first(headers, "Auto-Submitted")
    seen, answered = flags_seen_answered(getattr(msg, "flags", ()))
    return EmailRecord(
        uid=str(getattr(msg, "uid", "") or ""),
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        received_at=received,
        from_addr=from_addrs[0] if from_addrs else "",
        from_name=from_name,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        subject=getattr(msg, "subject", None) or "",
        snippet=snippet_from_parts(getattr(msg, "text", None), getattr(msg, "html", None)),
        has_attachment=_has_attachment(getattr(msg, "attachments", None)),
        list_unsubscribe=bool(header_first(headers, "List-Unsubscribe")),
        list_id=bool(header_first(headers, "List-Id")),
        precedence_bulk=precedence in PRECEDENCE_BULK,
        auto_submitted=bool(auto) and auto.lower() != "no",
        is_seen=seen,
        is_answered=answered,
        folder=folder,
    )


class ImapAdapter(Adapter):
    """Adapter IMAP con imap-tools. UID originale come chiave; dopo MOVE si cerca per Message-ID."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 993,
        tls: str = "ssl",
        inbox: str = "INBOX",
        sent_folder: str | None = None,
        client: Any = None,
        extra_folders: Sequence[str] | None = None,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = int(port)
        self.tls = tls
        self.inbox = inbox
        self.sent_folder = sent_folder
        self._client = client
        self._owns_client = client is None
        self._index: dict[str, tuple[str, str]] = {}
        self._extra_folders = list(extra_folders or [])

    def connect(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from imap_tools import MailBox, MailBoxStartTls, MailBoxUnencrypted
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("imap-tools is not installed") from exc
        if self.tls == "starttls":
            mb = MailBoxStartTls(self.host, self.port)
        elif self.tls == "none":
            mb = MailBoxUnencrypted(self.host, self.port)
        else:
            mb = MailBox(self.host, self.port)
        mb.login(self.username, self.password, initial_folder=self.inbox)
        self._client = mb
        return mb

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            try:
                self._client.logout()
            except Exception:
                pass
        if self._owns_client:
            self._client = None

    def __enter__(self) -> ImapAdapter:
        self.connect()
        return self

    def _mb(self) -> Any:
        if self._client is None:
            return self.connect()
        return self._client

    def _remember(self, rec: EmailRecord) -> None:
        self._index[rec.uid] = (rec.folder, rec.message_id)

    def _list_folders(self) -> list[str]:
        names: list[str] = []
        try:
            infos = self._mb().folder.list()
        except Exception:
            infos = []
        for info in infos:
            flags = {str(f).lstrip("\\").lower() for f in (getattr(info, "flags", ()) or ())}
            if "noselect" in flags:
                continue
            names.append(info.name)
        for extra in [self.inbox, *self._extra_folders]:
            if extra and extra not in names:
                names.append(extra)
        return names

    def _discover_sent(self) -> str | None:
        if self.sent_folder:
            return self.sent_folder
        try:
            infos = self._mb().folder.list()
        except Exception:
            return None
        for info in infos:
            flags = {str(f).lstrip("\\").lower() for f in (getattr(info, "flags", ()) or ())}
            if "sent" in flags:
                self.sent_folder = info.name
                return info.name
        for info in infos:
            key = info.name.replace("/", ".").strip().lower()
            if key in SENT_FOLDER_NAMES:
                self.sent_folder = info.name
                return info.name
        return None

    def _iter_folder(
        self,
        folder: str,
        *,
        uid_list: Sequence[str] | None = None,
        criteria: Any = None,
        headers_only: bool = False,
        bulk: bool | int = False,
        limit: int | None = None,
        skip_uids: set[str] | None = None,
    ) -> list[EmailRecord]:
        from imap_tools import AND

        mb = self._mb()
        try:
            mb.folder.set(folder)
        except Exception:
            return []
        kwargs: dict[str, Any] = {"mark_seen": False, "headers_only": headers_only, "bulk": bulk}
        if uid_list:
            kwargs["uid_list"] = list(uid_list)
        else:
            kwargs["criteria"] = criteria if criteria is not None else AND(all=True)
        skip = skip_uids or set()
        out: list[EmailRecord] = []
        try:
            for msg in mb.fetch(**kwargs):
                rec = message_to_record(msg, folder)
                if not rec.uid or rec.uid in skip:
                    continue
                self._remember(rec)
                out.append(rec)
                if limit is not None and len(out) >= limit:
                    break
        except Exception:
            return out
        return out

    def fetch_unseen(self, *, limit: int | None = None, skip_uids: set[str] | None = None) -> list[EmailRecord]:
        from imap_tools import AND

        return self._iter_folder(
            self.inbox,
            criteria=AND(seen=False),
            headers_only=False,
            limit=limit,
            skip_uids=skip_uids,
        )

    def fetch_status(
        self,
        uids: Sequence[str],
        *,
        message_ids: dict[str, str] | None = None,
    ) -> dict[str, EmailRecord]:
        found: dict[str, EmailRecord] = {}
        pending = [uid for uid in uids if uid]
        by_folder: dict[str, list[str]] = {}
        for uid in pending:
            folder, _mid = self._index.get(uid, (self.inbox, ""))
            by_folder.setdefault(folder, []).append(uid)
        for folder, group in by_folder.items():
            for rec in self._iter_folder(folder, uid_list=group, headers_only=False):
                if rec.uid in group:
                    found[rec.uid] = rec
        missing = [uid for uid in pending if uid not in found]
        if missing:
            for rec in self._search_missing(missing, message_ids or {}):
                found[rec.uid] = rec
        return found

    def probe(self, items: Sequence[ProbeItem], labels: Sequence[str]) -> dict[str, EmailRecord] | None:
        """One headers-only read per priority folder, matched by Message-ID.

        On IMAP a move changes the UID: the UID stored in the registry cannot find
        the mail. The body is downloaded only for mail whose folder changed.
        """
        wanted: dict[str, ProbeItem] = {}
        for item in items:
            key = canonical_message_id(item[1])
            if key:
                wanted[key] = item
        if not wanted:
            return {}
        found: dict[str, EmailRecord] = {}
        for folder in labels:
            for rec in self._iter_folder(folder, headers_only=True, bulk=True):
                item = wanted.get(canonical_message_id(rec.message_id))
                if item is None:
                    continue
                uid, _mid, written = item
                current_uid = rec.uid
                if not folders_match(rec.folder, written):
                    full = self._iter_folder(folder, uid_list=[current_uid], headers_only=False)
                    if full:
                        rec = full[0]
                rec.uid = uid
                found[uid] = rec
        return found

    def fetch_by_message_id(self, message_id: str) -> EmailRecord | None:
        from imap_tools import AND, Header

        mid = (message_id or "").strip()
        if not mid:
            return None
        candidates = [mid]
        bare = canonical_message_id(mid)
        bracketed = f"<{bare}>" if bare else ""
        if bracketed and bracketed not in candidates:
            candidates.append(bracketed)
        for folder in self._list_folders():
            for cand in candidates:
                recs = self._iter_folder(
                    folder,
                    criteria=AND(header=Header("Message-ID", cand)),
                    headers_only=False,
                )
                if recs:
                    return recs[0]
        return None

    def _search_missing(self, uids: Sequence[str], message_ids: dict[str, str]) -> list[EmailRecord]:
        from imap_tools import AND, Header

        out: list[EmailRecord] = []
        have: set[str] = set()
        folders = self._list_folders()
        for folder in folders:
            still = [uid for uid in uids if uid not in have]
            if still:
                for rec in self._iter_folder(folder, uid_list=still, headers_only=False):
                    if rec.uid in still:
                        out.append(rec)
                        have.add(rec.uid)
            for uid in [u for u in uids if u not in have]:
                mid = message_ids.get(uid) or ""
                if not mid:
                    continue
                try:
                    recs = self._iter_folder(
                        folder,
                        criteria=AND(header=Header("Message-ID", mid)),
                        headers_only=False,
                    )
                except Exception:
                    recs = []
                if recs:
                    rec = recs[0]
                    rec.uid = uid
                    self._remember(rec)
                    out.append(rec)
                    have.add(uid)
            if len(have) >= len(uids):
                break
        return out

    def write_label(self, uid: str, provider_label: str) -> None:
        mb = self._mb()
        folder, message_id = self._index.get(uid, (self.inbox, ""))
        located = folder
        if not self._uid_in_folder(folder, uid):
            located = self._locate_uid(uid, message_id)
        if located is None:
            raise KeyError(uid)
        if folders_match(located, provider_label):
            self._index[uid] = (provider_label, message_id)
            return
        mb.folder.set(located)
        mb.move(uid, provider_label)
        self._index[uid] = (provider_label, message_id)

    def _uid_in_folder(self, folder: str, uid: str) -> bool:
        recs = self._iter_folder(folder, uid_list=[uid], headers_only=True)
        return any(r.uid == uid for r in recs)

    def _locate_uid(self, uid: str, message_id: str) -> str | None:
        for folder in self._list_folders():
            if self._uid_in_folder(folder, uid):
                return folder
        if message_id:
            from imap_tools import AND, Header

            for folder in self._list_folders():
                recs = self._iter_folder(
                    folder,
                    criteria=AND(header=Header("Message-ID", message_id)),
                    headers_only=True,
                )
                if recs:
                    return folder
        return None

    def ensure_labels(self, labels: Sequence[LabelMap | str]) -> None:
        mb = self._mb()
        for name in label_names(labels):
            try:
                if not mb.folder.exists(name):
                    mb.folder.create(name)
            except Exception:
                continue
            self._extra_folders.append(name)

    def fetch_sent(self, since: datetime) -> list[EmailRecord]:
        from imap_tools import AND

        folder = self._discover_sent()
        if not folder:
            return []
        day = since.date() if isinstance(since, datetime) else since
        return self._iter_folder(folder, criteria=AND(date_gte=day), headers_only=True, bulk=100)
