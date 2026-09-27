from __future__ import annotations

import base64
import html
import re
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from email.utils import getaddresses
from typing import Any

from neuraec.constants import SNIPPET_CHARS
from neuraec.encoder import strip_html
from neuraec.records import EmailRecord, normalize_addr

_WS = re.compile(r"\s+")
PRECEDENCE_BULK = {"bulk", "list", "junk"}


def header_first(headers: Any, *names: str) -> str:
    if headers is None:
        return ""
    wanted = {n.lower() for n in names}
    getter = getattr(headers, "get", None)
    for name in names:
        val = getter(name) if getter else None
        if val is None and getter is not None:
            val = getter(name.lower())
        text = _header_to_text(val)
        if text:
            return text
    if hasattr(headers, "keys"):
        for key in headers.keys():
            if str(key).lower() in wanted:
                text = _header_to_text(headers[key])
                if text:
                    return text
    return ""


def _header_to_text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return str(val[0]).strip() if val else ""
    return str(val).strip()


def headers_from_pairs(items: Sequence[dict[str, Any]] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        name = str(item.get("name") or "").strip()
        if not name or name.lower() in {k.lower() for k in out}:
            continue
        out[name] = str(item.get("value") or "")
    return out


def parse_references(raw: str) -> list[str]:
    return [tok.strip() for tok in (raw or "").split() if tok.strip()]


def snippet_from_parts(text: str | None, html_body: str | None, limit: int = SNIPPET_CHARS) -> str:
    plain = (text or "").strip()
    if plain:
        cleaned = _WS.sub(" ", plain).strip()
        return cleaned[:limit]
    cleaned = strip_html(html.unescape(html_body or ""))
    return cleaned[:limit]


def join_snippet(body: str, preview: str, limit: int = SNIPPET_CHARS) -> str:
    body = (body or "").strip()
    preview = (preview or "").strip()
    if body and preview and preview not in body:
        return f"{preview}\n{body}"[:limit]
    return (body or preview)[:limit]


def flags_seen_answered(flags: Iterable[str] | None) -> tuple[bool, bool]:
    names = {str(f).lstrip("\\").lower() for f in (flags or ())}
    return "seen" in names, "answered" in names


def canonical_message_id(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text.startswith("<") and text.endswith(">") and len(text) > 2:
        text = text[1:-1].strip()
    return text


def message_ids_match(a: str | None, b: str | None) -> bool:
    left = canonical_message_id(a)
    right = canonical_message_id(b)
    return bool(left) and left == right


def answered_message_ids(sent: Sequence[EmailRecord]) -> set[str]:
    out: set[str] = set()
    for rec in sent:
        mid = canonical_message_id(rec.in_reply_to)
        if mid:
            out.add(mid)
    return out


def mark_answered(records: Sequence[EmailRecord], sent: Sequence[EmailRecord]) -> list[EmailRecord]:
    ids = answered_message_ids(sent)
    for rec in records:
        if canonical_message_id(rec.message_id) in ids:
            rec.is_answered = True
    return list(records)


def decode_b64url(data: str | None) -> str:
    raw = (data or "").strip()
    if not raw:
        return ""
    pad = "=" * (-len(raw) % 4)
    try:
        decoded = base64.urlsafe_b64decode(raw + pad)
    except Exception:
        return ""
    return decoded.decode("utf-8", errors="replace")


def parse_address_header(value: str | None) -> tuple[list[str], str]:
    emails: list[str] = []
    name = ""
    for display, addr in getaddresses([value or ""]):
        if not addr or addr == "none":
            continue
        emails.append(normalize_addr(addr))
        if display and not name:
            name = display
    return [e for e in emails if e], name


def pick_priority_folder(candidates: Sequence[str], priority_names: set[str], fallback: str) -> str:
    wanted = {name.lower() for name in priority_names}
    for name in candidates:
        if name and name.lower() in wanted:
            return name
    return fallback


def bulk_flags(headers: Any) -> tuple[bool, bool, bool, bool]:
    precedence = header_first(headers, "Precedence").lower()
    auto = header_first(headers, "Auto-Submitted")
    return (
        bool(header_first(headers, "List-Unsubscribe")),
        bool(header_first(headers, "List-Id")),
        precedence in PRECEDENCE_BULK,
        bool(auto) and auto.lower() != "no",
    )


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def walk_mime(payload: dict[str, Any] | None):
    if not payload:
        return
    yield payload
    for part in payload.get("parts") or []:
        yield from walk_mime(part)


def gmail_bodies(payload: dict[str, Any] | None) -> tuple[str, str, bool]:
    plain = ""
    html_body = ""
    attachment = False
    for part in walk_mime(payload):
        mime = str(part.get("mimeType") or "").lower()
        filename = str(part.get("filename") or "")
        body = part.get("body") or {}
        if filename and mime not in ("text/plain", "text/html", "text/"):
            attachment = True
        if body.get("attachmentId") and filename:
            attachment = True
        data = body.get("data")
        if not data:
            continue
        text = decode_b64url(data)
        if mime in ("text/plain", "text/") and not plain:
            plain = text
        elif mime == "text/html" and not html_body:
            html_body = text
    return plain, html_body, attachment


def gmail_message_to_record(
    msg: dict[str, Any],
    *,
    name_by_id: dict[str, str] | None = None,
    priority_names: set[str] | None = None,
) -> EmailRecord:
    name_by_id = name_by_id or {}
    priority_names = priority_names or set()
    payload = msg.get("payload") or {}
    headers = headers_from_pairs(payload.get("headers"))
    label_ids = [str(x) for x in (msg.get("labelIds") or [])]
    names = [name_by_id.get(lid, lid) for lid in label_ids]
    fallback = "SENT" if "SENT" in label_ids else "INBOX"
    folder = pick_priority_folder(names, priority_names, fallback)
    plain, html_body, attachment = gmail_bodies(payload)
    from_addrs, from_name = parse_address_header(header_first(headers, "From"))
    to_addrs, _ = parse_address_header(header_first(headers, "To"))
    cc_addrs, _ = parse_address_header(header_first(headers, "Cc"))
    unsub, list_id, bulk, auto = bulk_flags(headers)
    internal = msg.get("internalDate")
    if internal:
        received = datetime.fromtimestamp(int(internal) / 1000.0, tz=timezone.utc)
    else:
        received = datetime.now(timezone.utc)
    message_id = header_first(headers, "Message-ID", "Message-Id") or str(msg.get("id") or "")
    in_reply = header_first(headers, "In-Reply-To") or None
    return EmailRecord(
        uid=str(msg.get("id") or ""),
        message_id=message_id,
        in_reply_to=in_reply,
        references=parse_references(header_first(headers, "References")),
        thread_id=str(msg.get("threadId") or "") or None,
        received_at=received,
        from_addr=from_addrs[0] if from_addrs else "",
        from_name=from_name,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        subject=header_first(headers, "Subject"),
        snippet=join_snippet(snippet_from_parts(plain, html_body), str(msg.get("snippet") or "")),
        has_attachment=attachment,
        list_unsubscribe=unsub,
        list_id=list_id,
        precedence_bulk=bulk,
        auto_submitted=auto,
        is_seen="UNREAD" not in label_ids,
        is_answered=False,
        folder=folder,
    )


def graph_addrs(items: Sequence[dict[str, Any]] | dict[str, Any] | None) -> tuple[list[str], str]:
    if items is None:
        raw: list[Any] = []
    elif isinstance(items, dict):
        raw = [items]
    else:
        raw = list(items)
    emails: list[str] = []
    name = ""
    for item in raw:
        ea = item.get("emailAddress") if isinstance(item, dict) else None
        ea = ea if isinstance(ea, dict) else (item if isinstance(item, dict) else {})
        addr = normalize_addr(ea.get("address") or "")
        if addr:
            emails.append(addr)
        if not name:
            name = str(ea.get("name") or "")
    return emails, name


def graph_message_to_record(
    msg: dict[str, Any],
    *,
    folder_name: str = "",
    priority_names: set[str] | None = None,
) -> EmailRecord:
    priority_names = priority_names or set()
    categories = [str(c) for c in (msg.get("categories") or [])]
    folder = pick_priority_folder(categories, priority_names, folder_name or "inbox")
    headers = headers_from_pairs(msg.get("internetMessageHeaders"))
    body = msg.get("body") or {}
    content = str(body.get("content") or "")
    if str(body.get("contentType") or "").lower() == "html":
        body_text = snippet_from_parts("", content)
    else:
        body_text = snippet_from_parts(content, "")
    from_addrs, from_name = graph_addrs(msg.get("from"))
    to_addrs, _ = graph_addrs(msg.get("toRecipients"))
    cc_addrs, _ = graph_addrs(msg.get("ccRecipients"))
    unsub, list_id, bulk, auto = bulk_flags(headers)
    received_raw = str(msg.get("receivedDateTime") or "")
    if received_raw:
        received = _as_utc(datetime.fromisoformat(received_raw.replace("Z", "+00:00")))
    else:
        received = datetime.now(timezone.utc)
    message_id = str(msg.get("internetMessageId") or "") or header_first(headers, "Message-ID")
    in_reply = header_first(headers, "In-Reply-To") or None
    return EmailRecord(
        uid=str(msg.get("id") or ""),
        message_id=message_id,
        in_reply_to=in_reply,
        references=parse_references(header_first(headers, "References")),
        thread_id=str(msg.get("conversationId") or "") or None,
        received_at=received,
        from_addr=from_addrs[0] if from_addrs else "",
        from_name=from_name,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        subject=str(msg.get("subject") or header_first(headers, "Subject")),
        snippet=join_snippet(body_text, str(msg.get("bodyPreview") or "")),
        has_attachment=bool(msg.get("hasAttachments")),
        list_unsubscribe=unsub,
        list_id=list_id,
        precedence_bulk=bulk,
        auto_submitted=auto,
        is_seen=bool(msg.get("isRead")),
        is_answered=False,
        folder=folder,
    )
