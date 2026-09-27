from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from neuraec.bench.synthetic import make_email
from neuraec.estimators import domain_estimate, memory_estimate, sender_estimate
from neuraec.learn import observe
from neuraec.ordinal import argmax_rank, decay, uniform


def test_sender_confidence_grows_with_n_and_falls_with_disagreement(tmp_user):
    clf = tmp_user("u")
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    addr = "rossi@fornitore.it"
    for i in range(6):
        rec = make_email(f"s{i}", "invoice", from_addr=addr, user_id="u", minutes=i)
        observe(clf, rec, rank=0, source="corr", now=now)

    p1, c1 = sender_estimate(addr, clf.state, now)
    assert c1 > 0.7
    assert argmax_rank(p1) == 0 and p1[0] == 1.0

    clf2 = tmp_user("u2")
    for i, rank in enumerate([0, 3, 0, 3, 0, 3]):
        rec = make_email(f"d{i}", "invoice", from_addr=addr, user_id="u2", minutes=i)
        observe(clf2, rec, rank=rank, source="corr", now=now)
    p2, c2 = sender_estimate(addr, clf2.state, now)
    assert c2 < c1
    # bimodal sender: the distribution keeps both modes, no invented middle rank
    assert p2[0] == p2[3] == 0.5 and p2[1] == p2[2] == 0.0


def test_sender_mass_decays_exactly_with_time(tmp_user):
    clf = tmp_user("u")
    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    t1 = t0 + timedelta(days=90)
    addr = "old@x.it"
    rec = make_email("o0", "invoice", from_addr=addr, user_id="u")
    observe(clf, rec, rank=0, source="corr", now=t0)
    mass_t0 = clf.state.sender_mass(addr, t0)
    mass_t1 = clf.state.sender_mass(addr, t1)
    assert np.isclose(mass_t0.sum(), 1.0)
    assert np.isclose(mass_t1.sum(), 0.5)
    # aggregated decay equals per-exemplar decay after a second observation
    rec2 = make_email("o1", "invoice", from_addr=addr, user_id="u", minutes=1)
    observe(clf, rec2, rank=0, source="corr", now=t1)
    t2 = t1 + timedelta(days=90)
    expected = decay(t0, t2) + decay(t1, t2)
    assert np.isclose(clf.state.sender_mass(addr, t2).sum(), expected)
    _p, c_old = sender_estimate(addr, clf.state, t2 + timedelta(days=365))
    _p, c_new = sender_estimate(addr, clf.state, t1)
    assert c_new > c_old


def test_sender_stats_survive_memory_eviction(tmp_user):
    clf = tmp_user("u", m_max=3)
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    addr = "a@x.it"
    for i in range(6):
        rec = make_email(f"a{i}", "invoice", from_addr=addr if i < 3 else f"z{i}@q.it", user_id="u", minutes=i)
        observe(clf, rec, rank=0, source="corr", now=now + timedelta(minutes=i))
    assert clf.state.size == 3
    p, c = sender_estimate(addr, clf.state, now + timedelta(hours=1))
    assert c > 0.7 and argmax_rank(p) == 0


def test_memory_excludes_self_and_empty_top(tmp_user, encoder):
    clf = tmp_user("u")
    rec = make_email("m1", "invoice", user_id="u")
    e = encoder.encode(rec.encoder_text())
    p, c, _h = memory_estimate(e, clf.state, rec.received_at)
    assert c == 0.0 and np.allclose(p, uniform(clf.state.N))

    observe(clf, rec, rank=0, source="corr", e=e)
    p2, c2, _h2 = memory_estimate(e, clf.state, rec.received_at, exclude_uid="m1")
    assert c2 == 0.0
    p3, c3, _h3 = memory_estimate(e, clf.state, rec.received_at)
    assert c3 > 0 and argmax_rank(p3) == 0


def test_memory_cap_keeps_last_of_sender(tmp_user, encoder):
    clf = tmp_user("u", m_max=5)
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(4):
        rec = make_email(f"a{i}", "invoice", from_addr="a@x.it", user_id="u", minutes=i)
        observe(clf, rec, rank=1, source="corr", now=now + timedelta(minutes=i))
    rec_b = make_email("b0", "newsletter", from_addr="b@y.it", user_id="u")
    observe(clf, rec_b, rank=0, source="corr", now=now + timedelta(hours=1))
    assert clf.state.size == 5
    rec_a5 = make_email("a5", "invoice", from_addr="a@x.it", user_id="u")
    observe(clf, rec_a5, rank=1, source="corr", now=now + timedelta(hours=2))
    assert clf.state.size == 5
    uids = {it["uid"] for it in clf.state.items}
    assert "b0" in uids
    assert [it["from_addr"] for it in clf.state.items].count("b@y.it") == 1


def test_domain_estimate_weaker_than_sender(tmp_user):
    clf = tmp_user("u")
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    for i in range(4):
        rec = make_email(f"x{i}", "invoice", from_addr=f"p{i}@dom.it", user_id="u", minutes=i)
        observe(clf, rec, rank=0, source="corr", now=now)
    _ps, cs = sender_estimate("p0@dom.it", clf.state, now)
    _pd, cd = domain_estimate("dom.it", clf.state, now)
    assert cd <= 0.6
    assert cs > 0
