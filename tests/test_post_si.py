# SPDX-License-Identifier: GPL-3.0-or-later
import math

import numpy as np
import pytest
from scipy.constants import c as C0

from kicad_rf_studio.core.post.si import (LEAD, LOCAL_RISE, N_TDR, rise_filter, step_response, tdr,
                                          uniform_grid)
from p4a import cohn, even_odd_s

F, TR = uniform_grid(10e9), LOCAL_RISE / 10e9  # the presets' band and its localising rise time, 125 ps
TAU = 50e-3 * 2.0 / C0  # one way along 50 mm at εeff 4: 0.334 ns
GAMMA = 10 / 110  # a 60 Ω line's step from 50 Ω


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
