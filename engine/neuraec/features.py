from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from neuraec.encoder import Encoder, l2_normalize
from neuraec.records import EmailRecord, MailboxConfig, domain_of

_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog_descriptions.json"


@lru_cache(maxsize=1)
def load_catalog_descriptions() -> dict[str, dict[str, str]]:
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def struttura(record: EmailRecord, mailbox: MailboxConfig) -> np.ndarray:
    """s ∈ ℝ^11 as specified in §4.2. only_to and no_cc use the real fields."""
    own = mailbox.own_set
    to_addrs = record.to_addrs
    cc_addrs = record.cc_addrs
    in_to = 1.0 if any(a in own for a in to_addrs) else 0.0
    in_cc = 1.0 if any(a in own for a in cc_addrs) else 0.0
    only_to = 1.0 if (len(to_addrs) > 0 and all(a in own for a in to_addrs)) else 0.0
    no_cc = 1.0 if len(cc_addrs) == 0 else 0.0
    log1p_n_to = math.log1p(len(to_addrs))
    log1p_n_cc = math.log1p(len(cc_addrs))
    attachment = 1.0 if record.has_attachment else 0.0
    is_reply = 1.0 if record.in_reply_to else 0.0
    bulk = 1.0 if (record.list_unsubscribe or record.list_id or record.precedence_bulk) else 0.0
    auto = 1.0 if record.auto_submitted else 0.0
    same_domain = 1.0 if (record.domain and record.domain in mailbox.own_domains) else 0.0
    return np.array(
        [
            in_to,
            in_cc,
            only_to,
            no_cc,
            log1p_n_to,
            log1p_n_cc,
            attachment,
            is_reply,
            bulk,
            auto,
            same_domain,
        ],
        dtype=np.float32,
    )


def relazione(
    record: EmailRecord,
    mailbox: MailboxConfig,
    replied_to: dict[str, int],
) -> np.ndarray:
    """r ∈ ℝ^3 as specified in §4.3."""
    n_replied = int(replied_to.get(record.from_addr, 0) or 0)
    log1p_replied = math.log1p(n_replied)
    sender_dom = record.domain
    replied_domain = 0.0
    if sender_dom:
        for addr, n in replied_to.items():
            if n and domain_of(addr) == sender_dom:
                replied_domain = 1.0
                break
    in_contacts = 1.0 if record.from_addr in mailbox.contact_set else 0.0
    return np.array([log1p_replied, replied_domain, in_contacts], dtype=np.float32)


def _mean_prototype(vectors: list[np.ndarray], dim: int) -> np.ndarray:
    if not vectors:
        return np.zeros(dim, dtype=np.float32)
    stacked = np.stack(vectors, axis=0)
    return l2_normalize(stacked.mean(axis=0))


class ProfilePrototypes:
    """User profile as text prototypes in the same space as e (§4.4)."""

    def __init__(self, encoder: Encoder, profile: dict[str, list[str]] | None) -> None:
        self.encoder = encoder
        self.profile = profile or {"fig": [], "fun": [], "set": []}
        catalog = load_catalog_descriptions()
        self.p_fig = self._catalog_proto(catalog.get("fig", {}), self.profile.get("fig") or [])
        self.p_fun = self._catalog_proto(catalog.get("fun", {}), self.profile.get("fun") or [])
        self.p_set = self._catalog_proto(catalog.get("set", {}), self.profile.get("set") or [])

    def _catalog_proto(self, descriptions: dict[str, str], keys: list[str]) -> np.ndarray:
        vecs = []
        for key in keys:
            text = descriptions.get(key)
            if text:
                vecs.append(self.encoder.encode(text))
        if not vecs:
            return np.zeros(self.encoder.dim, dtype=np.float32)
        return _mean_prototype(vecs, self.encoder.dim)

    def sim(self, e: np.ndarray) -> np.ndarray:
        return np.array(
            [
                float(np.dot(e, self.p_fig)),
                float(np.dot(e, self.p_fun)),
                float(np.dot(e, self.p_set)),
            ],
            dtype=np.float32,
        )
