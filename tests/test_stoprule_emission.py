# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

from kicad_rf_studio.core.model.spec import emission_pulse
from kicad_rf_studio.stoprule import RING_FACTOR, Records, stop_rule, tail_fit, truncated

EXC = emission_pulse(1.83e9, 3e9)  # the probe's pulse: 1.40–3 GHz, t0 1.79 ns, T_max 31 ns
SPAN = 31e-9 - 2 * EXC["t0"] - 2e-9  # the tail past 2·t0 + 2 ns


def ringing(modes, ports=1, t_end=31e-9):
    """f1's synthetic record: port 0 the band pulse, and at each port each mode (f, Q, [its amplitude at each port],
    relative to the pulse's peak) as a·e^(−π·f·(t − 2·t0)/Q)·sin(2π·f·t) from 2·t0; i = u/50, the energy Σu²."""
    t, t0 = np.arange(0, t_end, 5e-12), EXC["t0"]
    fm, fw = (EXC["f1"] + EXC["f2"]) / 2, (EXC["f2"] - EXC["f1"]) / 2
    u = np.zeros((ports, t.size))
    u[0] = np.sin(2 * np.pi * fm * (t - t0)) * np.exp(-(2 * np.pi * fw * t / 3 - 3) ** 2) * (t < 2 * t0)
    for f, q, amps in modes:
        ring = np.exp(-np.pi * f * (t - 2 * t0) / q) * np.sin(2 * np.pi * f * t) * (t >= 2 * t0)
        for k, a in enumerate(amps):
            u[k] += a * ring
    return Records(t, u, t, u / 50, t, (u ** 2).sum(0) + 1e-30)


def fitted(rec, t_end=31e-9):
    return tail_fit(rec.t_u, rec.u, EXC, t_end)


def test_an_emission_job_that_rings_is_never_flat():  # design 5.7; f1
    rec = ringing([(1.413e9, 232, [0.1, 0.01])], ports=2)
    assert stop_rule(rec, 0, "normal", EXC) is None  # no verdict to T_max: the job ends there, "t_max"
    v = stop_rule(rec, 0, "normal", {k: x for k, x in EXC.items() if k != "emission"})
    assert v.kind == "flat" and 2 * EXC["t0"] + 5e-9 <= v.t <= 2 * EXC["t0"] + 9e-9  # today's rule, as f1 found


def test_the_tail_fit_reads_one_rings_q_and_its_truncation_factor():  # design 5.7; f1's single mode
    (r,) = fitted(ringing([(1.413e9, 232, [0.1, 0.01])], ports=2))
    assert abs(r["f_hz"] - 1.413e9) <= 1 / SPAN and r["q"] == pytest.approx(232, rel=0.05)
    assert r["factor"] == pytest.approx(np.exp(-np.pi * 1.413e9 * 31e-9 / 232), rel=0.05)  # 0.553


@pytest.mark.parametrize("modes", [[(1.413e9, 232), (1.999e9, 895)],  # risk 2: two modes 0.59 GHz apart
                                   [(1.413e9, 232), (1.999e9, 1789)]])  # f1's plane pair, its slowest TM11
def test_two_rings_at_one_port_are_both_fitted_and_neither_reads_as_held(modes):  # risk 2; AR-5
    rings = fitted(ringing([(f, q, [0.1]) for f, q in modes]))
    assert len(rings) == 2
    for r, (f, q) in zip(rings, modes):
        assert abs(r["f_hz"] - f) <= 2 / SPAN and r["q"] == pytest.approx(q, rel=0.10) and r["factor"] > RING_FACTOR


def test_three_rings_over_two_ports_are_the_union_and_a_ring_weak_at_the_source_is_seen():  # risk 2; BC6
    modes = [(1.413e9, 232, [0.1, 0.001]), (1.999e9, 895, [0.001, 0.1]), (2.826e9, 186, [0.05, 0.001])]
    rings = fitted(ringing(modes, ports=2))
    assert len(rings) == 3
    for r, (f, q, _) in zip(rings, modes):
        assert abs(r["f_hz"] - f) <= 2 / SPAN and r["q"] == pytest.approx(q, rel=0.10) and r["factor"] > RING_FACTOR


