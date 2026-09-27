from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np


def u_star(rank: int, N: int) -> float:
    """Center of the uniform urgency bin for rank r. 0 = max urgency."""
    r = int(rank)
    n = int(N)
    if n < 1:
        raise ValueError("N must be >= 1")
    r = min(max(r, 0), n - 1)
    return 1.0 - (r + 0.5) / n


def u_star_vector(N: int) -> np.ndarray:
    return np.array([u_star(r, N) for r in range(int(N))], dtype=np.float64)


def expected_u(p: np.ndarray, N: int) -> float:
    return float(np.dot(np.asarray(p, dtype=np.float64), u_star_vector(N)))


def one_hot(rank: int, N: int) -> np.ndarray:
    p = np.zeros(int(N), dtype=np.float64)
    p[min(max(int(rank), 0), int(N) - 1)] = 1.0
    return p


def uniform(N: int) -> np.ndarray:
    return np.full(int(N), 1.0 / int(N), dtype=np.float64)


def argmax_rank(p: np.ndarray) -> int:
    """Rank with the largest mass; ties go to the more urgent rank (lower index)."""
    return int(np.argmax(np.asarray(p)))


def label_to_rank(id_service_label: int, N: int, order: str) -> int:
    """Map IdServiceLabel (0 = first label) to internal rank.

    order=desc: first label is most urgent, rank = IdServiceLabel.
    order=asc: last label is most urgent, rank = N − 1 − IdServiceLabel.
    """
    s = int(id_service_label)
    n = int(N)
    s = min(max(s, 0), n - 1)
    if order == "desc":
        return s
    return (n - 1) - s


def rank_to_label(rank: int, N: int, order: str) -> int:
    if order == "desc":
        return int(rank)
    return (int(N) - 1) - int(rank)


def remap_ranks(old_ranks: list[int], N_old: int, N_new: int) -> list[int]:
    """rank ← round(rank_old · (N_new − 1) / (N_old − 1)). Preserves order."""
    if N_old < 2:
        return [0 for _ in old_ranks]
    scale = (N_new - 1) / (N_old - 1)
    out = []
    for r in old_ranks:
        mapped = int(round(r * scale))
        out.append(min(max(mapped, 0), N_new - 1))
    return out


def _as_dt(x) -> datetime:
    if isinstance(x, datetime):
        return x if x.tzinfo is not None else x.replace(tzinfo=timezone.utc)
    if isinstance(x, str):
        return datetime.fromisoformat(x.replace("Z", "+00:00"))
    raise TypeError(type(x))


def days_between(ts, now) -> float:
    return (_as_dt(now) - _as_dt(ts)).total_seconds() / 86400.0


def decay(ts, now, half_life_days: float = 90.0) -> float:
    """0.5 ** (days / half_life). Clamped to 1 for ts in the future."""
    days = days_between(ts, now)
    if days <= 0:
        return 1.0
    return float(math.pow(0.5, days / half_life_days))
