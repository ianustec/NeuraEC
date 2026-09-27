from __future__ import annotations

import hashlib
from datetime import datetime

import numpy as np

from neuraec.combine import STAGE_ORDER, combine
from neuraec.constants import MODEL_VERSION, SNIPPET_CHARS
from neuraec.prior_net import PriorNet
from neuraec.encoder import Encoder
from neuraec.estimators import (
    domain_estimate,
    memory_estimate,
    prior_estimate,
    sender_estimate,
    thread_estimate,
)
from neuraec.features import ProfilePrototypes, relazione, struttura
from neuraec.ordinal import argmax_rank, expected_u
from neuraec.records import EmailRecord, MailboxConfig, Prediction, utcnow
from neuraec.registry import Registry
from neuraec.state import UserState


class Classifier:
    def __init__(
        self,
        mailbox: MailboxConfig,
        state: UserState,
        encoder: Encoder,
        registry: Registry | None = None,
        prior_net: PriorNet | None = None,
    ) -> None:
        self.mailbox = mailbox
        self.state = state
        self.encoder = encoder
        self.registry = registry
        self.prior_net = prior_net if prior_net is not None and prior_net.accepted else None
        self.model_version = "neura-tappa4-prior-v1" if self.prior_net is not None else MODEL_VERSION
        self._prototypes = ProfilePrototypes(encoder, state.profile)

    def refresh_profile(self) -> None:
        self._prototypes = ProfilePrototypes(self.encoder, self.state.profile)

    def encode_record(self, rec: EmailRecord) -> np.ndarray:
        return self.encoder.encode(rec.encoder_text(SNIPPET_CHARS))

    def parts(
        self,
        rec: EmailRecord,
        e: np.ndarray,
        s: np.ndarray,
        r: np.ndarray,
        now: datetime,
        exclude_uid: str | None = None,
    ) -> dict[str, tuple[np.ndarray, float]]:
        sim = self._prototypes.sim(e)
        p_thr, c_thr = thread_estimate(rec, self.registry, self.state.N)
        p_snd, c_snd = sender_estimate(rec.from_addr, self.state, now)
        p_dom, c_dom = domain_estimate(rec.domain, self.state, now)
        p_mem, c_mem, _h = memory_estimate(e, self.state, now, exclude_uid=exclude_uid)
        p_pri, c_pri = prior_estimate(s, r, sim, self.state, now, e=e, prior_net=self.prior_net)
        return {
            "thread": (p_thr, c_thr),
            "sender": (p_snd, c_snd),
            "domain": (p_dom, c_dom),
            "memory": (p_mem, c_mem),
            "prior": (p_pri, c_pri),
        }

    def distribution(
        self,
        rec: EmailRecord,
        *,
        exclude_uid: str | None = None,
        now: datetime | None = None,
        e: np.ndarray | None = None,
    ) -> tuple[np.ndarray, dict[str, tuple[np.ndarray, float]]]:
        now = now or rec.received_at or utcnow()
        if e is None:
            e = self.encode_record(rec)
        s = struttura(rec, self.mailbox)
        r = relazione(rec, self.mailbox, self.state.replied_to)
        parts = self.parts(rec, e, s, r, now, exclude_uid)
        return combine(parts, self.state.N), parts

    def predict(
        self,
        rec: EmailRecord,
        *,
        now: datetime | None = None,
        write_registry: bool = True,
        e: np.ndarray | None = None,
    ) -> Prediction:
        now = now or utcnow()
        if e is None:
            e = self.encode_record(rec)
        P, parts = self.distribution(rec, now=now, e=e)
        rank = argmax_rank(P)
        u = expected_u(P, self.state.N)
        stage = max(STAGE_ORDER, key=lambda name: parts[name][1])
        conf = max(c for _, c in parts.values())
        pred = Prediction(
            rank=rank,
            u=u,
            conf=conf,
            stage=stage,
            parts={k: (float(np.dot(p, _centers(self.state.N))), float(c)) for k, (p, c) in parts.items()},
            p=P.tolist(),
            p_max=float(P.max()),
        )
        self.state.n_pred += 1
        if write_registry and self.registry is not None:
            text = rec.encoder_text(SNIPPET_CHARS)
            e_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
            self.registry.insert_prediction(
                uid=rec.uid,
                message_id=rec.message_id,
                thread_key=rec.thread_key,
                from_addr=rec.from_addr,
                received_at=rec.received_at,
                e_hash=e_hash,
                pred_rank=rank,
                pred_u=u,
                pred_conf=conf,
                stage=stage,
                model_version=self.model_version,
                written_label=self.mailbox.label_for_rank(rank),
                written_at=now,
            )
        return pred


def _centers(N: int) -> np.ndarray:
    from neuraec.ordinal import u_star_vector

    return u_star_vector(N)
