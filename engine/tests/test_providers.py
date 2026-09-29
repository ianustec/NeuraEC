from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pytest

from neuraec.adapters.gmail import GmailAdapter
from neuraec.adapters.graph import GraphAdapter
from neuraec.adapters.parse import (
    canonical_message_id,
    gmail_message_to_record,
    graph_message_to_record,
    mark_answered,
)
from neuraec.bench.synthetic import make_email
from neuraec.cli import main
from neuraec.config import load_mailbox_config
from neuraec.learn import SOURCE_WEIGHT
from neuraec.nightly import apply_manual, predict_unseen
from neuraec.records import EmailRecord
from neuraec.serve import make_server


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _gmail_message() -> dict:
    return {
        "id": "18abc",
        "threadId": "thr1",
        "labelIds": ["INBOX", "UNREAD", "Label_9"],
        "snippet": "anteprima",
        "internalDate": "1717228800000",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Ufficio <mittente@fornitore.it>"},
                {"name": "To", "value": "me@azienda.it"},
                {"name": "Cc", "value": "altro@azienda.it"},
                {"name": "Subject", "value": "Fattura"},
                {"name": "Message-ID", "value": "<m42@x>"},
                {"name": "In-Reply-To", "value": "<parent@x>"},
                {"name": "References", "value": "<root@x> <parent@x>"},
                {"name": "List-Unsubscribe", "value": "<mailto:unsub@x>"},
                {"name": "List-Id", "value": "list.example"},
                {"name": "Precedence", "value": "bulk"},
                {"name": "Auto-Submitted", "value": "auto-generated"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("corpo plain della fattura")}},
                {"mimeType": "application/pdf", "filename": "f.pdf", "body": {"attachmentId": "att1"}},
            ],
        },
    }


def _gmail_sent() -> dict:
    msg = {
        "id": "sent1",
        "threadId": "thr1",
        "labelIds": ["SENT"],
        "internalDate": "1717232400000",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "me@azienda.it"},
                {"name": "To", "value": "Cliente <cliente@esterno.it>"},
                {"name": "Subject", "value": "Re: Fattura"},
                {"name": "Message-ID", "value": "<sent1@x>"},
                {"name": "In-Reply-To", "value": "<m42@x>"},
            ],
        },
    }
    return msg


def test_gmail_message_to_record_and_answered():
    rec = gmail_message_to_record(
        _gmail_message(),
        name_by_id={"Label_9": "BeC-P2", "INBOX": "INBOX"},
        priority_names={"BeC-P1", "BeC-P2"},
    )
    assert rec.uid == "18abc"
    assert rec.thread_id == "thr1"
    assert rec.message_id == "<m42@x>"
    assert rec.in_reply_to == "<parent@x>"
    assert rec.references == ["<root@x>", "<parent@x>"]
    assert rec.from_addr == "mittente@fornitore.it"
    assert rec.from_name == "Ufficio"
    assert rec.to_addrs == ["me@azienda.it"]
    assert rec.cc_addrs == ["altro@azienda.it"]
    assert rec.subject == "Fattura"
    assert "corpo plain" in rec.snippet
    assert "anteprima" in rec.snippet
    assert rec.has_attachment is True
    assert rec.list_unsubscribe and rec.list_id and rec.precedence_bulk and rec.auto_submitted
    assert rec.is_seen is False
    assert rec.is_answered is False
    assert rec.folder == "BeC-P2"
    assert rec.received_at == datetime(2024, 6, 1, 8, 0, tzinfo=timezone.utc)

    sent = gmail_message_to_record(_gmail_sent(), name_by_id={"SENT": "SENT"})
    assert sent.folder == "SENT"
    mark_answered([rec], [sent])
    assert rec.is_answered is True
    assert canonical_message_id("<M42@x>") == "m42@x"


