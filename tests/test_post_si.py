# SPDX-License-Identifier: GPL-3.0-or-later
import math
import subprocess
import sys

import numpy as np
import pytest
from scipy.constants import c as C0

from kicad_rf_studio.core.post.si import (ARRIVAL_FLOOR, COPPER_RHO, FLOOR_DB, LEAD, LOCAL_RISE, N_TDR, SE_OHM,
                                          Reading, arrival, distance_mm, hammerstad, levels, mixed_mode, read,
                                          rise_filter, step_response, tdr, uniform_grid)
from p4a import cohn, even_odd_s
from test_project import si_dict

F, TR = uniform_grid(10e9), LOCAL_RISE / 10e9  # the presets' band and its localising rise time, 125 ps
TAU = 50e-3 * 2.0 / C0  # one way along 50 mm at εeff 4: 0.334 ns
GAMMA = 10 / 110  # a 60 Ω line's step from 50 Ω
SE = {"target_ohm": 50.0, "tolerance": 0.1, "f_max_hz": 10e9, "rise_s": 1e-9, "marker_hz": 133e6, "pair": None,
      "dielectric": "lossless",
      "lines": [{"role": "measured", "chain": {"start": "A1.1", "end": "A2.1", "nets": ["SIG"], "series": [],
                                                "shunt": []}}]}  # a se50 net, as si_lines reads one
P100 = {**si_dict(), "target_ohm": 100.0}  # usb2_hs's pair and victim at 100 Ω: 50 Ω a leg, nothing renormalised
P2V = {**P100, "lines": [*P100["lines"], {"role": "victim", "chain": {"start": "TP3.1", "end": "TP4.1",
                                                                         "nets": ["AUX2"], "series": [],
                                                                         "shunt": []}}]}  # design 3: a second victim
ROUTE1 = [(50.0, 4.0, 15.0), (60.0, 4.0, 30.0), (50.0, 4.0, 15.0), (40.0, 4.0, 3.0), (50.0, 4.0, 15.0)]  # Z, εeff, mm
NECK = [(90.0, 3.0, 30.0), (110.0, 3.0, 5.0), (90.0, 3.0, 30.0)]  # design 5.6: a 5 mm neck-down from 90 to 110 Ω


def line_s(sections, f, z0=50.0):
    """S (F, 2, 2) at z0 of lossless lines in cascade, each (Z in Ω, εeff, length in mm), from their ABCD matrices."""
    a, b, c, d = (np.ones(len(f), complex), np.zeros(len(f), complex), np.zeros(len(f), complex),
                  np.ones(len(f), complex))
    for z, eps, length in sections:
        th = 2 * np.pi * f * length * 1e-3 * math.sqrt(eps) / C0
        a, b, c, d = (a * np.cos(th) + b * 1j * np.sin(th) / z, a * 1j * z * np.sin(th) + b * np.cos(th),
                      c * np.cos(th) + d * 1j * np.sin(th) / z, c * 1j * z * np.sin(th) + d * np.cos(th))
    den = a + b / z0 + c * z0 + d
    s11, s21, s22 = (a + b / z0 - c * z0 - d) / den, 2 / den, (-a + b / z0 - c * z0 + d) / den
    return np.stack([np.stack([s11, s21], -1), np.stack([s21, s22], -1)], -2)


def pair6(next_a=0.0, fext_a=0.0, tau_n=0.2e-9):
    """S (F, 6, 6) at 50 Ω of a pair's two matched legs (P 0.2 ns, N tau_n) and a matched victim, in SI's port order,
    the victim's start coupled to P's start by next_a and its end by fext_a."""
    s = np.zeros((len(F), 6, 6), complex)
    for (i, j), tau in (((0, 2), 0.2e-9), ((1, 3), tau_n), ((4, 5), 0.2e-9)):
        s[:, i, j] = s[:, j, i] = np.exp(-2j * np.pi * F * tau)
    s[:, 4, 0] = s[:, 0, 4] = next_a
    s[:, 5, 0] = s[:, 0, 5] = fext_a
    return s


