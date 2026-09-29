from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from neuraec.adapters.base import Adapter, ProbeItem, label_names
from neuraec.adapters.parse import answered_message_ids, canonical_message_id, graph_message_to_record
from neuraec.constants import SENT_LOOKBACK_DAYS
from neuraec.records import DEFAULT_LABEL_PREFIX, EmailRecord, LabelMap, is_priority_name, utcnow

GRAPH_DELEGATED_SCOPES = (
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/MailboxSettings.ReadWrite",
    "https://graph.microsoft.com/User.Read",
)

GRAPH_SELECT = ",".join(
    [
        "id",
        "conversationId",
        "internetMessageId",
        "subject",
        "bodyPreview",
        "receivedDateTime",
        "isRead",
        "hasAttachments",
        "parentFolderId",
        "categories",
        "from",
        "toRecipients",
        "ccRecipients",
        "body",
        "internetMessageHeaders",
    ]
)

Transport = Callable[..., dict[str, Any]]


def _mid_forms(message_id: str) -> list[str]:
    raw = (message_id or "").strip()
    if not raw:
        return []
    bare = canonical_message_id(raw)
    forms = [raw]
    if bare and f"<{bare}>" not in forms:
        forms.append(f"<{bare}>")
    if bare and bare not in forms:
        forms.append(bare)
    return forms