def test_graph_message_to_record_and_answered():
    msg = {
        "id": "AAMk1",
        "conversationId": "AAQk1",
        "internetMessageId": "<m42@x>",
        "subject": "Fattura",
        "bodyPreview": "anteprima",
        "receivedDateTime": "2024-06-01T08:00:00Z",
        "isRead": False,
        "hasAttachments": True,
        "parentFolderId": "inbox-id",
        "categories": ["BeC-P3", "Progetto"],
        "from": {"emailAddress": {"name": "Ufficio", "address": "Mittente@fornitore.it"}},
        "toRecipients": [{"emailAddress": {"address": "me@azienda.it"}}],
        "ccRecipients": [{"emailAddress": {"address": "altro@azienda.it", "name": "Altro"}}],
        "body": {"contentType": "html", "content": "<p>corpo&nbsp;html</p>"},
        "internetMessageHeaders": [
            {"name": "In-Reply-To", "value": "<parent@x>"},
            {"name": "References", "value": "<root@x> <parent@x>"},
            {"name": "List-Unsubscribe", "value": "<mailto:unsub@x>"},
            {"name": "List-Id", "value": "list.example"},
            {"name": "Precedence", "value": "list"},
            {"name": "Auto-Submitted", "value": "no"},
        ],
    }
    rec = graph_message_to_record(msg, folder_name="inbox", priority_names={"BeC-P3"})
    assert rec.uid == "AAMk1"
    assert rec.thread_id == "AAQk1"
    assert rec.from_addr == "mittente@fornitore.it"
    assert rec.from_name == "Ufficio"
    assert rec.to_addrs == ["me@azienda.it"]
    assert rec.folder == "BeC-P3"
    assert rec.is_seen is False
    assert rec.auto_submitted is False
    assert rec.precedence_bulk is True
    assert rec.list_unsubscribe is True
    assert "<p>" not in rec.snippet and "corpo" in rec.snippet
    assert rec.received_at == datetime(2024, 6, 1, 8, 0, tzinfo=timezone.utc)

    sent = EmailRecord(
        uid="out",
        message_id="<sent@x>",
        in_reply_to="<m42@x>",
        received_at=datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc),
        to_addrs=["cliente@esterno.it"],
    )
    mark_answered([rec], [sent])
    assert rec.is_answered is True


class _Req:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class _FakeGmail:
    def __init__(self, messages: dict, labels: list[dict]):
        self.by_id = messages
        self.label_rows = labels
        self.modifies: list[tuple[str, dict]] = []

    def users(self):
        return self

    def labels(self):
        return _FakeLabels(self)

    def messages(self):
        return _FakeMessages(self)


class _FakeLabels:
    def __init__(self, root: _FakeGmail):
        self.root = root

    def list(self, userId="me"):
        return _Req(lambda: {"labels": self.root.label_rows})

    def create(self, userId="me", body=None):
        def run():
            lid = "L" + str(len(self.root.label_rows) + 1)
            self.root.label_rows.append({"id": lid, "name": body["name"]})
            return {"id": lid, "name": body["name"]}

        return _Req(run)


class _FakeMessages:
    def __init__(self, root: _FakeGmail):
        self.root = root

    def list(self, userId="me", q="", maxResults=100, pageToken=None):
        def run():
            ids = []
            for mid, msg in self.root.by_id.items():
                labels = set(msg.get("labelIds") or [])
                if "in:inbox" in q and "INBOX" not in labels:
                    continue
                if "is:unread" in q and "UNREAD" not in labels:
                    continue
                if "in:sent" in q and "SENT" not in labels:
                    continue
                if "rfc822msgid:" in q:
                    token = canonical_message_id(q.split("rfc822msgid:", 1)[1].split()[0])
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in (msg.get("payload") or {}).get("headers") or []
                    }
                    if canonical_message_id(headers.get("message-id")) != token:
                        continue
                ids.append({"id": mid})
            return {"messages": ids}

        return _Req(run)

    def get(self, userId="me", id="", format="full", metadataHeaders=None):
        def run():
            if id not in self.root.by_id:
                raise RuntimeError("404 not found")
            return self.root.by_id[id]

        return _Req(run)

    def modify(self, userId="me", id="", body=None):
        def run():
            self.root.modifies.append((id, body))
            return {"id": id}

        return _Req(run)


def test_gmail_adapter_unseen_labels_and_modify():
    box = _FakeGmail(
        {"18abc": _gmail_message(), "sent1": _gmail_sent()},
        [
            {"id": "INBOX", "name": "INBOX"},
            {"id": "UNREAD", "name": "UNREAD"},
            {"id": "SENT", "name": "SENT"},
            {"id": "Label_9", "name": "BeC-P2"},
        ],
    )
    adapter = GmailAdapter(service=box, label_prefix="BeC-P")
    unseen = adapter.fetch_unseen()
    assert len(unseen) == 1
    assert unseen[0].uid == "18abc"
    assert unseen[0].is_answered is True
    assert unseen[0].folder == "BeC-P2"

    adapter.ensure_labels(["BeC-P1"])
    adapter.write_label("18abc", "BeC-P1")
    uid, body = box.modifies[-1]
    assert uid == "18abc"
    assert body["addLabelIds"] == ["L5"]
    assert "Label_9" in body["removeLabelIds"]

    found = adapter.fetch_by_message_id("m42@x")
    assert found is not None and found.uid == "18abc"