def pair8(next2=0.01, fext2=0.005):
    """pair6(0.05, 0.02) with a second matched victim on ports 7 and 8, coupled to P's start by next2 and its end by
    fext2: P2V's ports."""
    s = np.zeros((len(F), 8, 8), complex)
    s[:, :6, :6] = pair6(0.05, 0.02)
    s[:, 6, 7] = s[:, 7, 6] = np.exp(-2j * np.pi * F * 0.2e-9)
    s[:, 6, 0] = s[:, 0, 6] = next2
    s[:, 7, 0] = s[:, 0, 7] = fext2
    return s


def test_a_homogeneous_striplines_4port_has_no_fext_and_its_next_peaks_at_k():  # design 5.11: P4-A, to 1e-9
    ze, zo = cohn(0.15, 0.15, 0.5, 4.3)
    fq = C0 / (4 * 50e-3 * math.sqrt(4.3))  # the quarter wave
    s = even_odd_s(ze, 4.3, zo, 4.3, 50.0, np.r_[np.linspace(0, 3 * fq, 301), fq], math.sqrt(ze * zo))
    k = (ze - zo) / (ze + zo)
    assert np.abs(s[:, 0, 3]).max() <= 1e-9 and np.abs(s[:, 0, 0]).max() <= 1e-9  # FEXT and S11
    assert abs(abs(s[-1, 0, 1]) - k) <= 1e-9 and np.abs(s[:, 0, 1]).max() <= k + 1e-9  # NEXT's peak
    assert np.abs(s - s.transpose(0, 2, 1)).max() <= 1e-15  # reciprocal
    assert np.abs(np.einsum("fij,fkj->fik", s, s.conj()) - np.eye(4)).max() <= 1e-9  # lossless


def test_a_lines_reflection_is_the_bounce_series_of_its_steps_gamma():  # design 5.11: P4-A, to 1e-9
    f = np.linspace(0, 10e9, 401)
    s = even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, f)  # no coupling: each leg a 60 Ω line between 50 Ω ports
    th = 2 * np.pi * f * TAU
    x = np.exp(-2j * th)
    assert np.abs(s[:, 0, 0] - GAMMA * (1 - x) / (1 - GAMMA ** 2 * x)).max() <= 1e-9
    assert np.abs(s[:, 0, 2] - (1 - GAMMA ** 2) * np.exp(-1j * th) / (1 - GAMMA ** 2 * x)).max() <= 1e-9
    assert np.abs(s[:, 0, 1]).max() == np.abs(s[:, 0, 3]).max() == 0.0


def test_the_tdr_reads_an_ideal_60_ohm_line_as_60_then_50():  # design 5.6, 5.11
    t, z = tdr(even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F)[:, 0, 0], F, TR)
    assert round(float(np.interp(TAU, t, z)), 1) == 60.0  # mid-line: 59.999
    late = (t >= 4 * TAU + 4 * TR) & (t <= 20e-9)  # past the second round trip; until then 50.075 Ω, the line's Γ³
    assert set(np.round(z[late], 1).tolist()) == {50.0}


def test_the_tdrs_sum_starts_before_t_0():  # Review Focus 2: r1's first version read half the step, 55 Ω
    t, rho = step_response(even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F)[:, 0, 0], F, TR)
    assert t[0] <= -LEAD * TR and abs(rho[0]) <= 1e-5  # quiet before the filter's impulse, centred on t = 0
    assert float(np.interp(TAU, t, rho)) == pytest.approx(GAMMA, rel=1e-3)  # the whole step, not half of it


def test_the_tdr_needs_a_uniform_grid_from_dc():  # Review Focus 2
    for f in (np.array([1e9, 2e9, 3e9]), np.array([0.0, 1e9, 3e9])):
        with pytest.raises(ValueError, match="uniform grid from DC"):
            step_response(np.zeros(3), f, TR)
    assert len(F) == N_TDR + 1 and F[[0, 1, -1]].tolist() == [0.0, 5e6, 10e9]
    assert 20 * math.log10(rise_filter(np.array([10e9]), TR)[0]) == pytest.approx(-40.78, abs=0.01)  # design 5.1
    assert rise_filter(np.array([0.0]), TR)[0] == 1.0


