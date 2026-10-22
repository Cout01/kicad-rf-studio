# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

from kicad_rf_studio.core.post.chain import with_box, z_part
from kicad_rf_studio.core.post.checks import (LOSS_LIMIT, RECIP_LIMIT, SIGMA_LIMIT, compare, indicator_lines,
                                              loss_budget, loss_expected, recip_err, sigma_max)
from kicad_rf_studio.core.post.waves import grid
from networks import C_BOX, star, thru
from test_post_chain import LPF, M0402

F0 = 915e6
F, _ = grid(F0, 3, 1.1)


def db(x):
    return 20 * np.log10(np.abs(x))


def lpf_zk():
    return np.stack([with_box(z_part(k, v, M0402, F), F, C_BOX) for _, k, v in LPF], -1)


def test_passivity_is_sigma_max_and_reciprocity_the_largest_asymmetry():  # spec 7.4, C-33, C-35
    assert (SIGMA_LIMIT, RECIP_LIMIT, LOSS_LIMIT) == (1.02, 0.02, 0.02)
    assert np.abs(sigma_max(star(F, 3, a=1.0)) - 1).max() <= 1e-14
    assert sigma_max(star(F, 6)).max() == pytest.approx(0.95 ** 2, abs=1e-12)
    s = star(F, 3).copy()
    s[:, 0, 2] += 0.01
    assert recip_err(s) == pytest.approx(np.full(len(F), 0.01), abs=1e-15)


def test_the_loss_budget_removes_the_part_losses_exactly():  # C-34; r6 §7
    assert np.abs(loss_budget(star(F, 6, a=1.0), [0, 1], lpf_zk())).max() <= 1e-14  # lossless layout, ESR parts
    expected = loss_expected([(4.5, 2.984, 0.02, 20.0)], F0)
    assert expected == pytest.approx(0.0112634, abs=1e-7)  # a 20 mm line under mask
    g = np.sqrt(1 - expected) * np.exp(-2j * np.pi * F * 0.1e-9)
    line = np.zeros((len(F), 2, 2), complex)
    line[:, 0, 1] = line[:, 1, 0] = g
    assert np.abs(loss_budget(line, [0, 1], np.zeros((len(F), 0))) - expected).max() <= 1e-14  # M = 0, flat


def test_the_indicators_name_their_worst_frequency_and_flag_above_their_limits():  # spec 7.4, C-12, C-33..C-35
    a_db = np.full(len(F), -3.0)
    calm = indicator_lines(F, a_db, star(F, 3), np.full(len(F), 0.01), 0.005)
    assert [code for code, _ in calm] == ["I_PASSIVITY", "I_RECIPROCITY", "I_LOSS_BUDGET"]
    s = star(F, 3).copy()
    s[100] *= 1.2
    s[200, 0, 1] += 0.05
    lines = indicator_lines(F, a_db, s, np.full(len(F), 0.05), 0.02)
    assert lines[0] == ("W_PASSIVITY", {"sigma": "1.0830", "limit": "1.02", "f_mhz": f"{F[100] / 1e6:.1f}",
                                        "a_db": "-3.0"})
    assert lines[1] == ("W_RECIPROCITY", {"err": "5.00e-02", "limit": "0.02", "f_mhz": f"{F[200] / 1e6:.1f}",
                                          "a_db": "-3.0"})
    assert lines[2] == ("W_LOSS_BUDGET", {"layout_pct": "5.00", "expected_pct": "2.00", "limit_pct": "2",
                                          "f_mhz": "457.5", "a_db": "-3.0"})
    assert [code for code, _ in indicator_lines(F, a_db, star(F, 3), None, 0.0)] == ["I_PASSIVITY", "I_RECIPROCITY"]
    verify = [indicator_lines(F, a_db, x, np.full(len(F), p), e, in_grid=True)[2]  # the parts in the grid: verify's
              for x, p, e in ((star(F, 3), 0.01, 0.005), (s, 0.05, 0.02))]
    assert verify == [("I_VERIFY_LOSS_BUDGET", calm[2][1]), ("W_VERIFY_LOSS_BUDGET", lines[2][1])]


def test_compare_reports_delta_s_and_the_null_shift():  # spec 7.5, 7.6, C-38, C-39; r6 §8: −1.9419 % within 1e-5
    a = thru(z_part("C", 6.8e-12, {**M0402, "esl_h": 5.2e-10}, F), "shunt")  # verify's: a −48 dB trap
    b = thru(z_part("C", 6.8e-12, M0402, F), "shunt")
    c = compare(a, b, F, 71, 0.02)
    assert c["ds21_db_f0"] == pytest.approx(abs(db(a[71, 1, 0]) - db(b[71, 1, 0])), rel=1e-12)
    assert c["ds11_f0"] == pytest.approx(abs(a[71, 0, 0] - b[71, 0, 0]), rel=1e-12)
    assert c["ds_max"] == pytest.approx(np.abs(a - b).max(), rel=1e-12)
    (null,) = c["nulls"]
    assert null["f_hz"] == pytest.approx(2676.48e6, abs=0.05e6)
    assert null["shift"] == pytest.approx(1 / np.sqrt(1.04) - 1, abs=1e-5)
    flat = thru(np.full(len(F), 1e9 + 0j), "shunt")
    assert compare(a, flat, F, 71, 0.02)["nulls"] == [{"f_hz": pytest.approx(null["f_hz"]), "shift": None}]
    assert compare(a, b, F, 71, 0.5)["nulls"] == []  # shoulders 0.892 at f1 and 0.083 at f2: the smaller one rules
