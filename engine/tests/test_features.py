from __future__ import annotations

import math

from neuraec.bench.synthetic import mailbox, make_email
from neuraec.features import struttura


def test_only_to_and_no_cc_use_real_fields():
    mb = mailbox("u")
    # me in To, alone, empty Cc
    rec = make_email("1", "other", user_id="u", only_me=True, n_cc=0)
    s = struttura(rec, mb)
    assert s[0] == 1.0  # in_to
    assert s[1] == 0.0  # in_cc
    assert s[2] == 1.0  # only_to
    assert s[3] == 1.0  # no_cc

    # me in Cc with 5 others in To: only_to and no_cc stay independent of in_cc
    rec2 = make_email(
        "2",
        "other",
        user_id="u",
        to_me=False,
        only_me=False,
        cc_me=True,
        n_to=5,
        n_cc=2,
    )
    s2 = struttura(rec2, mb)
    assert s2[0] == 0.0
    assert s2[1] == 1.0  # in_cc
    assert s2[2] == 0.0  # only_to (To is others)
    assert s2[3] == 0.0  # no_cc is false even though in_cc is true
    assert abs(s2[4] - math.log1p(5)) < 1e-6
    assert abs(s2[5] - math.log1p(2)) < 1e-6


def test_bulk_and_same_domain():
    mb = mailbox("u")
    rec = make_email("b", "newsletter", user_id="u", bulk=True)
    s = struttura(rec, mb)
    assert s[8] == 1.0
    rec2 = make_email("d", "other", from_addr="collega@azienda.it", user_id="u")
    s2 = struttura(rec2, mb)
    assert s2[10] == 1.0


def test_empty_to_is_not_only_to():
    mb = mailbox("u")
    rec = make_email("e", "other", user_id="u", to_me=False, only_me=False, n_to=0)
    rec.to_addrs = []
    s = struttura(rec, mb)
    assert s[2] == 0.0
