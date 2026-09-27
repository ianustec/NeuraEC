from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from neuraec.adapters.fake import FakeAdapter
from neuraec.adapters.imap import (
    flags_seen_answered,
    header_first,
    message_to_record,
    parse_references,
    snippet_from_parts,
)
from neuraec.bench.synthetic import make_email, mailbox
from neuraec.classifier import Classifier
from neuraec.cli import main
from neuraec.learn import SOURCE_WEIGHT
from neuraec.nightly import compute_stats, init_mailbox, nightly, predict_unseen
from neuraec.records import EmailRecord
from neuraec.registry import Registry
from neuraec.state import UserState


def _clf(tmp_path: Path, encoder, user_id: str = "u") -> Classifier:
    mb = mailbox(user_id)
    state = UserState(
        tmp_path / user_id,
        user_id=user_id,
        N=mb.N,
        order=mb.order,
        encoder_name=encoder.name,
    )
    registry = Registry(tmp_path / user_id / "pred.sqlite")
    return Classifier(mb, state, encoder, registry)


def test_asc_order_puts_most_urgent_in_the_last_folder():
    from neuraec.records import LabelMap, MailboxConfig

    mb = MailboxConfig(
        mailbox_id="mb",
        user_id="me",
        own_addresses=["a@b.it"],
        N=4,
        order="asc",
        labels=[
            LabelMap(rank=i, provider_label=f"INBOX.BeC-P{i + 1}", text=f"Priority {i + 1}")
            for i in range(4)
        ],
    )
    assert mb.label_for_rank(0) == "INBOX.BeC-P4"
    assert mb.label_for_rank(3) == "INBOX.BeC-P1"
    assert mb.rank_for_label("INBOX.BeC-P1") == 3
    assert mb.rank_for_label("INBOX.BeC-P4") == 0
    desc = mailbox("u", N=4, order="desc")
    assert desc.label_for_rank(0) == "P0"
    assert desc.rank_for_label("P3") == 3


def test_predict_unseen_moves_opens_and_leaves_state(tmp_path, encoder):
    clf = _clf(tmp_path, encoder)
    rec = make_email("u1", "invoice", user_id="u")
    rec.folder = "INBOX"
    rec.is_seen = False
    adapter = FakeAdapter([rec])

    mem_before = clf.state.size
    senders_before = dict(clf.state.senders)
    replied_before = dict(clf.state.replied_to)
    mass_before = clf.state.rank_mass.mass.copy()

    out = predict_unseen(clf.mailbox, adapter, clf)
    assert len(out) == 1
    pred = out[0][1]
    label = clf.mailbox.label_for_rank(pred.rank)
    assert rec.folder == label
    assert adapter.write_calls == [("u1", label)]

    row = clf.registry.get("u1")
    assert row is not None
    assert row["status"] == "open"
    assert row["written_label"] == label
    assert row["pred_rank"] == pred.rank

    assert clf.state.size == mem_before
    assert clf.state.senders == senders_before
    assert clf.state.replied_to == replied_before
    assert (clf.state.rank_mass.mass == mass_before).all()


def test_observe_moves_learns_moves_now_and_leaves_the_rest_to_the_night(tmp_path, encoder):
    """A move does not wait 24 hours. Read-and-left, deleted, and still-unread do."""
    from neuraec.nightly import observe_moves

    clf = _clf(tmp_path, encoder)
    t0 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    moved = make_email("m1", "invoice", user_id="u", minutes=0)
    read = make_email("k1", "other", user_id="u", minutes=1)
    gone = make_email("d1", "other", user_id="u", minutes=2, subject_extra="archivio")
    answered = make_email("r1", "newsletter", user_id="u", minutes=3)
    fresh = make_email("n1", "other", user_id="u", minutes=4, subject_extra="attesa")
    for rec in (moved, read, gone, answered, fresh):
        rec.folder = "INBOX"
        rec.is_seen = False
        rec.is_answered = False
    adapter = FakeAdapter([moved, read, gone, answered, fresh])
    predict_unseen(clf.mailbox, adapter, clf, now=t0)
    clf.state.rank_mass.add(0, 8.0, t0, is_correction=True)

    pred_m = clf.registry.get("m1")["pred_rank"]
    other_rank = (pred_m + 1) % clf.mailbox.N
    moved.folder = clf.mailbox.label_for_rank(other_rank)
    read.is_seen = True  # letta, lasciata dov'era
    gone.folder = "Archive"  # outside the priority folders
    answered.is_answered = True

    five_minutes = t0 + timedelta(minutes=5)
    n_corr_before = clf.state.n_corr
    report = observe_moves(clf.mailbox, adapter, clf, now=five_minutes)

    assert report.n_corr == 1 and report.n_replied == 1
    assert report.n_conf == 0 and report.n_deleted == 0
    assert clf.state.n_corr == n_corr_before + 1
    row_m = clf.registry.get("m1")
    assert row_m["status"] == "frozen" and row_m["user_action"] == "moved"
    assert row_m["final_rank"] == other_rank
    assert clf.registry.get("r1")["user_action"] == "replied"
    # these three stay open: the night decides, after 24 hours
    for uid in ("k1", "d1", "n1"):
        assert clf.registry.get(uid)["status"] == "open"

    # secondo giro: niente da rifare
    again = observe_moves(clf.mailbox, adapter, clf, now=five_minutes + timedelta(minutes=5))
    assert again.n_observed == 0
    assert clf.state.n_corr == n_corr_before + 1

    # the night then closes the rest without touching the move already learned
    night = nightly(clf.mailbox, adapter, clf, now=t0 + timedelta(hours=25))
    assert night.n_corr == 0 and night.n_conf == 1 and night.n_deleted == 1 and night.n_unread == 1
    assert clf.state.n_corr == n_corr_before + 1


