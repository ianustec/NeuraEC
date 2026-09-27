"""Stage 5: one encoder, several mailboxes, a lock per user."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from neuraec.adapters.fake import FakeAdapter
from neuraec.bench.synthetic import mailbox, opposite_policy_corpus
from neuraec.cli import main
from neuraec.cycle import CycleMailbox, build_classifier, imap_password, mailbox_paths, nightly_due, run_cycle
from neuraec.encoder import FakeEncoder
from neuraec.learn import observe
from neuraec.state import UserState


class OneEncoder(FakeEncoder):
    created = 0

    def __init__(self) -> None:
        OneEncoder.created += 1


def _policy_rank(kind: str, user: str, N: int = 4) -> int:
    if user == "a":
        return 0 if kind == "newsletter" else N - 1
    return N - 1 if kind == "newsletter" else 0


def _snapshot(clf, holdout, now):
    preds = [clf.predict(rec, write_registry=False, now=now) for rec, _ in holdout]
    return (
        [(p.rank, p.stage) for p in preds],
        np.array([p.u for p in preds]),
        clf.state.vectors.copy(),
    )


def _dump(path: Path, user_id: str) -> None:
    mb = mailbox(user_id)
    payload = {
        "mailbox_id": mb.mailbox_id,
        "user_id": mb.user_id,
        "own_addresses": mb.own_addresses,
        "N": mb.N,
        "order": mb.order,
        "provider": "imap",
        "host": "imap.example",
        "username": mb.own_addresses[0],
        "port": 993,
        "tls": "ssl",
        "labels": [
            {"rank": lab.rank, "provider_label": lab.provider_label, "text": lab.text} for lab in mb.labels
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_fifty_users_share_one_encoder_and_keep_predictions(tmp_path):
    OneEncoder.created = 0
    encoder = OneEncoder()
    data = tmp_path / "data"
    clf_a = build_classifier(mailbox("a"), encoder, data)
    clf_b = build_classifier(mailbox("b"), encoder, data)
    assert clf_a.encoder is encoder and clf_b.encoder is encoder

    for rec, kind in opposite_policy_corpus(20, user_id="a"):
        observe(clf_a, rec, rank=_policy_rank(kind, "a"), source="corr")
    for rec, kind in opposite_policy_corpus(20, user_id="b"):
        observe(clf_b, rec, rank=_policy_rank(kind, "b"), source="corr")

    hold_a = opposite_policy_corpus(50, user_id="hold-a")
    hold_b = opposite_policy_corpus(50, user_id="hold-b")
    now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    snap_a = _snapshot(clf_a, hold_a, now)
    snap_b = _snapshot(clf_b, hold_b, now)

    ids = ["a", "b"]
    for i in range(48):
        uid = f"u{i:02d}"
        ids.append(uid)
        clf = build_classifier(mailbox(uid), encoder, data)
        assert clf.encoder is encoder
        for rec, kind in opposite_policy_corpus(20, user_id=uid):
            observe(clf, rec, rank=_policy_rank(kind, "a"), source="corr", persist=False)
        clf.state.save()

    boxes = [CycleMailbox(mailbox(uid), FakeAdapter()) for uid in ids]
    run_cycle(boxes, encoder, data, run_nightly=False)
    assert OneEncoder.created == 1

    again_a = _snapshot(clf_a, hold_a, now)
    again_b = _snapshot(clf_b, hold_b, now)
    assert snap_a[0] == again_a[0]
    assert snap_b[0] == again_b[0]
    assert np.array_equal(snap_a[1], again_a[1])
    assert np.array_equal(snap_b[1], again_b[1])
    assert np.array_equal(snap_a[2], again_a[2])
    assert np.array_equal(snap_b[2], again_b[2])


def test_cycle_resolves_encoder_once_and_skips_missing_password(tmp_path, monkeypatch, capsys):
    primary = tmp_path / "mailbox.json"
    _dump(primary, "a")
    _dump(tmp_path / "mailboxes" / "b.json", "b")
    monkeypatch.setenv("NEURA_IMAP_PASSWORD", "secret")
    calls = {"n": 0}
    encoder = FakeEncoder()
    opened: list[str] = []

    def resolve(_choice):
        calls["n"] += 1
        return encoder

    def open_adapter(box, kind, *, password=None, config_path=None):
        opened.append(box.mailbox_id)
        assert password == "secret"
        return FakeAdapter()

    monkeypatch.setattr("neuraec.cli.resolve_encoder", resolve)
    monkeypatch.setattr("neuraec.cli._open_adapter", open_adapter)
    code = main(
        ["cycle", "--config", str(primary), "--data", str(tmp_path / "data"), "--encoder", "fake"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert calls["n"] == 1
    assert opened == ["mb-a"]
    assert "password missing" in out
    assert "secret" not in out

    monkeypatch.delenv("NEURA_IMAP_PASSWORD", raising=False)
    code = main(
        ["cycle", "--config", str(primary), "--data", str(tmp_path / "data"), "--encoder", "fake"]
    )
    assert code == 1
    assert calls["n"] == 1


def test_cycle_learns_a_move_at_the_next_pass_without_waiting_for_the_night(tmp_path):
    from neuraec.bench.synthetic import make_email

    mb = mailbox("a")
    rec = make_email("m1", "invoice", user_id="a")
    rec.folder = "INBOX"
    rec.is_seen = False
    adapter = FakeAdapter([rec])
    encoder = FakeEncoder()
    data = tmp_path / "data"
    t0 = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    said: list[str] = []

    run_cycle([CycleMailbox(mb, adapter)], encoder, data, now=t0, run_nightly=False, progress=said.append)
    clf = build_classifier(mb, encoder, data)
    row = clf.registry.get("m1")
    assert row["status"] == "open"
    other = (row["pred_rank"] + 1) % mb.N
    rec.folder = mb.label_for_rank(other)

    # cinque minuti dopo, di giorno: la correzione entra subito
    adapter2 = FakeAdapter([rec])
    run_cycle([CycleMailbox(mb, adapter2)], encoder, data, now=t0 + timedelta(minutes=5), run_nightly=False, progress=said.append)
    clf = build_classifier(mb, encoder, data)
    row = clf.registry.get("m1")
    assert row["status"] == "frozen" and row["final_rank"] == other
    assert clf.state.n_corr == 1
    assert any("learned 1 corrections" in line for line in said)
    assert adapter2.probe_calls == 1


def test_cycle_writes_a_notify_file_only_when_it_labels(tmp_path):
    from neuraec.bench.synthetic import make_email

    mb = mailbox("a")
    recs = []
    for index, kind in enumerate(("invoice", "newsletter")):
        rec = make_email(f"n{index}", kind, user_id="a", subject_extra="riga\tdue\nrighe")
        rec.folder = "INBOX"
        rec.is_seen = False
        recs.append(rec)
    data = tmp_path / "data"
    now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    said: list[str] = []
    run_cycle(
        [CycleMailbox(mb, FakeAdapter(recs))],
        FakeEncoder(),
        data,
        now=now,
        run_nightly=False,
        progress=said.append,
    )
    files = sorted((tmp_path / "notify").glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["mailbox_id"] == mb.mailbox_id
    assert payload["account"] == "a@azienda.it"
    assert len(payload["items"]) == 2
    for item in payload["items"]:
        assert item["label"] == mb.label_for_rank(item["rank"])
        assert "\n" not in item["subject"] and "\t" not in item["snippet"]
        assert len(item["snippet"]) <= 160
    assert any(line.startswith("new: ") for line in said)

    run_cycle(
        [CycleMailbox(mb, FakeAdapter())],
        FakeEncoder(),
        data,
        now=now + timedelta(minutes=5),
        run_nightly=False,
    )
    assert len(list((tmp_path / "notify").glob("*.json"))) == 1


def test_imap_password_file_is_not_the_json(tmp_path):
    primary = tmp_path / "mailbox.json"
    extra = tmp_path / "mailboxes" / "altro.json"
    _dump(primary, "a")
    _dump(extra, "b")
    extra.with_suffix(".password").write_text("nascosta\n", encoding="utf-8")
    assert "nascosta" not in extra.read_text(encoding="utf-8")
    assert imap_password(extra, primary) == "nascosta"
    assert mailbox_paths(primary) == [primary, extra]


def test_nightly_due_after_two_once_a_day():
    tz = datetime.now().astimezone().tzinfo
    morning = datetime(2026, 9, 26, 3, 0, tzinfo=tz)
    assert nightly_due(None, morning) is True
    assert nightly_due(None, datetime(2026, 9, 26, 1, 0, tzinfo=tz)) is False
    done = morning.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    assert nightly_due(done, datetime(2026, 9, 26, 15, 0, tzinfo=tz)) is False
    assert nightly_due(done, datetime(2026, 9, 27, 2, 30, tzinfo=tz)) is True


def test_user_lock_is_reentrant_and_exclusive(tmp_path):
    state = UserState(tmp_path / "u", user_id="u", N=4)
    with state.lock():
        with state.lock():
            state.n_pred = 3
    order: list[str] = []

    def worker(name: str) -> None:
        with state.lock():
            order.append(f"in-{name}")
            time.sleep(0.05)
            order.append(f"out-{name}")

    threads = [threading.Thread(target=worker, args=(str(i),)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert [step.split("-")[0] for step in order] == ["in", "out", "in", "out"]
