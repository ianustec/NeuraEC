from __future__ import annotations

import numpy as np

from neuraec.ordinal import (
    argmax_rank,
    expected_u,
    label_to_rank,
    one_hot,
    rank_to_label,
    remap_ranks,
    u_star,
    u_star_vector,
)


def test_u_star_monotone_and_inverse_via_one_hot():
    for N in range(3, 11):
        centers = u_star_vector(N)
        assert np.all(np.diff(centers) < 0)  # rank 0 is most urgent
        for r in range(N):
            p = one_hot(r, N)
            assert argmax_rank(p) == r
            assert abs(expected_u(p, N) - u_star(r, N)) < 1e-12


def test_label_to_rank_both_orders_roundtrip():
    for N in range(3, 11):
        for order in ("desc", "asc"):
            for label in range(N):
                rank = label_to_rank(label, N, order)
                assert rank_to_label(rank, N, order) == label
    assert label_to_rank(0, 4, "desc") == 0
    assert label_to_rank(0, 4, "asc") == 3


def test_remap_ranks_preserves_order():
    old = [0, 1, 2, 3]
    new = remap_ranks(old, N_old=4, N_new=8)
    assert new == sorted(new)
    assert new[0] == 0 and new[-1] == 7
    assert new[0] < new[1] < new[2] < new[3]
    down = remap_ranks(list(range(10)), N_old=10, N_new=3)
    assert down == sorted(down)
    assert down[0] == 0 and down[-1] == 2