def test_observe_moves_skips_when_provider_cannot_probe(tmp_path, encoder):
    from neuraec.adapters.base import Adapter
    from neuraec.nightly import observe_moves

    class Blind(FakeAdapter):
        def probe(self, items, labels):
            return Adapter.probe(self, items, labels)

    clf = _clf(tmp_path, encoder)
    rec = make_email("u1", "invoice", user_id="u")
    rec.folder = "INBOX"
    adapter = Blind([rec])
    predict_unseen(clf.mailbox, adapter, clf)
    rec.folder = clf.mailbox.label_for_rank((clf.registry.get("u1")["pred_rank"] + 1) % clf.mailbox.N)
    report = observe_moves(clf.mailbox, adapter, clf)
    assert report.n_observed == 0
    assert report.kpi.get("skipped") == "provider"
    assert clf.registry.get("u1")["status"] == "open"


def test_nightly_five_observations_and_idempotent(tmp_path, encoder):
    clf = _clf(tmp_path, encoder)
    t0 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    kinds = {
        "corr": make_email("c1", "invoice", user_id="u", minutes=0),
        "replied": make_email("r1", "newsletter", user_id="u", minutes=1),
        "conf": make_email("k1", "other", user_id="u", minutes=2),
        "deleted": make_email("d1", "other", user_id="u", minutes=3, subject_extra="archivio"),
        "unread": make_email("n1", "other", user_id="u", minutes=4, subject_extra="attesa"),
    }
    for rec in kinds.values():
        rec.folder = "INBOX"
        rec.is_seen = False
        rec.is_answered = False
    adapter = FakeAdapter(list(kinds.values()))
    predict_unseen(clf.mailbox, adapter, clf, now=t0)
    for rec in kinds.values():
        assert clf.registry.get(rec.uid) is not None

    clf.state.rank_mass.add(0, 8.0, t0, is_correction=True)

    preds = {rec.uid: clf.registry.get(rec.uid)["pred_rank"] for rec in kinds.values()}
    written = {rec.uid: clf.registry.get(rec.uid)["written_label"] for rec in kinds.values()}

    other_rank = (preds["c1"] + 1) % clf.mailbox.N
    kinds["corr"].folder = clf.mailbox.label_for_rank(other_rank)
    kinds["replied"].is_answered = True
    kinds["replied"].folder = written["r1"]
    kinds["conf"].is_seen = True
    kinds["conf"].folder = written["k1"]
    kinds["deleted"].folder = "Archive"
    kinds["unread"].folder = written["n1"]
    kinds["unread"].is_seen = False

    later = t0 + timedelta(hours=25)
    report = nightly(clf.mailbox, adapter, clf, now=later)

    assert report.n_observed == 5
    assert report.n_corr == 1
    assert report.n_replied == 1
    assert report.n_conf == 1
    assert report.n_deleted == 1
    assert report.n_unread == 1

    row_c = clf.registry.get("c1")
    assert row_c["status"] == "frozen" and row_c["user_action"] == "moved"
    assert row_c["final_rank"] == other_rank
    item_c = clf.state.get("c1")
    assert item_c["source"] == "corr" and item_c["weight"] == SOURCE_WEIGHT["corr"]

    row_r = clf.registry.get("r1")
    assert row_r["status"] == "resolved" and row_r["user_action"] == "replied"
    expected_replied = min(preds["r1"], 0)
    assert row_r["final_rank"] == expected_replied
    item_r = clf.state.get("r1")
    assert item_r["source"] == "replied" and item_r["weight"] == SOURCE_WEIGHT["replied"]
    assert item_r["rank"] == expected_replied

    row_k = clf.registry.get("k1")
    assert row_k["status"] == "resolved" and row_k["user_action"] == "read_unmoved"
    assert row_k["final_rank"] == preds["k1"]
    item_k = clf.state.get("k1")
    assert item_k["source"] == "conf" and item_k["weight"] == SOURCE_WEIGHT["conf"]

    row_d = clf.registry.get("d1")
    assert row_d["status"] == "resolved" and row_d["user_action"] == "deleted"
    assert clf.state.get("d1") is None

    row_n = clf.registry.get("n1")
    assert row_n["status"] == "open" and row_n.get("user_action") is None
    assert clf.state.get("n1") is None

    resolved_at = {uid: clf.registry.get(uid)["resolved_at"] for uid in ("c1", "r1", "k1", "d1")}

    report2 = nightly(clf.mailbox, adapter, clf, now=later + timedelta(hours=1))
    assert report2.n_corr == 0
    assert report2.n_replied == 0
    assert report2.n_conf == 0
    assert report2.n_deleted == 0
    assert report2.n_unread == 1
    for uid in ("c1", "r1", "k1", "d1"):
        again = clf.registry.get(uid)
        assert again["resolved_at"] == resolved_at[uid]
        assert again["user_action"] == clf.registry.get(uid)["user_action"]