def test_mixed_mode_of_an_ideal_coupled_pair_is_matched_in_its_modes():  # design 5.5: se2gmm at the target
    ze, ee, zo, eo, length = 60.0, 3.3, 45.0, 2.9, 30.0  # a 90 Ω pair, its common mode at 30 Ω
    m = mixed_mode(even_odd_s(ze, ee, zo, eo, length, F), F, 90.0, True)  # the 4-port at 50 Ω a port
    leg = even_odd_s(ze, ee, zo, eo, length, F, 45.0)  # each leg at 45 Ω: 90 Ω differential, 22.5 Ω common
    th = 2 * np.pi * F * length * 1e-3 * math.sqrt(eo) / C0
    assert np.abs(m[:, 0, 0]).max() <= 1e-12 and np.abs(m[:, 1, 0] - np.exp(-1j * th)).max() <= 1e-12  # Sdd
    assert np.abs(m[:, 2, 2] - leg[:, 0, 0] - leg[:, 0, 1]).max() <= 1e-12  # Scc11: the even mode's Γ at 45 Ω
    assert np.abs(m[:, 3, 2] - leg[:, 0, 2] - leg[:, 0, 3]).max() <= 1e-12  # Scc21
    assert np.abs(m[:, 2:, :2]).max() <= 1e-12 and np.abs(m[:, :2, 2:]).max() <= 1e-12  # a symmetric pair converts none
    o = [0, 2, 1, 3]  # a 60 Ω line and an uncoupled victim in a net's order: start, end, the victim's start and end
    s4 = even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F)[:, o][:, :, o]
    net = mixed_mode(s4, F, 60.0, False)
    th = 2 * np.pi * F * 50e-3 * 2.0 / C0
    assert np.abs(net[:, 0, 0]).max() <= 1e-6 and np.abs(net[:, 1, 0] - np.exp(-1j * th)).max() <= 1e-6
    assert np.abs(net[:, 2:, :2]).max() == 0.0  # no coupling made
    assert np.abs(net[:, 2:, 2:] - s4[:, 2:, 2:]).max() <= 1e-6  # the victim's ends stay at 50 Ω (renormalize: 3.6e-8)


def test_the_crosstalk_peaks_follow_the_even_odd_4port():  # design 5.6; P4-A's identities
    ze, zo = 62.5, 40.0  # √(Ze·Zo) = 50 Ω: a homogeneous stripline's 4-port at 50 Ω has no S11 and no FEXT
    o = [0, 2, 1, 3]
    (next_db, next_hz, fext_db, _), = read(even_odd_s(ze, 4.0, zo, 4.0, 30.0, F)[:, o][:, :, o], F, SE, 4.0).xt
    assert next_db == pytest.approx(20 * math.log10((ze - zo) / (ze + zo)), abs=1e-5) and next_hz == 6.245e9
    assert fext_db == FLOOR_DB  # exactly none: the floor, never -inf with a warning
    xt = read(pair6(next_a=0.05), F, P100, 3.0).xt
    assert xt[0][0] == pytest.approx(20 * math.log10(0.05 / math.sqrt(2)), abs=1e-9)  # driven differentially: half
    two = read(pair8(), F, P2V, 3.0).xt  # the second victim at m's ports 6 and 7
    assert [(round(x[0], 4), round(x[2], 4)) for x in two] == [(-29.0309, -36.9897), (-43.0103, -49.0309)]


def test_the_tdt_arrives_at_half_its_peak_and_the_skew_is_the_legs_difference():  # design 5.6, 6
    t, step = step_response(even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F, 60.0)[:, 2, 0], F, TR)  # a matched line
    assert arrival(t, step) == pytest.approx(TAU - (t[1] - t[0]) / 2, abs=0.05e-12)  # the sum's half sample
    assert arrival(t, 0.9 * ARRIVAL_FLOOR * step) is None  # nothing passes
    p, n = read(pair6(tau_n=0.2137e-9)[:, :4, :4], F, P100, 3.0).skew
    assert n - p == pytest.approx(13.7e-12, abs=0.01e-12)


