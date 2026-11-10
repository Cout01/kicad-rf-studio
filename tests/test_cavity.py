# SPDX-License-Identifier: GPL-3.0-or-later
import math

import numpy as np
import pytest
import shapely
from scipy.constants import c
from scipy.special import jnp_zeros
from shapely.geometry import Point, Polygon, box

from kicad_rf_studio.core.cavity import solve

EPS = 4.4
UNIT = c / (2 * math.sqrt(EPS))  # Hz·m: f_mn = UNIT·√((m/a)² + (n/b)²)


def rectangle_modes(a_mm, b_mm, f_max):
    a, b = a_mm / 1e3, b_mm / 1e3
    return sorted(f for m in range(20) for n in range(20)
                  if (m, n) != (0, 0) and (f := UNIT * math.hypot(m / a, n / b)) <= f_max)


@pytest.mark.parametrize("angle", [0, 30])
def test_e_e1_the_rectangle_matches_f_mn_aligned_and_rotated(angle):  # design 5.12 E-E (1)
    f = solve(shapely.affinity.rotate(box(0, 0, 50, 30), angle, origin=(0, 0)), EPS, 6e9).f
    exact = rectangle_modes(50, 30, 6e9)
    assert len(exact) == 11 and len(f) == 12 and (f < 1e6).sum() == 1  # every mode to 6 GHz, one DC mode
    assert f[0] == 0.0  # the static mode carries no round-off into the goldens
    assert np.allclose(f[1:], exact, rtol=5e-3, atol=0)


def test_cut_faces_keep_the_rotated_rectangle_within_0_1_percent():  # Review Focus 1: faces taken as 1 read 0.44 % off
    f = solve(shapely.affinity.rotate(box(0, 0, 50, 30), 30, origin=(0, 0)), EPS, 6e9).f
    assert np.allclose(f[1:], rectangle_modes(50, 30, 6e9), rtol=1e-3, atol=0)  # r2 measured 0.013 %


def test_e_e2_the_circle_matches_bessels_x_prime_over_its_first_six_modes():  # design 5.12 E-E (2)
    r_m, f_max = 25e-3, 5e9
    roots = [(x, 1 if m == 0 else 2) for m in range(8) for x in jnp_zeros(m, 3)]  # J_m'(x) = 0, m > 0 twice
    exact = sorted(f for x, k in roots for f in [x * c / (2 * math.pi * r_m * math.sqrt(EPS))] * k if f <= f_max)
    assert len(set(np.round(exact))) == 6  # the first six distinct modes
    f = solve(Point(0, 0).buffer(25, quad_segs=256), EPS, f_max).f
    assert f[0] == 0.0 and (f < 1e6).sum() == 1 and np.allclose(f[1:], exact, rtol=5e-3, atol=0)


def test_e_e6_the_l_shapes_first_mode_differences_shrink_at_least_2x_per_halving():  # design 5.12 E-E (6)
    ell = Polygon([(0, 0), (50, 0), (50, 25), (25, 25), (25, 50), (0, 50)])
    d = np.abs(np.diff([solve(ell, EPS, 2e9, h=h).f[1] for h in (1.0, 0.5, 0.25, 0.125)]))
    assert d[1] <= d[0] / 2 and d[2] <= d[1] / 2  # self-convergence only: no remembered value


def test_a_slot_between_two_cell_centres_cuts_their_link():  # r2 §2 detail 2
    plane = box(0, 0, 50, 50)
    slotted = plane.difference(box(24.3, -1, 24.45, 40))  # 0.15 mm wide, between the centres 24.25 and 24.75
    assert solve(slotted, EPS, 3e9, h=0.5).f[1] < 0.6 * solve(plane, EPS, 3e9, h=0.5).f[1]  # the slot mode


@pytest.mark.parametrize(("side", "dc"), [(0.8, 1), (2.0, 2)])
def test_islands_under_1_mm2_are_dropped(side, dc):  # design 5.4 guards
    f = solve(box(0, 0, 50, 30).union(box(60, 0, 60 + side, side)), EPS, 3e9).f
    assert (f < 1e6).sum() == dc and (f[:dc] == 0.0).all()


def test_two_solves_give_the_same_bits():  # ARPACK's start vector is fixed
    assert np.array_equal(solve(box(0, 0, 50, 30), EPS, 6e9).f, solve(box(0, 0, 50, 30), EPS, 6e9).f)