class GraphAdapter(Adapter):
    """Microsoft Graph. uid = message id. Label = priority category. is_answered comes from Sent."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        refresh_token: str = "",
        *,
        tenant: str = "common",
        access_token: str = "",
        transport: Transport | None = None,
        label_prefix: str = DEFAULT_LABEL_PREFIX,
        placement: str = "label",
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.tenant = tenant or "common"
        self.access_token = access_token
        self.transport = transport
        self.base = "https://graph.microsoft.com/v1.0/me"
        self._folder_by_id: dict[str, str] = {}
        self._extra_priority: set[str] = set()
        self._answered_cache: set[str] | None = None
        self.label_prefix = label_prefix or DEFAULT_LABEL_PREFIX
        # "label": categoria di Outlook, la mail resta in Arrivo.
        # "move": a real folder with the same name; the message id changes.
        self.placement = placement if placement in ("label", "move") else "label"

    def supports_labels(self) -> bool:
        return True

    def connect(self) -> None:
        if self.transport is not None or self.access_token:
            return
        self._token()

    def close(self) -> None:
        return None

    def __enter__(self) -> GraphAdapter:
        self.connect()
        return self

    def _token(self) -> str:
        if self.access_token:
            return self.access_token
        import msal

        app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant}",
        )
        result = app.acquire_token_by_refresh_token(
            self.refresh_token,
            scopes=list(GRAPH_DELEGATED_SCOPES),
        )
        if "access_token" not in result:
            raise RuntimeError(result.get("error_description") or "Graph token was not obtained")
        self.access_token = result["access_token"]
        return self.access_token

    def _request(self, method: str, url: str, *, json_body: dict | None = None, params: dict | None = None) -> dict:
        if self.transport is not None:
            data = self.transport(method, url, json_body=json_body, params=params)
            return data or {}
        import requests

        resp = requests.request(
            method,
            url,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
            },
            json=json_body,
            params=params,
            timeout=60,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Graph {method} {url} → {resp.status_code} {resp.text[:400]}")
        if resp.status_code == 204 or not resp.content:
            return {}
        body = resp.json()
        return body if isinstance(body, dict) else {}

    def _pages(self, url: str, params: dict | None = None) -> list[dict]:
        out: list[dict] = []
        while url:
            data = self._request("GET", url, params=params)
            out.extend(data.get("value") or [])
            url = data.get("@odata.nextLink") or ""
            params = None
        return out

    def _load_folders(self, force: bool = False) -> None:
        if self._folder_by_id and not force:
            return
        self._folder_by_id = {}
        for row in self._pages(f"{self.base}/mailFolders", {"$top": "100"}):
            self._folder_by_id[str(row.get("id") or "")] = str(row.get("displayName") or "")

    def _folder_id(self, name: str) -> str | None:
        self._load_folders()
        for fid, display in self._folder_by_id.items():
            if display.lower() == name.lower():
                return fid
        return None

    def _priority_names(self, msg: dict | None = None) -> set[str]:
        names = {n for n in self._extra_priority if is_priority_name(n, self.label_prefix)}
        for cat in (msg or {}).get("categories") or []:
            if is_priority_name(str(cat), self.label_prefix):
                names.add(str(cat))
        return names

    def _record(self, msg: dict, folder_name: str = "") -> EmailRecord:
        if not folder_name:
            self._load_folders()
            folder_name = self._folder_by_id.get(str(msg.get("parentFolderId") or ""), "") or "inbox"
        return graph_message_to_record(
            msg,
            folder_name=folder_name,
            priority_names=self._priority_names(msg),
        )

    def _answered_ids(self) -> set[str]:
        if self._answered_cache is None:
            since = utcnow() - timedelta(days=SENT_LOOKBACK_DAYS)
            self._answered_cache = answered_message_ids(self.fetch_sent(since))
        return self._answered_cache

    def _apply_answered(self, records: list[EmailRecord]) -> list[EmailRecord]:
        ids = self._answered_ids()
        for rec in records:
            if canonical_message_id(rec.message_id) in ids:
                rec.is_answered = True
        return records

    def fetch_unseen(self, *, limit: int | None = None, skip_uids: set[str] | None = None) -> list[EmailRecord]:
        skip = skip_uids or set()
        rows: list[dict] = []
        url = f"{self.base}/mailFolders/inbox/messages"
        params: dict | None = {"$filter": "isRead eq false", "$top": "50", "$select": GRAPH_SELECT}
        while url and (limit is None or len(rows) < limit):
            data = self._request("GET", url, params=params)
            for row in data.get("value") or []:
                if str(row.get("id") or "") in skip:
                    continue
                rows.append(row)
                if limit is not None and len(rows) >= limit:
                    break
            url = "" if limit is not None and len(rows) >= limit else (data.get("@odata.nextLink") or "")
            params = None
        recs = [self._record(row, "inbox") for row in rows]
        return self._apply_answered(recs)

    def fetch_status(
        self,
        uids: Sequence[str],
        *,
        message_ids: dict[str, str] | None = None,
    ) -> dict[str, EmailRecord]:
        message_ids = message_ids or {}
        found: dict[str, EmailRecord] = {}
        for uid in uids:
            if not uid:
                continue
            try:
                msg = self._request(
                    "GET",
                    f"{self.base}/messages/{quote(uid, safe='')}",
                    params={"$select": GRAPH_SELECT},
                )
            except Exception as exc:
                if "404" not in str(exc):
                    raise
                msg = {}
            if msg.get("id"):
                found[uid] = self._record(msg)
                continue
            mid = message_ids.get(uid) or ""
            if not mid:
                continue
            rec = self.fetch_by_message_id(mid)
            if rec:
                rec.uid = uid
                found[uid] = rec
        self._apply_answered(list(found.values()))
        return found

    def probe(self, items: Sequence[ProbeItem], labels: Sequence[str]) -> dict[str, EmailRecord] | None:
        """Where open mail sits today.

        With categories the id does not change: list each category and download only
        what changed. With folders a move changes the id: match by Message-ID.
        """
        if self.placement == "move":
            return self._probe_folders(items, labels)
        written = {uid: label for uid, _mid, label in items if uid}
        if not written:
            return {}
        where: dict[str, str] = {}
        for name in labels:
            escaped = name.replace("'", "''")
            rows = self._pages(
                f"{self.base}/messages",
                {"$filter": f"categories/any(c:c eq '{escaped}')", "$top": "100", "$select": "id"},
            )
            for row in rows:
                uid = str(row.get("id") or "")
                if uid in written:
                    where[uid] = name
        found: dict[str, EmailRecord] = {}
        for uid, name in where.items():
            if name == written[uid]:
                continue
            msg = self._request(
                "GET",
                f"{self.base}/messages/{quote(uid, safe='')}",
                params={"$select": GRAPH_SELECT},
            )
            if msg.get("id"):
                found[uid] = self._record(msg)
        return found

    def _probe_folders(self, items: Sequence[ProbeItem], labels: Sequence[str]) -> dict[str, EmailRecord]:
        wanted: dict[str, ProbeItem] = {}
        for item in items:
            key = canonical_message_id(item[1])
            if key:
                wanted[key] = item
        if not wanted:
            return {}
        found: dict[str, EmailRecord] = {}
        for name in labels:
            fid = self._folder_id(name)
            if not fid:
                continue
            rows = self._pages(
                f"{self.base}/mailFolders/{quote(fid, safe='')}/messages",
                {"$top": "100", "$select": "id,internetMessageId"},
            )
            for row in rows:
                item = wanted.get(canonical_message_id(str(row.get("internetMessageId") or "")))
                if item is None:
                    continue
                uid, _mid, written = item
                if written.lower() == name.lower():
                    continue
                msg = self._request(
                    "GET",
                    f"{self.base}/messages/{quote(str(row.get('id') or ''), safe='')}",
                    params={"$select": GRAPH_SELECT},
                )
                if msg.get("id"):
                    rec = self._record(msg, name)
                    rec.uid = uid
                    found[uid] = rec
        return found

    def fetch_by_message_id(self, message_id: str) -> EmailRecord | None:
        for cand in _mid_forms(message_id):
            escaped = cand.replace("'", "''")
            rows = self._pages(
                f"{self.base}/messages",
                {
                    "$filter": f"internetMessageId eq '{escaped}'",
                    "$top": "1",
                    "$select": GRAPH_SELECT,
                },
            )
            if rows:
                rec = self._record(rows[0])
                self._apply_answered([rec])
                return rec
        return None

    def write_label(self, uid: str, provider_label: str) -> None:
        url = f"{self.base}/messages/{quote(uid, safe='')}"
        if self.placement == "move":
            fid = self._folder_id(provider_label)
            if not fid:
                self.ensure_labels([provider_label])
                fid = self._folder_id(provider_label)
            if not fid:
                raise RuntimeError(f"folder {provider_label} was not found")
            self._request("POST", f"{url}/move", json_body={"destinationId": fid})
            return
        current = self._request("GET", url, params={"$select": "categories"})
        kept = [str(c) for c in (current.get("categories") or []) if not is_priority_name(str(c), self.label_prefix)]
        kept.append(provider_label)
        self._request("PATCH", url, json_body={"categories": kept})

    def ensure_labels(self, labels: Sequence[LabelMap | str]) -> None:
        if self.placement == "move":
            self._load_folders(force=True)
            have = {name.lower() for name in self._folder_by_id.values()}
            for name in label_names(labels):
                self._extra_priority.add(name)
                if name.lower() in have:
                    continue
                created = self._request("POST", f"{self.base}/mailFolders", json_body={"displayName": name})
                if created.get("id"):
                    self._folder_by_id[str(created["id"])] = name
                have.add(name.lower())
            return
        existing = self._request("GET", f"{self.base}/outlook/masterCategories")
        have = {str(row.get("displayName") or "") for row in (existing.get("value") or [])}
        for name in label_names(labels):
            self._extra_priority.add(name)
            if name in have:
                continue
            self._request(
                "POST",
                f"{self.base}/outlook/masterCategories",
                json_body={"displayName": name, "color": "preset0"},
            )
            have.add(name)

    def fetch_sent(self, since: datetime) -> list[EmailRecord]:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        stamp = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self._pages(
            f"{self.base}/mailFolders/sentitems/messages",
            {
                "$filter": f"receivedDateTime ge {stamp}",
                "$top": "50",
                "$select": GRAPH_SELECT,
            },
        )
        return [self._record(row, "sentitems") for row in rows]
