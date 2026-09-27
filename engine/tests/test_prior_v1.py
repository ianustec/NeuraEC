from __future__ import annotations

import numpy as np
import pytest

from neuraec.bench.synthetic import make_email, opposite_policy_corpus
from neuraec.classifier import Classifier
from neuraec.constants import CONF_PRIOR, CONF_PRIOR_V1
from neuraec.learn import observe
from neuraec.prior_net import H1, H2, IN_DIM, PriorNet, load_accepted, pack_features
from neuraec.prior_train import accepts, collect_disk, holdout_user_ids, train_mlp


def _zeros_net(*, accepted: bool) -> PriorNet:
    return PriorNet(
        np.zeros((IN_DIM, H1)),
        np.zeros(H1),
        np.zeros((H1, H2)),
        np.zeros(H2),
        np.zeros((H2, 1)),
        np.zeros(1),
        accepted=accepted,
    )


def test_urgency_is_sigmoid_of_zero_when_weights_are_zero():
    net = _zeros_net(accepted=True)
    e = np.zeros(384)
    s = np.zeros(11)
    r = np.zeros(3)
    sim = np.zeros(3)
    assert net.urgency(e, s, r, sim) == pytest.approx(0.5)
    assert pack_features(e, s, r, sim).shape == (IN_DIM,)


def test_numpy_forward_matches_torch_eval():
    torch = pytest.importorskip("torch")
    from torch import nn

    from neuraec.prior_train import _net_from_sequential

    torch.manual_seed(0)
    model = nn.Sequential(
        nn.Linear(IN_DIM, H1),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(H1, H2),
        nn.ReLU(),
        nn.Linear(H2, 1),
        nn.Sigmoid(),
    )
    net = _net_from_sequential(model)
    model.eval()
    x = torch.randn(4, IN_DIM)
    with torch.no_grad():
        ref = model(x).squeeze(-1).numpy()
    for i in range(4):
        row = x[i].numpy()
        e, s, r, sim = row[:384], row[384:395], row[395:398], row[398:]
        assert net.urgency(e, s, r, sim) == pytest.approx(float(ref[i]), abs=1e-5)


def test_rejected_net_is_ignored(tmp_user):
    net = _zeros_net(accepted=False)
    net.b3 = np.array([30.0])
    clf = tmp_user("u")
    clf.prior_net = None
    wired = Classifier(clf.mailbox, clf.state, clf.encoder, clf.registry, prior_net=net)
    assert wired.prior_net is None
    rec = make_email("p", "invoice", user_id="u")
    pred = wired.predict(rec, write_registry=False)
    assert pred.parts["prior"][1] == pytest.approx(CONF_PRIOR)


def test_accepted_net_raises_prior_confidence(tmp_user, tmp_path):
    net = _zeros_net(accepted=True)
    clf = tmp_user("u")
    wired = Classifier(clf.mailbox, clf.state, clf.encoder, clf.registry, prior_net=net)
    rec = make_email("p", "invoice", user_id="u")
    pred = wired.predict(rec, write_registry=False)
    assert pred.parts["prior"][1] == pytest.approx(CONF_PRIOR_V1)
    path = tmp_path / "prior.npz"
    net.accepted = False
    net.save(path)
    assert load_accepted(path) is None
    net.accepted = True
    net.save(path)
    loaded = load_accepted(path)
    assert loaded is not None and loaded.accepted
    again = Classifier(clf.mailbox, clf.state, clf.encoder, clf.registry, prior_net=loaded)
    assert again.predict(rec, write_registry=False).parts["prior"][1] == pytest.approx(CONF_PRIOR_V1)