def test_the_levels_between_the_launches_and_the_short_features():  # design 5.6; anti-goal 2; Review Focus 2, 3
    s = line_s(ROUTE1, F)
    t, z = tdr(s[:, 0, 0], F, TR)
    t_far = 2 * arrival(t, step_response(s[:, 1, 0], F, TR)[1])
    low, high = levels(t, z, TR, t_far, 50.0, SE_OHM)
    assert (low[0], round(low[1], 2), low[2]) == (pytest.approx(818.75e-12), 46.68, True)  # 3 mm of 40 Ω: no level
    assert (high[0], round(high[1], 2), high[2]) == (pytest.approx(431.25e-12), 60.0, False)  # 30 mm of 60 Ω
    neck = read(line_s(NECK, F), F, {**SE, "target_ohm": 90.0}, 3.0).levels
    assert (round(neck[1][1], 2), neck[1][2], neck[0][2]) == (98.45, True, False)  # about 8 Ω high, not 20; marked
    off = read(line_s([(96.0, 3.0, 30.0), (110.0, 3.0, 5.0), (96.0, 3.0, 30.0)], F), F, {**SE, "target_ohm": 90.0},
               3.0).levels[1]  # the neck on a route 6 Ω high, inside the band
    pad = read(line_s([(47.0, 4.0, 30.0), (40.0, 4.0, 3.0), (47.0, 4.0, 30.0)], F), F, SE, 4.0).levels[0]
    assert (round(off[1], 2), off[2], round(pad[1], 2), pad[2]) == (102.02, True, 44.64, True)  # each against its base
    flat = read(line_s([(95.0, 3.2777, 30.405)], F), F, {**SE, "target_ohm": 90.0}, 3.2777)  # usb2_hs's route, 95 Ω
    assert flat.t_far == pytest.approx(361.08e-12, abs=0.01e-12) and [x[2] for x in flat.levels] == [False, False]
    assert levels(t, z, TR, None, 50.0, SE_OHM) is None
    short = read(line_s([(50.0, 4.0, 5.0)], F), F, SE, 4.0)  # a 5 mm route: its round trip under its two launches
    assert short.t_far == pytest.approx(60.47e-12, abs=0.01e-12) and short.levels is None
    assert distance_mm(TR, 4.0) == pytest.approx(9.3685, abs=1e-4)  # t_r·v/2, the resolution length


def test_read_holds_what_the_lines_and_the_deltas_need():  # design 5.6; Review Focus 5
    r = read(pair6(0.05, 0.02), F, P100, 3.0)
    assert isinstance(r, Reading) and (r.marker, r.rise, r.eeff) == (48, (LOCAL_RISE / 10e9, 5e-10), 3.0)
    assert r.m.shape == (len(F), 6, 6) and r.t.shape == r.z.shape == r.z_link.shape == r.tdt.shape == r.tdt_link.shape
    assert r.t_far == pytest.approx(0.4e-9 - (r.t[1] - r.t[0]), abs=0.1e-12)  # twice the thru's arrival
    assert len(r.xt) == 1 and r.skew[0] == r.skew[1]
    n = read(line_s(ROUTE1, F), F, SE, 4.0)
    assert (n.marker, n.skew, n.xt) == (27, None, [])  # 133 MHz on the 5 MHz grid reads at 135 MHz; a net: no skew
    long = read(line_s([(50.0, 4.0, 15.0), (60.0, 4.0, 200.0)], F), F, SE, 4.0)  # the link's on the localising t
    assert abs(long.t[np.argmax(long.z_link > 55)] - long.t[np.argmax(long.z > 55)]) < long.rise[1]  # 25 ps, not 3.5 ns
    assert abs(long.t[np.argmax(long.tdt_link > 0.5)] - long.t[np.argmax(long.tdt > 0.5)]) < long.rise[1]


def test_hammerstads_conductor_loss_is_scikit_rfs():  # design 5.6: Hammerstad, smooth copper
    from skrf.media import MLine
    f = np.array([240e6, 10e9])
    for w, z0 in ((0.3, 51.0), (0.6, 35.0)):  # analyse_loss reads nothing of its instance
        mline = MLine.analyse_loss(None, 4.3, 3.2, 0.0, COPPER_RHO, 1.0, z0, z0, f, w * 1e-3, 35e-6, 0.0)[0]
        assert [hammerstad(x, w, z0) for x in f] == pytest.approx(mline, rel=1e-12)


def test_the_project_and_the_cli_import_neither_scipy_nor_scikit_rf():  # C-5: core.project imports this module
    out = subprocess.run([sys.executable, "-I", "-c", "import sys, kicad_rf_studio.core.project, kicad_rf_studio.cli; "
                          "print(sorted(m for m in ('scipy', 'skrf') if m in sys.modules))"],
                         capture_output=True, text=True)
    assert out.stdout.strip() == "[]"
