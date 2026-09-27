from __future__ import annotations

from pathlib import Path

import numpy as np

from neuraec.bench.synthetic import mailbox, opposite_policy_corpus
from neuraec.classifier import Classifier
from neuraec.encoder import FakeEncoder
from neuraec.learn import observe
from neuraec.registry import Registry
from neuraec.state import UserState


def _clf(root: Path, user_id: str, encoder: FakeEncoder, N: int = 4) -> Classifier:
    mb = mailbox(user_id, N=N)
    state = UserState(root / user_id, user_id=user_id, N=N, encoder_name=encoder.name)
    registry = Registry(root / user_id / "pred.sqlite")
    return Classifier(mb, state, encoder, registry)


def _policy_rank(kind: str, user: str, N: int = 4) -> int:
    # A: newsletters rank 0, invoices rank N-1
    # B: opposite
    if user == "a":
        return 0 if kind == "newsletter" else N - 1
    return N - 1 if kind == "newsletter" else 0


def test_opposite_policies_diverge_and_third_user_is_isolated(tmp_path):
    encoder = FakeEncoder()
    N = 4
    clf_a = _clf(tmp_path, "a", encoder, N)
    clf_b = _clf(tmp_path, "b", encoder, N)

    train_a = opposite_policy_corpus(20, user_id="a")
    train_b = opposite_policy_corpus(20, user_id="b")
    for rec, kind in train_a:
        observe(clf_a, rec, rank=_policy_rank(kind, "a", N), source="corr")
    for rec, kind in train_b:
        observe(clf_b, rec, rank=_policy_rank(kind, "b", N), source="corr")

    holdout = opposite_policy_corpus(50, user_id="hold")
    preds_a = [clf_a.predict(rec, write_registry=False) for rec, _ in holdout]
    preds_b = [clf_b.predict(rec, write_registry=False) for rec, _ in holdout]

    news_a = [p.u for p, (_, k) in zip(preds_a, holdout) if k == "newsletter"]
    news_b = [p.u for p, (_, k) in zip(preds_b, holdout) if k == "newsletter"]
    inv_a = [p.u for p, (_, k) in zip(preds_a, holdout) if k == "invoice"]
    inv_b = [p.u for p, (_, k) in zip(preds_b, holdout) if k == "invoice"]
    # A treats newsletters as more urgent than B does
    assert sum(news_a) / len(news_a) > sum(news_b) / len(news_b)
    # A treats invoices as less urgent than B does
    assert sum(inv_a) / len(inv_a) < sum(inv_b) / len(inv_b)

    snap_a = [(p.rank, p.stage) for p in preds_a]
    snap_b = [(p.rank, p.stage) for p in preds_b]
    u_a = np.array([p.u for p in preds_a])
    u_b = np.array([p.u for p in preds_b])
    vecs_a = clf_a.state.vectors.copy()
    vecs_b = clf_b.state.vectors.copy()

    clf_c = _clf(tmp_path, "c", encoder, N)
    train_c = opposite_policy_corpus(1000, user_id="c")
    for rec, kind in train_c:
        observe(clf_c, rec, rank=_policy_rank(kind, "a", N), source="corr", persist=False)
    clf_c.state.save()

    preds_a2 = [clf_a.predict(rec, write_registry=False) for rec, _ in holdout]
    preds_b2 = [clf_b.predict(rec, write_registry=False) for rec, _ in holdout]
    assert snap_a == [(p.rank, p.stage) for p in preds_a2]
    assert snap_b == [(p.rank, p.stage) for p in preds_b2]
    assert np.array_equal(vecs_a, clf_a.state.vectors)
    assert np.array_equal(vecs_b, clf_b.state.vectors)
    assert np.allclose(u_a, np.array([p.u for p in preds_a2]))
    assert np.allclose(u_b, np.array([p.u for p in preds_b2]))