def test_shared_net_does_not_couple_users(tmp_path, encoder):
    from neuraec.bench.synthetic import mailbox
    from neuraec.registry import Registry
    from neuraec.state import UserState

    net = _zeros_net(accepted=True)
    before = net.W1.copy()

    def make(user_id: str) -> Classifier:
        mb = mailbox(user_id)
        state = UserState(tmp_path / user_id, user_id=user_id, N=mb.N, encoder_name=encoder.name)
        return Classifier(mb, state, encoder, Registry(tmp_path / user_id / "pred.sqlite"), prior_net=net)

    clf_a = make("a")
    clf_b = make("b")
    for rec, kind in opposite_policy_corpus(20, user_id="a"):
        observe(clf_a, rec, rank=0 if kind == "newsletter" else 3, source="corr")
    for rec, kind in opposite_policy_corpus(20, user_id="b"):
        observe(clf_b, rec, rank=3 if kind == "newsletter" else 0, source="corr")
    holdout = opposite_policy_corpus(16, user_id="hold")
    news_a = []
    news_b = []
    for rec, kind in holdout:
        if kind != "newsletter":
            continue
        news_a.append(clf_a.predict(rec, write_registry=False).u)
        news_b.append(clf_b.predict(rec, write_registry=False).u)
    assert sum(news_a) / len(news_a) > sum(news_b) / len(news_b)
    assert np.array_equal(before, net.W1)

    snap = [clf_a.predict(rec, write_registry=False).rank for rec, _ in holdout]
    clf_c = make("c")
    for rec, kind in opposite_policy_corpus(30, user_id="c"):
        observe(clf_c, rec, rank=0, source="corr", persist=False)
    assert snap == [clf_a.predict(rec, write_registry=False).rank for rec, _ in holdout]


def test_holdout_is_whole_users_and_stable():
    ids = [str(i) for i in range(13)]
    first = holdout_user_ids(ids)
    second = holdout_user_ids(list(reversed(ids)))
    assert first == second
    assert len(first) == 3
    assert len(set(first)) == 3
    assert set(first).isdisjoint(set(ids) - set(first))


def test_accepts_requires_both_gates():
    base = {"per_user": {"1": {"accuracy": 0.8, "n": 10}, "2": {"accuracy": 0.5, "n": 4}}}
    better = {"per_user": {"1": {"accuracy": 0.8, "n": 10}, "2": {"accuracy": 0.55, "n": 4}}}
    worse = {"per_user": {"1": {"accuracy": 0.7, "n": 10}, "2": {"accuracy": 0.9, "n": 4}}}
    assert accepts(0.10, 0.20, base, better)
    assert accepts(0.20, 0.20, base, better) is False
    assert accepts(0.10, 0.20, base, worse) is False


def test_disk_collects_only_corrections(tmp_user, tmp_path, encoder):
    clf = tmp_user("u")
    corr = make_email("c1", "invoice", user_id="u")
    conf = make_email("k1", "newsletter", user_id="u", minutes=1)
    observe(clf, corr, rank=0, source="corr")
    observe(clf, conf, rank=3, source="conf")
    samples = collect_disk(tmp_path, encoder)
    assert len(samples) == 1
    assert samples[0].user_id == "u"
    assert samples[0].features.shape == (IN_DIM,)
    assert samples[0].u == pytest.approx(1.0 - 0.5 / 4)


def test_train_mlp_writes_a_net():
    pytest.importorskip("torch")
    rng = np.random.default_rng(0)
    samples = []
    from neuraec.prior_train import PriorSample

    for user, u in (("a", 0.2), ("b", 0.8), ("c", 0.4), ("d", 0.6)):
        for _ in range(6):
            e = rng.normal(size=384)
            s = rng.normal(size=11)
            r = np.zeros(3)
            sim = np.zeros(3)
            samples.append(
                PriorSample(user, pack_features(e, s, r, sim), u, s, r, sim)
            )
    holdout = holdout_user_ids([s.user_id for s in samples], k=1)
    net, info = train_mlp(samples, holdout, max_epochs=4, patience=2)
    assert net.accepted is False
    assert info["epochs"] >= 1
    assert 0.0 < net.urgency(np.zeros(384), np.zeros(11), np.zeros(3), np.zeros(3)) < 1.0
