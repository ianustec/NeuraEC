from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from neuraec.adapters.base import Adapter, ProbeItem, label_names
from neuraec.adapters.parse import (
    answered_message_ids,
    canonical_message_id,
    gmail_message_to_record,
)
from neuraec.constants import SENT_LOOKBACK_DAYS
from neuraec.records import DEFAULT_LABEL_PREFIX, EmailRecord, LabelMap, is_priority_name, utcnow


class GmailAdapter(Adapter):
    """Gmail API. uid = message id. is_answered dalle Inviate (In-Reply-To)."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        refresh_token: str = "",
        *,
        service: Any = None,
        label_prefix: str = DEFAULT_LABEL_PREFIX,
        placement: str = "label",
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._service = service
        self._owns_service = service is None
        self._name_by_id: dict[str, str] = {}
        self._id_by_name: dict[str, str] = {}
        self._answered_cache: set[str] | None = None
        self.label_prefix = label_prefix or DEFAULT_LABEL_PREFIX
        # "label": the label is added and the mail stays in the inbox.
        # "move": INBOX is also removed, which on Gmail is the same as moving it into the folder.
        self.placement = placement if placement in ("label", "move") else "label"

    def supports_labels(self) -> bool:
        return True

    def connect(self) -> Any:
        if self._service is not None:
            return self._service
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def close(self) -> None:
        if self._owns_service:
            self._service = None

    def __enter__(self) -> GmailAdapter:
        self.connect()
        return self

    def _svc(self) -> Any:
        if self._service is None:
            return self.connect()
        return self._service

    def _load_labels(self, force: bool = False) -> None:
        if self._id_by_name and not force:
            return
        resp = self._svc().users().labels().list(userId="me").execute()
        self._name_by_id = {}
        self._id_by_name = {}
        for lab in resp.get("labels") or []:
            self._name_by_id[str(lab["id"])] = str(lab["name"])
            self._id_by_name[str(lab["name"])] = str(lab["id"])

    def _priority_names(self) -> set[str]:
        self._load_labels()
        return {name for name in self._id_by_name if is_priority_name(name, self.label_prefix)}

    def _list_ids(self, query: str) -> list[str]:
        ids: list[str] = []
        page = None
        while True:
            kwargs: dict[str, Any] = {"userId": "me", "q": query, "maxResults": 100}
            if page:
                kwargs["pageToken"] = page
            resp = self._svc().users().messages().list(**kwargs).execute()
            ids.extend(str(m["id"]) for m in (resp.get("messages") or []))
            page = resp.get("nextPageToken")
            if not page:
                break
        return ids

    def _get(self, uid: str, *, metadata: bool = False) -> dict[str, Any] | None:
        try:
            kwargs: dict[str, Any] = {"userId": "me", "id": uid}
            if metadata:
                kwargs["format"] = "metadata"
                kwargs["metadataHeaders"] = [
                    "From",
                    "To",
                    "Cc",
                    "Subject",
                    "Message-ID",
                    "In-Reply-To",
                    "References",
                    "Date",
                ]
            else:
                kwargs["format"] = "full"
            return self._svc().users().messages().get(**kwargs).execute()
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 404 or "404" in str(exc):
                return None
            raise

    def _to_record(self, msg: dict[str, Any]) -> EmailRecord:
        self._load_labels()
        return gmail_message_to_record(
            msg,
            name_by_id=self._name_by_id,
            priority_names=self._priority_names(),
        )

    def _answered_ids(self) -> set[str]:
        if self._answered_cache is None:
            since = utcnow() - timedelta(days=SENT_LOOKBACK_DAYS)
            sent = self.fetch_sent(since)
            self._answered_cache = answered_message_ids(sent)
        return self._answered_cache

    def _apply_answered(self, records: list[EmailRecord]) -> list[EmailRecord]:
        ids = self._answered_ids()
        for rec in records:
            if canonical_message_id(rec.message_id) in ids:
                rec.is_answered = True
        return records

    def fetch_unseen(self) -> list[EmailRecord]:
        recs = []
        for uid in self._list_ids("in:inbox is:unread"):
            msg = self._get(uid)
            if msg:
                recs.append(self._to_record(msg))
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
            msg = self._get(uid) if uid else None
            if msg is None and message_ids.get(uid):
                rec = self.fetch_by_message_id(message_ids[uid])
                if rec:
                    rec.uid = uid
                    found[uid] = rec
                continue
            if msg:
                found[uid] = self._to_record(msg)
        self._apply_answered(list(found.values()))
        return found

    def probe(self, items: Sequence[ProbeItem], labels: Sequence[str]) -> dict[str, EmailRecord] | None:
        """Gmail ids do not change with the label: listing ids per label is enough.

        The message is downloaded only when it now carries a label different from the one written.
        """
        written = {uid: label for uid, _mid, label in items if uid}
        if not written:
            return {}
        where: dict[str, str] = {}
        for name in labels:
            for uid in self._list_ids(f"label:{name}"):
                if uid in written:
                    where[uid] = name
        found: dict[str, EmailRecord] = {}
        for uid, name in where.items():
            if name == written[uid]:
                continue
            msg = self._get(uid)
            if msg:
                found[uid] = self._to_record(msg)
        return found

    def fetch_by_message_id(self, message_id: str) -> EmailRecord | None:
        bare = canonical_message_id(message_id)
        if not bare:
            return None
        ids = self._list_ids(f"rfc822msgid:{bare}")
        if not ids:
            return None
        msg = self._get(ids[0])
        if not msg:
            return None
        rec = self._to_record(msg)
        self._apply_answered([rec])
        return rec

    def write_label(self, uid: str, provider_label: str) -> None:
        self._load_labels()
        label_id = self._id_by_name.get(provider_label)
        if not label_id:
            self.ensure_labels([provider_label])
            label_id = self._id_by_name[provider_label]
        remove = [
            lid
            for name, lid in self._id_by_name.items()
            if is_priority_name(name, self.label_prefix) and lid != label_id
        ]
        if self.placement == "move":
            remove.append("INBOX")
        self._svc().users().messages().modify(
            userId="me",
            id=uid,
            body={"addLabelIds": [label_id], "removeLabelIds": remove},
        ).execute()

    def ensure_labels(self, labels: Sequence[LabelMap | str]) -> None:
        self._load_labels()
        for name in label_names(labels):
            if name in self._id_by_name:
                continue
            created = (
                self._svc()
                .users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
                .execute()
            )
            self._id_by_name[name] = str(created["id"])
            self._name_by_id[str(created["id"])] = name

    def fetch_sent(self, since: datetime) -> list[EmailRecord]:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        day = since.astimezone(timezone.utc).strftime("%Y/%m/%d")
        recs = []
        for uid in self._list_ids(f"in:sent after:{day}"):
            msg = self._get(uid, metadata=True)
            if msg:
                recs.append(self._to_record(msg))
        return recs
