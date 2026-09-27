from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from neuraec.bench.synthetic import make_email
from neuraec.learn import observe
from neuraec.ordinal import argmax_rank


def test_cold_prior_puts_bulk_low_and_direct_reply_high(tmp_user):
    clf = tmp_user("u", N=4)
    news = make_email("n", "newsletter", user_id="u", bulk=True, to_me=False, only_me=False, n_to=3)
    direct = make_email("d", "other", user_id="u", only_me=True, is_reply=True)
    p_news = clf.predict(news, write_registry=False)
    p_direct = clf.predict(direct, write_registry=False)
    assert p_news.stage == "prior" and p_direct.stage == "prior"
    assert p_news.rank > p_direct.rank


def test_prior_falls_back_to_user_majority(tmp_user):
    """User puts 90% of emails in rank 2 of 4: an unknown sender goes to rank 2."""
    clf = tmp_user("u", N=4)
    now = datetime(2024, 3, 1, tzinfo=timezone.utc)
    for i in range(30):
        rec = make_email(f"m{i}", "other", from_addr=f"p{i}@x{i}.it", user_id="u", minutes=i)
        rank = 2 if i % 10 else 0
        observe(clf, rec, rank=rank, source="corr", now=now)
    unknown = make_email("q", "other", from_addr="nuovo@mai-visto.it", user_id="u", only_me=False, to_me=True, n_to=2)
    pred = clf.predict(unknown, write_registry=False, now=now)
    assert pred.stage in {"prior", "memory"}
    assert pred.rank == 2


def test_prior_tilt_moves_bulk_down_with_data(tmp_user):
    clf = tmp_user("u", N=4)
    now = datetime(2024, 3, 1, tzinfo=timezone.utc)
    # user spreads across ranks 1 and 2 equally
    for i in range(20):
        rec = make_email(f"m{i}", "other", from_addr=f"p{i}@x{i}.it", user_id="u", minutes=i)
        observe(clf, rec, rank=1 + (i % 2), source="corr", now=now)
    news = make_email("n", "newsletter", from_addr="new@promo.example", user_id="u", bulk=True)
    reply = make_email("r", "other", from_addr="boss@altrove.it", user_id="u", is_reply=True, only_me=True)
    p_news = clf.predict(news, write_registry=False, now=now)
    p_reply = clf.predict(reply, write_registry=False, now=now)
    assert p_news.rank >= p_reply.rank
    assert np.isclose(sum(p_news.p), 1.0)
