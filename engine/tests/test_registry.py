from __future__ import annotations

from datetime import datetime, timezone

from neuraec.registry import Registry
from neuraec.records import utcnow


def test_insert_and_thread_lookup(tmp_path):
    reg = Registry(tmp_path / "p.sqlite")
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    reg.insert_prediction(
        uid="1",
        message_id="m1",
        thread_key="t1",
        from_addr="a@b.it",
        received_at=now,
        e_hash="abc",
        pred_rank=1,
        pred_u=0.6,
        pred_conf=0.2,
        stage="prior",
        model_version="t",
        written_label="P1",
        written_at=now,
    )
    row = reg.lookup_thread("t1")
    assert row is not None
    assert row["status"] == "open"
    assert row["pred_u"] == 0.6


def test_resolve_is_idempotent(tmp_path):
    reg = Registry(tmp_path / "p.sqlite")
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    reg.insert_prediction(
        uid="1",
        message_id="m1",
        thread_key="t1",
        from_addr="a@b.it",
        received_at=now,
        e_hash="abc",
        pred_rank=1,
        pred_u=0.6,
        pred_conf=0.2,
        stage="prior",
        model_version="t",
        written_label="P1",
        written_at=now,
    )
    assert reg.resolve("1", user_action="moved", final_rank=0, status="frozen", now=now) is True
    assert reg.resolve("1", user_action="moved", final_rank=2, status="frozen", now=now) is False
    row = reg.get("1")
    assert row["status"] == "frozen"
    assert row["final_rank"] == 0
    assert row["user_action"] == "moved"


def test_predict_writes_registry_and_observe_closes_it(tmp_user):
    from neuraec.bench.synthetic import make_email
    from neuraec.learn import observe

    clf = tmp_user("u")
    rec = make_email("p1", "invoice", user_id="u")
    pred = clf.predict(rec)
    row = clf.registry.get("p1")
    assert row is not None and row["status"] == "open" and row["pred_rank"] == pred.rank

    observe(clf, rec, rank=0, source="corr")
    row = clf.registry.get("p1")
    assert row["status"] == "frozen" and row["user_action"] == "moved" and row["final_rank"] == 0

    # frozen rows are never overwritten by a new prediction
    pred2 = clf.predict(rec)
    row2 = clf.registry.get("p1")
    assert row2["status"] == "frozen" and row2["final_rank"] == 0
    assert pred2.rank == 0  # the thread of a corrected email inherits the user's rank


def test_thread_lookup_excludes_own_row(tmp_path):
    reg = Registry(tmp_path / "p.sqlite")
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    reg.insert_prediction(
        uid="self",
        message_id="m",
        thread_key="m",
        from_addr="a@b.it",
        received_at=now,
        e_hash="h",
        pred_rank=2,
        pred_u=0.4,
        pred_conf=0.2,
        stage="prior",
        model_version="t",
        written_label="P2",
        written_at=now,
    )
    assert reg.lookup_thread("m", exclude_uid="self") is None
    assert reg.lookup_thread("m") is not None


def test_reply_inherits_user_rank_from_thread(tmp_user):
    from neuraec.bench.synthetic import make_email
    from neuraec.learn import observe

    clf = tmp_user("u")
    parent = make_email("root", "other", from_addr="capo@altrove.it", user_id="u")
    clf.predict(parent)
    observe(clf, parent, rank=0, source="corr")
    child = make_email("child", "other", from_addr="altro@altrove2.it", user_id="u", minutes=10)
    child.in_reply_to = parent.message_id
    child.references = [parent.message_id]
    pred = clf.predict(child, write_registry=False)
    assert pred.stage == "thread"
    assert pred.rank == 0