class _GraphBox:
    def __init__(self, inbox: list[dict], sent: list[dict]):
        self.inbox = inbox
        self.sent = sent
        self.categories: list[str] = []
        self.patches: list[dict] = []

    def __call__(self, method, url, json_body=None, params=None):
        params = params or {}
        if method == "GET" and url.rstrip("/").endswith("/mailFolders"):
            return {"value": [{"id": "inbox-id", "displayName": "Posta in arrivo"}]}
        if "sentitems/messages" in url:
            return {"value": self.sent}
        if "inbox/messages" in url:
            return {"value": self.inbox}
        if url.rstrip("/").endswith("/outlook/masterCategories") and method == "GET":
            return {"value": [{"displayName": name} for name in self.categories]}
        if url.rstrip("/").endswith("/outlook/masterCategories") and method == "POST":
            self.categories.append(json_body["displayName"])
            return json_body
        if method == "GET" and params.get("$select") == "categories":
            return {"id": "AAMk1", "categories": ["BeC-P1", "Progetto"]}
        if method == "PATCH":
            self.patches.append(json_body)
            return json_body
        if method == "GET" and "internetMessageId" in str(params.get("$filter") or ""):
            return {"value": self.inbox}
        if method == "GET" and "/messages/" in url:
            return self.inbox[0]
        return {"value": []}


def _graph_inbox() -> dict:
    return {
        "id": "AAMk1",
        "conversationId": "AAQk1",
        "internetMessageId": "<m42@x>",
        "subject": "Fattura",
        "bodyPreview": "anteprima",
        "receivedDateTime": "2024-06-01T08:00:00Z",
        "isRead": False,
        "hasAttachments": False,
        "parentFolderId": "inbox-id",
        "categories": [],
        "from": {"emailAddress": {"name": "Ufficio", "address": "mittente@fornitore.it"}},
        "toRecipients": [{"emailAddress": {"address": "me@azienda.it"}}],
        "ccRecipients": [],
        "body": {"contentType": "text", "content": "corpo"},
        "internetMessageHeaders": [],
    }


def _graph_sent() -> dict:
    return {
        "id": "AAMkSent",
        "conversationId": "AAQk1",
        "internetMessageId": "<sent@x>",
        "subject": "Re: Fattura",
        "receivedDateTime": "2024-06-01T09:00:00Z",
        "isRead": True,
        "hasAttachments": False,
        "parentFolderId": "sent-id",
        "categories": [],
        "from": {"emailAddress": {"address": "me@azienda.it"}},
        "toRecipients": [{"emailAddress": {"address": "cliente@esterno.it"}}],
        "ccRecipients": [],
        "body": {"contentType": "text", "content": "ok"},
        "internetMessageHeaders": [{"name": "In-Reply-To", "value": "<m42@x>"}],
    }


def test_graph_adapter_unseen_category_and_answered():
    box = _GraphBox([_graph_inbox()], [_graph_sent()])
    adapter = GraphAdapter(transport=box, label_prefix="BeC-P")
    unseen = adapter.fetch_unseen()
    assert len(unseen) == 1
    assert unseen[0].is_answered is True
    assert unseen[0].folder == "inbox"
    assert unseen[0].to_addrs == ["me@azienda.it"]

    adapter.ensure_labels(["BeC-P1", "BeC-P2"])
    assert box.categories == ["BeC-P1", "BeC-P2"]
    adapter.write_label("AAMk1", "BeC-P2")
    assert box.patches[-1]["categories"] == ["Progetto", "BeC-P2"]

    found = adapter.fetch_by_message_id("<m42@x>")
    assert found is not None and found.uid == "AAMk1"


def test_gmail_move_mode_also_leaves_the_inbox():
    box = _FakeGmail(
        {"18abc": _gmail_message()},
        [
            {"id": "INBOX", "name": "INBOX"},
            {"id": "UNREAD", "name": "UNREAD"},
            {"id": "Label_9", "name": "BeC-P2"},
        ],
    )
    labelled = GmailAdapter(service=box, label_prefix="BeC-P")
    assert labelled.supports_labels() is True
    labelled.write_label("18abc", "BeC-P2")
    assert "INBOX" not in box.modifies[-1][1]["removeLabelIds"]

    moved = GmailAdapter(service=box, label_prefix="BeC-P", placement="move")
    moved.write_label("18abc", "BeC-P2")
    assert "INBOX" in box.modifies[-1][1]["removeLabelIds"]
    assert box.modifies[-1][1]["addLabelIds"] == ["Label_9"]


