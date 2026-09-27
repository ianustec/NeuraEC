from __future__ import annotations

from pathlib import Path

import pytest

from neuraec.bench.synthetic import mailbox
from neuraec.classifier import Classifier
from neuraec.encoder import FakeEncoder
from neuraec.registry import Registry
from neuraec.state import UserState


@pytest.fixture
def encoder() -> FakeEncoder:
    return FakeEncoder()


@pytest.fixture
def tmp_user(tmp_path: Path, encoder: FakeEncoder):
    def _make(user_id: str = "u1", N: int = 4, order: str = "desc", m_max: int = 10000) -> Classifier:
        mb = mailbox(user_id, N=N, order=order)
        state = UserState(
            tmp_path / user_id,
            user_id=user_id,
            N=N,
            order=order,
            encoder_name=encoder.name,
            m_max=m_max,
        )
        registry = Registry(tmp_path / user_id / "pred.sqlite")
        return Classifier(mb, state, encoder, registry)

    return _make
