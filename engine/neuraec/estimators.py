"""Stimatori: ognuno restituisce (p, c) con p distribuzione sui ranghi, c ∈ [0, 1]."""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from neuraec.constants import (
    CONF_PRIOR,
    CONF_PRIOR_V1,
    CONF_THREAD_MODEL,
    CONF_THREAD_USER,
    DOMAIN_CONF_SCALE,
    DOMAIN_N_SCALE,
    HALF_LIFE_DAYS,
    MEMORY_COS_TAU,
    MEMORY_K,
    MEMORY_TEMPERATURE,
    PRIOR_COLD_MASS,
    PRIOR_GAUSS_SIGMA,
    PRIOR_LAPLACE,
    PRIOR_TILT_BETA,
    SENDER_CONF_SCALE,
    SENDER_N_SCALE,
)
from neuraec.ordinal import decay, one_hot, u_star_vector, uniform
from neuraec.records import EmailRecord
from neuraec.registry import Registry
from neuraec.state import UserState


def _none(N: int) -> tuple[np.ndarray, float]:
    return uniform(N), 0.0


def thread_estimate(
    record: EmailRecord,
    registry: Registry | None,
    N: int,
) -> tuple[np.ndarray, float]:
    if registry is None:
        return _none(N)
    row = registry.lookup_thread(record.thread_key, exclude_uid=record.uid)
    if row is None:
        return _none(N)
    if row.get("status") in ("resolved", "frozen") and row.get("user_action") in (
        "moved",
        "replied",
        "manual",
    ):
        final = row.get("final_rank")
        if final is None:
            return _none(N)
        return one_hot(int(final), N), CONF_THREAD_USER
    if row.get("status") == "open" and row.get("pred_rank") is not None:
        return one_hot(int(row["pred_rank"]), N), CONF_THREAD_MODEL
    return _none(N)


def _from_mass(mass: np.ndarray | None, N: int, conf_scale: float, n_scale: float) -> tuple[np.ndarray, float]:
    if mass is None:
        return _none(N)
    n_eff = float(mass.sum())
    if n_eff <= 0:
        return _none(N)
    p = mass / n_eff
    agree = float(p.max())
    c = conf_scale * (1.0 - math.exp(-n_eff / n_scale)) * agree
    return p, min(max(c, 0.0), 1.0)


def sender_estimate(from_addr: str, state: UserState, now: datetime) -> tuple[np.ndarray, float]:
    return _from_mass(state.sender_mass(from_addr, now), state.N, SENDER_CONF_SCALE, SENDER_N_SCALE)


def domain_estimate(domain: str, state: UserState, now: datetime) -> tuple[np.ndarray, float]:
    return _from_mass(state.domain_mass(domain, now), state.N, DOMAIN_CONF_SCALE, DOMAIN_N_SCALE)


def memory_estimate(
    e: np.ndarray,
    state: UserState,
    now: datetime,
    exclude_uid: str | None = None,
    k: int = MEMORY_K,
    tau: float = MEMORY_COS_TAU,
    temperature: float = MEMORY_TEMPERATURE,
) -> tuple[np.ndarray, float, np.ndarray]:
    N = state.N
    zero_h = np.zeros(e.shape[0], dtype=np.float32)
    if state.size == 0:
        return uniform(N), 0.0, zero_h
    sims = state.vectors @ e.astype(np.float32)
    if exclude_uid is not None:
        idx = state.index_of_uid(exclude_uid)
        if idx is not None:
            sims = sims.copy()
            sims[idx] = -1.0
    order = np.argsort(sims)[::-1][:k]
    top = [int(i) for i in order if sims[i] >= tau]
    if not top:
        return uniform(N), 0.0, zero_h
    cos = np.array([float(sims[i]) for i in top], dtype=np.float64)
    logits = cos / temperature
    alpha = np.exp(logits - logits.max())
    weights = np.array(
        [
            float(state.items[i].get("weight") or 0.0) * decay(state.items[i]["ts"], now, HALF_LIFE_DAYS)
            for i in top
        ],
        dtype=np.float64,
    )
    alpha = alpha * weights
    if alpha.sum() <= 0:
        return uniform(N), 0.0, zero_h
    alpha = alpha / alpha.sum()
    p = np.zeros(N, dtype=np.float64)
    h = np.zeros(e.shape[0], dtype=np.float64)
    for a, i in zip(alpha, top):
        p[min(max(int(state.items[i]["rank"]), 0), N - 1)] += a
        h += a * state.vectors[i]
    mean_margin = float(np.mean(np.clip(cos - tau, 0.0, None)))
    c = min(max(mean_margin / 0.4, 0.0), 1.0) * (1.0 - math.exp(-len(top) / 3.0))
    return p, float(c), h.astype(np.float32)


def rules_urgency(s: np.ndarray, r: np.ndarray, sim: np.ndarray) -> float:
    """Prior v0 a regole: urgenza scalare in [0.05, 0.95] (§6.4)."""
    u = 0.5
    u += 0.20 * (1.0 if r[0] > 0 else 0.0)
    u += 0.10 * float(s[2])
    u += 0.10 * float(s[7])
    u += 0.05 * float(s[10])
    u -= 0.30 * float(s[8])
    u -= 0.20 * float(s[9])
    u -= 0.05 * float(s[1]) * (1.0 - float(s[0]))
    u += 0.15 * (float(np.max(sim)) - 0.25)
    return min(max(u, 0.05), 0.95)


def prior_estimate(
    s: np.ndarray,
    r: np.ndarray,
    sim: np.ndarray,
    state: UserState,
    now: datetime,
    *,
    e: np.ndarray | None = None,
    prior_net=None,
) -> tuple[np.ndarray, float]:
    """Prior = the user's empirical rank distribution, tilted by u_rule.

    v0: u_rule from the rules, c = 0.15. v1: u_rule = f_θ(e, s, r, sim), c = 0.3,
    only when prior_net.accepted. The shape of the distribution does not change.
    """
    N = state.N
    use_v1 = prior_net is not None and getattr(prior_net, "accepted", False) and e is not None
    if use_v1:
        u_rule = float(prior_net.urgency(e, s, r, sim))
        conf = CONF_PRIOR_V1
    else:
        u_rule = rules_urgency(s, r, sim)
        conf = CONF_PRIOR
    centers = u_star_vector(N)
    mass = state.rank_mass.at(now)
    total = float(mass.sum())
    if total < PRIOR_COLD_MASS:
        g = np.exp(-((centers - u_rule) ** 2) / (2.0 * PRIOR_GAUSS_SIGMA**2))
        p = g / g.sum()
        return p, conf
    p_emp = (mass + PRIOR_LAPLACE) / (total + PRIOR_LAPLACE * N)
    tilt = np.exp(PRIOR_TILT_BETA * (u_rule - 0.5) * (centers - 0.5))
    p = p_emp * tilt
    p = p / p.sum()
    return p, conf