class _GraphFolderBox(_GraphBox):
    """Like _GraphBox, but with real folders: it tracks them and records moves."""

    def __init__(self, inbox, sent):
        super().__init__(inbox, sent)
        self.folders: list[dict] = [{"id": "inbox-id", "displayName": "Posta in arrivo"}]
        self.moves: list[tuple[str, str]] = []

    def __call__(self, method, url, json_body=None, params=None):
        params = params or {}
        if method == "GET" and url.rstrip("/").endswith("/mailFolders"):
            return {"value": self.folders}
        if method == "POST" and url.rstrip("/").endswith("/mailFolders"):
            fid = f"f{len(self.folders)}"
            self.folders.append({"id": fid, "displayName": json_body["displayName"]})
            return {"id": fid, "displayName": json_body["displayName"]}
        if method == "POST" and url.endswith("/move"):
            self.moves.append((url.split("/messages/")[1].split("/")[0], json_body["destinationId"]))
            return {"id": "AAMk1-moved"}
        if method == "GET" and "/mailFolders/" in url and url.endswith("/messages"):
            fid = url.split("/mailFolders/")[1].split("/")[0]
            if any(dest == fid for _uid, dest in self.moves):
                return {"value": [{"id": "AAMk1-moved", "internetMessageId": "<m42@x>"}]}
            return {"value": []}
        return super().__call__(method, url, json_body=json_body, params=params)


def test_graph_move_mode_uses_real_folders_and_probes_by_message_id():
    box = _GraphFolderBox([_graph_inbox()], [_graph_sent()])
    adapter = GraphAdapter(transport=box, label_prefix="BeC-P", placement="move")
    adapter.ensure_labels(["BeC-P1", "BeC-P2"])
    names = [f["displayName"] for f in box.folders]
    assert "BeC-P1" in names and "BeC-P2" in names
    assert box.categories == []  # no categories in move mode

    adapter.write_label("AAMk1", "BeC-P2")
    assert box.moves == [("AAMk1", "f2")]
    assert box.patches == []

    # fast path: mail written to BeC-P1 is now in folder BeC-P2
    found = adapter.probe([("AAMk1", "<m42@x>", "BeC-P1")], ["BeC-P1", "BeC-P2"])
    assert found is not None and "AAMk1" in found
    assert found["AAMk1"].folder == "BeC-P2"
    # and if it is still where it was written, it is not reported
    assert adapter.probe([("AAMk1", "<m42@x>", "BeC-P2")], ["BeC-P1", "BeC-P2"]) == {}


def test_placement_defaults_follow_the_provider():
    from neuraec.records import MailboxConfig

    imap = MailboxConfig(mailbox_id="a", user_id="a", own_addresses=["a@b.it"], N=3, provider="imap")
    gmail = MailboxConfig(mailbox_id="b", user_id="b", own_addresses=["b@b.it"], N=3, provider="gmail")
    forced = MailboxConfig(
        mailbox_id="c", user_id="c", own_addresses=["c@b.it"], N=3, provider="imap", placement="label"
    )
    assert imap.placement == "move"
    assert gmail.placement == "label"
    assert forced.placement == "move"  # IMAP has folders only
    chosen = MailboxConfig(
        mailbox_id="d", user_id="d", own_addresses=["d@b.it"], N=3, provider="graph", placement="move"
    )
    assert chosen.placement == "move"


def test_predict_unseen_skips_mail_already_labelled_in_inbox(tmp_path, encoder):
    """With labels the mail stays in the inbox: the next cycle must not predict or notify it again."""
    from neuraec.adapters.fake import FakeAdapter
    from neuraec.bench.synthetic import mailbox, make_email
    from neuraec.classifier import Classifier
    from neuraec.nightly import predict_unseen
    from neuraec.registry import Registry
    from neuraec.state import UserState

    mb = mailbox("u")
    state = UserState(tmp_path / "u", user_id="u", N=mb.N, order=mb.order, encoder_name=encoder.name)
    clf = Classifier(mb, state, encoder, Registry(tmp_path / "u" / "pred.sqlite"))
    rec = make_email("g1", "invoice", user_id="u")
    rec.folder = "INBOX"
    rec.is_seen = False
    adapter = FakeAdapter([rec])
    first = predict_unseen(mb, adapter, clf)
    assert len(first) == 1
    written_at = clf.registry.get("g1")["written_at"]

    # simulate Gmail: labelled mail is still "unread in the inbox"
    rec.folder = "INBOX"
    again = predict_unseen(mb, adapter, clf)
    assert again == []
    assert clf.registry.get("g1")["written_at"] == written_at
    assert len(adapter.write_calls) == 1

    # and mail that already carries a priority label, even without a row, is left alone
    other = make_email("g2", "invoice", user_id="u")
    other.folder = mb.label_for_rank(0)
    other.is_seen = False
    box = FakeAdapter([other])
    box.fetch_unseen = lambda **_kwargs: [other]  # type: ignore[method-assign]
    assert predict_unseen(mb, box, clf) == []