def test_frozen_row_not_rewritten_by_predict(tmp_path, encoder):
    clf = _clf(tmp_path, encoder)
    t0 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    rec = make_email("f1", "invoice", user_id="u")
    rec.folder = "INBOX"
    adapter = FakeAdapter([rec])
    predict_unseen(clf.mailbox, adapter, clf, now=t0)
    pred_rank = clf.registry.get("f1")["pred_rank"]
    other = (pred_rank + 1) % clf.mailbox.N
    rec.folder = clf.mailbox.label_for_rank(other)
    nightly(clf.mailbox, adapter, clf, now=t0 + timedelta(hours=25))
    row = clf.registry.get("f1")
    assert row["status"] == "frozen" and row["final_rank"] == other

    writes_before = list(adapter.write_calls)
    rec.folder = "INBOX"
    rec.is_seen = False
    out = predict_unseen(clf.mailbox, adapter, clf, now=t0 + timedelta(hours=26))
    assert out == []
    assert adapter.write_calls == writes_before
    row2 = clf.registry.get("f1")
    assert row2["status"] == "frozen" and row2["final_rank"] == other
    assert row2["written_at"] == row["written_at"]


def test_stats_corrections_per_100(tmp_path, encoder):
    clf = _clf(tmp_path, encoder)
    t0 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    recs = [
        make_email("s1", "invoice", user_id="u", minutes=0),
        make_email("s2", "newsletter", user_id="u", minutes=1),
        make_email("s3", "other", user_id="u", minutes=2),
        make_email("s4", "other", user_id="u", minutes=3, subject_extra="x"),
    ]
    for rec in recs:
        rec.folder = "INBOX"
    adapter = FakeAdapter(recs)
    predict_unseen(clf.mailbox, adapter, clf, now=t0)

    r1 = (clf.registry.get("s1")["pred_rank"] + 1) % clf.mailbox.N
    recs[0].folder = clf.mailbox.label_for_rank(r1)
    recs[1].is_answered = True
    recs[2].is_seen = True
    recs[3].is_seen = False
    nightly(clf.mailbox, adapter, clf, now=t0 + timedelta(hours=25))

    stats = compute_stats(clf.registry)
    assert stats["n_corr"] == 1
    assert stats["n_conf"] == 1
    assert stats["n_replied"] == 1
    assert stats["n_labeled"] == 3
    assert stats["n_open"] == 1
    assert stats["corrections_per_100"] == 33.33


