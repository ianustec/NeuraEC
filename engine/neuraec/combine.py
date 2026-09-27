from __future__ import annotations

import numpy as np

from neuraec.ordinal import uniform

STAGE_ORDER = ("thread", "sender", "domain", "memory", "prior")


def combine(parts: dict[str, tuple[np.ndarray, float]], N: int) -> np.ndarray:
    """P ∝ Σ_i c_i · p_i. If no confidence is > 0, P is uniform."""
    P = np.zeros(int(N), dtype=np.float64)
    total = 0.0
    for name in STAGE_ORDER:
        p, c = parts.get(name, (None, 0.0))
        if p is None or c <= 0:
            continue
        P += float(c) * np.asarray(p, dtype=np.float64)
        total += float(c)
    if total <= 0:
        return uniform(N)
    return P / P.sum()