def test_a_held_ring_has_no_q_and_truncates_every_frequency_beside_decaying_ones():  # Review Focus 4; AR-5
    modes = [(1.413e9, 232, [0.1]), (1.999e9, -2000, [0.03]), (2.826e9, 186, [0.1])]  # the middle one grows a little
    a, held, c = fitted(ringing(modes))
    assert (held["q"], held["factor"]) == (None, 1.0) and abs(held["f_hz"] - 1.999e9) <= 2 / SPAN
    assert a["q"] == pytest.approx(232, rel=0.10) and c["q"] == pytest.approx(186, rel=0.10)
    assert truncated(np.array([1e9, 3e9]), [a, held, c]).all()


def test_a_damped_ring_converges_and_truncates_nothing():  # design 5.7: a factor under 0.01
    rec = ringing([(1.413e9, 10, [0.1])])
    v = stop_rule(rec, 0, "normal", EXC)
    assert v.kind == "converged" and v.t < 31e-9
    rings = fitted(rec, v.t)
    assert all(r["factor"] < RING_FACTOR for r in rings) and not truncated(np.array([1.413e9]), rings).any()


def test_a_quiet_tail_and_a_short_one_fit_nothing():  # Review Focus 4
    assert fitted(ringing([])) == []  # the pulse ends at 2·t0
    short = 2 * EXC["t0"] + 2e-9 + 5e-9  # two whole 2 ns windows only
    assert fitted(ringing([(1.413e9, 232, [0.1])], t_end=short), short) == []


def test_truncated_is_50_f_over_q_round_each_ring_over_0_01():  # design 5.7
    rings = [{"f_hz": 2e9, "q": 1000.0, "factor": 0.5}, {"f_hz": 2.5e9, "q": 100.0, "factor": 0.005}]
    f = np.array([1.89e9, 1.9e9, 2.1e9, 2.11e9, 2.5e9])
    assert truncated(f, rings).tolist() == [False, True, True, False, False]


def test_a_ring_just_past_f2_is_fitted_at_f2_and_truncates_the_top_of_the_band():  # risk 2; the ruling on Task 5
    (r,) = fitted(ringing([(3.02e9, 232, [0.1])]))  # as P_pp's TM21, near 3.2 GHz, past f_max 3 GHz
    assert abs(r["f_hz"] - EXC["f2"]) <= 2 / SPAN
    assert r["factor"] == pytest.approx(np.exp(-np.pi * 3.02e9 * 31e-9 / 232), rel=0.10)  # 0.28: the slope fixes f/Q
    assert truncated(np.array([2.9e9]), [r]).all()  # within 50·f/Q, 651 MHz, of 3.02 GHz


def test_a_ring_just_below_f1_is_fitted_at_f1_and_its_neighbour_keeps_its_q():  # risk 2; the ruling on Task 5
    a, b = fitted(ringing([(1.38e9, 232, [0.1]), (2.0e9, 895, [0.1])]))  # A missed has no column in the joint fit
    assert abs(a["f_hz"] - EXC["f1"]) <= 2 / SPAN
    assert b["q"] is not None and b["q"] == pytest.approx(895, rel=0.10)


@pytest.mark.parametrize("qs", [(232, 895), (895, 232)])  # the larger factor at either port
def test_a_ring_at_two_ports_keeps_the_larger_factor_of_its_two_fits(qs):  # BC6: the worst over the ports
    (r,) = fitted(ringing([(2e9, qs[0], [0.1, 0]), (2e9, qs[1], [0, 0.1])], ports=2))  # one f, another Q per port
    assert r["factor"] == pytest.approx(np.exp(-np.pi * 2e9 * 31e-9 / 895), rel=0.10)  # 0.80, not Q 232's 0.43