def test_cli_stats(tmp_path, encoder, capsys):
    user_id = "me"
    mb = mailbox(user_id)
    data = tmp_path / "data"
    user_root = data / "users" / user_id
    box_root = data / "mailboxes" / mb.mailbox_id
    state = UserState(user_root, user_id=user_id, N=mb.N, encoder_name=encoder.name)
    registry = Registry(box_root / "pred.sqlite")
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    registry.insert_prediction(
        uid="a",
        message_id="m-a",
        thread_key="t",
        from_addr="x@y.it",
        received_at=now,
        e_hash="h",
        pred_rank=1,
        pred_u=0.4,
        pred_conf=0.2,
        stage="prior",
        model_version="t",
        written_label="P1",
        written_at=now,
    )
    registry.insert_prediction(
        uid="b",
        message_id="m-b",
        thread_key="t",
        from_addr="x@y.it",
        received_at=now,
        e_hash="h",
        pred_rank=2,
        pred_u=0.2,
        pred_conf=0.2,
        stage="prior",
        model_version="t",
        written_label="P2",
        written_at=now,
    )
    registry.resolve("a", user_action="moved", final_rank=0, status="frozen", now=now)
    registry.resolve("b", user_action="read_unmoved", final_rank=2, status="resolved", now=now)
    state.save()

    cfg = tmp_path / "mailbox.json"
    cfg.write_text(
        json.dumps(
            {
                "mailbox_id": mb.mailbox_id,
                "user_id": user_id,
                "own_addresses": mb.own_addresses,
                "N": mb.N,
                "order": mb.order,
                "labels": [
                    {"rank": lab.rank, "provider_label": lab.provider_label, "text": lab.text}
                    for lab in mb.labels
                ],
                "host": "imap.example.test",
            }
        ),
        encoding="utf-8",
    )
    assert main(["stats", "--config", str(cfg), "--data", str(data), "--encoder", "fake", "--adapter", "fake"]) == 0
    printed = capsys.readouterr().out
    assert "corrections: 1" in printed
    assert "confirmations: 1" in printed
    assert "corrections/100: 50.0" in printed


def test_init_reads_sent(tmp_path, encoder):
    clf = _clf(tmp_path, encoder)
    sent = EmailRecord(
        uid="out1",
        message_id="<out1@test>",
        received_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
        from_addr="u@azienda.it",
        to_addrs=["cliente@esterno.it", "u@azienda.it"],
        cc_addrs=["altro@esterno.it"],
        subject="Re: ordine",
        folder="Sent",
    )
    adapter = FakeAdapter(sent=[sent])
    info = init_mailbox(clf.mailbox, adapter, clf, now=datetime(2024, 6, 1, tzinfo=timezone.utc))
    assert "P0" in adapter.folders
    assert clf.state.replied_to["cliente@esterno.it"] == 1
    assert clf.state.replied_to["altro@esterno.it"] == 1
    assert "u@azienda.it" not in clf.state.replied_to
    assert info["n_recipients"] == 2


def test_imap_message_to_record_extracts_dagger_fields():
    class _Addr:
        def __init__(self, email, name=""):
            self.email = email
            self.name = name

    class _Att:
        content_disposition = "attachment"

    class _Msg:
        uid = "42"
        subject = "Fattura"
        from_ = "mittente@fornitore.it"
        from_values = _Addr("mittente@fornitore.it", "Ufficio")
        to = ("me@azienda.it",)
        to_values = (_Addr("me@azienda.it"),)
        cc = ()
        cc_values = ()
        date = datetime(2024, 6, 1, 8, 0, tzinfo=timezone.utc)
        text = ""
        html = "<p>corpo&nbsp;html</p>"
        headers = {
            "message-id": ("<m42@x>",),
            "in-reply-to": ("<parent@x>",),
            "references": ("<root@x> <parent@x>",),
            "list-unsubscribe": ("<mailto:unsub@x>",),
            "list-id": ("list.example",),
            "precedence": ("bulk",),
            "auto-submitted": ("auto-generated",),
        }
        flags = ("\\Seen", "\\Answered")
        attachments = [_Att()]

    rec = message_to_record(_Msg(), "INBOX")
    assert rec.uid == "42"
    assert rec.message_id == "<m42@x>"
    assert rec.in_reply_to == "<parent@x>"
    assert rec.references == ["<root@x>", "<parent@x>"]
    assert rec.from_addr == "mittente@fornitore.it"
    assert rec.from_name == "Ufficio"
    assert rec.to_addrs == ["me@azienda.it"]
    assert rec.list_unsubscribe is True
    assert rec.list_id is True
    assert rec.precedence_bulk is True
    assert rec.auto_submitted is True
    assert rec.is_seen is True
    assert rec.is_answered is True
    assert rec.has_attachment is True
    assert rec.folder == "INBOX"
    assert "corpo" in rec.snippet
    assert "<p>" not in rec.snippet

    assert header_first(_Msg.headers, "Message-ID") == "<m42@x>"
    assert parse_references("<a> <b>") == ["<a>", "<b>"]
    assert flags_seen_answered(("\\Seen",)) == (True, False)
    assert snippet_from_parts("plain " * 300, "<b>x</b>").startswith("plain")
    assert len(snippet_from_parts("plain " * 300, "")) <= 1000