def test_apply_manual_freezes_and_writes_label(tmp_path, encoder):
    from neuraec.classifier import Classifier
    from neuraec.encoder import FakeEncoder
    from neuraec.registry import Registry
    from neuraec.state import UserState
    from neuraec.adapters.fake import FakeAdapter
    from neuraec.bench.synthetic import mailbox

    assert isinstance(encoder, FakeEncoder)
    mb = mailbox("u")
    state = UserState(tmp_path / "u", user_id="u", N=mb.N, encoder_name=encoder.name)
    clf = Classifier(mb, state, encoder, Registry(tmp_path / "u" / "pred.sqlite"))
    rec = make_email("man1", "invoice", user_id="u")
    rec.folder = "INBOX"
    adapter = FakeAdapter([rec])
    now = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    pred = predict_unseen(mb, adapter, clf, now=now)[0][1]
    other = (pred.rank + 1) % mb.N

    assert apply_manual(mb, adapter, clf, EmailRecord(uid="", message_id=rec.message_id), other, now=now)
    row = clf.registry.get("man1")
    assert row["status"] == "frozen"
    assert row["user_action"] == "manual"
    assert row["final_rank"] == other
    item = clf.state.get("man1")
    assert item["source"] == "manual"
    assert item["weight"] == SOURCE_WEIGHT["manual"]
    assert adapter.messages["man1"].folder == mb.label_for_rank(other)
    assert adapter.write_calls[-1] == ("man1", mb.label_for_rank(other))


def test_manual_http_and_config_labels(tmp_path, encoder):
    from neuraec.adapters.fake import FakeAdapter
    from neuraec.bench.synthetic import mailbox
    from neuraec.classifier import Classifier
    from neuraec.registry import Registry
    from neuraec.state import UserState

    mb = mailbox("u")
    state = UserState(tmp_path / "u", user_id="u", N=mb.N, encoder_name=encoder.name)
    clf = Classifier(mb, state, encoder, Registry(tmp_path / "u" / "pred.sqlite"))
    rec = make_email("http1", "other", user_id="u")
    rec.folder = "INBOX"
    adapter = FakeAdapter([rec])
    predict_unseen(mb, adapter, clf)

    httpd = make_server(mb, adapter, clf, "127.0.0.1", 0)
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    caught: dict = {}

    def client():
        try:
            caught["cfg"] = _get_json(base + "/config")
            caught["body"] = _post_json(base + "/manual", {"internetMessageId": rec.message_id, "rank": 1})
        except Exception as exc:
            caught["error"] = exc

    thread = threading.Thread(target=client)
    thread.start()
    httpd.handle_request()
    httpd.handle_request()
    thread.join(timeout=5)
    httpd.server_close()
    assert "error" not in caught, caught.get("error")
    assert caught["cfg"]["N"] == mb.N
    assert caught["cfg"]["labels"][0]["provider_label"] == mb.labels[0].provider_label
    assert caught["body"]["ok"] is True
    assert caught["body"]["user_action"] == "manual"
    row = clf.registry.get("http1")
    assert row["status"] == "frozen" and row["final_rank"] == 1


def test_gmail_provider_default_labels(tmp_path):
    path = tmp_path / "mailbox.json"
    path.write_text(
        json.dumps(
            {
                "mailbox_id": "g",
                "user_id": "me",
                "own_addresses": ["me@gmail.com"],
                "N": 3,
                "provider": "gmail",
            }
        ),
        encoding="utf-8",
    )
    cfg = load_mailbox_config(path)
    assert cfg.provider == "gmail"
    assert [lab.provider_label for lab in cfg.labels] == ["Neura-P1", "Neura-P2", "Neura-P3"]


def test_manual_cli_requires_id():
    with pytest.raises(SystemExit) as exc:
        main(["manual", "--rank", "0", "--adapter", "fake"])
    assert "message-id" in str(exc.value)


def _get_json(url: str) -> dict:
    last = None
    for _ in range(20):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.load(resp)
        except urllib.error.URLError as exc:
            last = exc
    raise AssertionError(last)


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        return json.load(resp)
