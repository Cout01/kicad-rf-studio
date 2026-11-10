# SPDX-License-Identifier: GPL-3.0-or-later
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import shapely
from scipy.constants import c
from scipy.optimize import brentq
from scipy.special import j0, j1, jnp_zeros, y0, y1
from shapely.geometry import Point, Polygon, box

from kicad_rf_studio.core import cavity
from kicad_rf_studio.core.cavity import cavities, marks, narrow_slot, solve
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.board import CopperArea

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


def shorted_circle(r, big=25.0):  # Hz: the root of J0'(kR)·Y0(kr) − Y0'(kR)·J0(kr), k in 1/mm
    def g(k):
        return -j1(k * big) * y0(k * r) + y1(k * big) * j0(k * r)

    k = brentq(g, 1e-6 / big, jnp_zeros(0, 1)[0] / big)  # the post mode lies under the first m = 0 Neumann root
    return k * 1e3 * c / (2 * math.pi * math.sqrt(EPS))


@pytest.mark.parametrize("r", [0.1, 0.15, 0.2])
def test_e_e3_a_centre_post_matches_the_shorted_circle_and_leaves_no_dc_mode(r):  # design 5.12 E-E (3)
    # (0.125, 0.125) is a cell centre: (0, 0) is a cell corner, four cells tied; 0.18 mm off the axis moves the
    # post mode by O((k·0.18)²), far under the tolerance
    f = solve(Point(0, 0).buffer(25.0, quad_segs=256), EPS, 2e9, posts=[((0.125, 0.125), r)]).f
    assert f[0] > 1e6 and f[0] == pytest.approx(shorted_circle(r), rel=1e-2)


@pytest.mark.parametrize("at", [(0.125, 0.125), (0.0, 0.0)])  # a cell centre; a cell corner
@pytest.mark.parametrize("r", [0.25, 0.3, 0.5, 1.0])
def test_a_post_of_r_at_or_over_h_is_its_discs_cells_within_7_percent(r, at):  # design 5.4: r >= h, the disc
    f = solve(Point(0, 0).buffer(25.0, quad_segs=256), EPS, 2e9, posts=[(at, r)]).f
    assert f[0] > 1e6 and abs(f[0] / shorted_circle(r) - 1) <= 0.07  # probed down to -6.2 %: I_LIMIT_CAVITY states it


SHAPE = Polygon([(0, 0), (40, 0), (40, 10), (25, 10), (25, 30), (0, 30)])  # vertices on the grid's lines
POSTS = [((5.1, 4.3), 0.15), ((30.2, 5.6), 0.15), ((12.7, 22.1), 0.2)]  # no centre tie


@pytest.mark.parametrize("move", [lambda xy: xy * (-1, 1), lambda xy: xy[:, ::-1] * (-1, 1)])  # mirror; quarter turn
def test_e_e4_the_mirror_and_the_quarter_turn_give_identical_lists(move):  # design 5.12 E-E (4), with posts
    f = solve(SHAPE, EPS, 6e9, posts=POSTS).f
    moved = [(tuple(move(np.array([xy]))[0]), r) for xy, r in POSTS]
    g = solve(shapely.transform(SHAPE, move), EPS, 6e9, posts=moved).f
    assert f[0] > 1e6  # the posts hold: no DC mode
    assert len(g) == len(f) and np.allclose(g, f, rtol=1e-9, atol=0)


H5 = 50 / 201  # x = 25 is a cell centre, so (1,0)'s nodal line holds the post


def post_at(x):
    return solve(box(0, 0, 50, 30), EPS, 3e9, posts=[((x, 15.0), 0.15)], h=H5).f


def test_e_e5_the_post_on_the_nodal_line_mirrored_posts_and_the_post_mode_toward_the_antinode():  # E-E (5)
    assert np.min(np.abs(post_at(25.0) / (UNIT / 0.05) - 1)) <= 1e-3  # f10 kept within 0.1 %
    for x in (20.0, 12.5):
        assert np.allclose(post_at(50 - x), post_at(x), rtol=1e-9, atol=0)
    assert post_at(25.0)[0] > post_at(20.0)[0] > post_at(12.5)[0]  # strictly lower toward x = 0


def test_past_cells_max_or_mem_max_the_grid_coarsens(monkeypatch):  # design 5.4: past about 1.5 M cells
    monkeypatch.setattr(cavity, "CELLS_MAX", 10_000)  # 50 × 30 mm: 24 000 cells at 0.25 mm, 6 000 at 0.5 mm
    assert solve(box(0, 0, 50, 30), EPS, 3e9).h == 0.5 and solve(box(0, 0, 20, 20), EPS, 3e9).h == 0.25
    monkeypatch.setattr(cavity, "CELLS_MAX", 1_500_000)
    monkeypatch.setattr(cavity, "MEM_MAX", 2e6)  # 24 000 cells × (2k + 1) Lanczos vectors × 8 B; k about 13
    assert solve(box(0, 0, 50, 30), EPS, 3e9).h == 0.5


def test_a_slot_under_0_5_mm_is_named_and_holes_and_corners_are_not():  # design 5.4 guards
    plane = box(0, 0, 50, 30)
    assert narrow_slot(plane.difference(box(20, 10, 30, 10.3)))
    assert not narrow_slot(plane.difference(box(20, 10, 30, 10.6)))
    assert not narrow_slot(plane.difference(box(5, 5, 7, 7)).difference(Point(20, 20).buffer(0.4)))
    assert not narrow_slot(Polygon([(0, 0), (50, 0), (50, 25), (25, 25), (25, 50), (0, 50)]))


def test_marks_hold_the_window_the_fundamental_a_clocks_tenth_harmonic_and_never_dc():  # design 5.4
    assert marks(1.83e9 * 1.04, 915e6, ()) == [{"of": "carrier", "f_hz": 915e6, "n": 2}]
    assert marks(1.83e9 * 1.06, 915e6, ()) == []
    assert marks(950e6, 915e6, ()) == [{"of": "carrier", "f_hz": 915e6, "n": 1}]
    assert marks(30e9, 1e9, ()) == [{"of": "carrier", "f_hz": 1e9, "n": 30}]  # the carrier is never suppressed
    assert marks(400e6, None, (40e6,)) == [{"of": "clock", "f_hz": 40e6, "n": 10}]
    assert marks(440e6, None, (40e6,)) == []  # n 11: adjacent windows overlap
    assert marks(0.0, 915e6, (40e6,)) == []
    assert marks(1.83e9, 915e6, (61e6,)) == [{"of": "carrier", "f_hz": 915e6, "n": 2}]  # 61 MHz: n 30, suppressed


FIX = Path(__file__).parent / "fixtures"


def board(name):
    return load_board(FIX / f"{name}.kicad_pcb")


def pairs(b):
    return cavities(b, zstack(b.stackup, b.copper_layers))


def test_usb2_hs_holds_one_gnd_3v3_cavity_between_in1_and_in2_with_no_post():  # design 5.4; r2 §3's table
    (cav,) = pairs(board("usb2_hs"))
    assert (cav.layers, cav.nets, cav.posts) == (("In1.Cu", "In2.Cu"), (("GND",), ("+3V3",)), ())
    assert (cav.d, cav.eps_r) == (pytest.approx(1.04), pytest.approx(4.5))
    assert cav.region.area == pytest.approx(413.5, rel=0.02)


def test_lpf915s_stitched_gnd_pair_gets_a_post_at_each_via_and_plated_pad_joining_its_layers():  # design 5.4
    cav = max((c for c in pairs(board("lpf915")) if c.layers == ("F.Cu", "B.Cu")), key=lambda c: c.region.area)
    assert cav.nets == (("GND",), ("GND",)) and len(cav.posts) == 36
    assert cav.region.area == pytest.approx(582.7, rel=0.02)


def test_emc_reviews_in1_in2_pair_is_a_postless_gnd_3v3_cavity_and_a_gnd_rim_with_one_post():  # ruling 3
    b = board("emc_review")
    inner = [c for c in pairs(b) if c.layers == ("In1.Cu", "In2.Cu")]
    assert [c.nets for c in inner] == [(("GND",), ("+3V3",)), (("GND",), ("GND",))]  # nothing else: no third region
    main, rim = inner
    assert main.posts == () and main.region.area == pytest.approx(1697.5, rel=0.02)  # fence vias pass antipads
    assert not main.region.contains(Point(137, -137))  # SH1's ring: In2.Cu bare inside it (plan 1's carried minor)
    tie = next(v for v in b.vias if v.at == (109.0, -119.0))  # the island's tie (make_fixtures.emc_review)
    assert rim.posts == ((tie.at, tie.drill / 2),) and rim.region.area == pytest.approx(80.0, rel=0.02)


def test_a_pair_faces_only_where_no_layer_between_has_copper_and_takes_the_series_eps():  # design 5.4
    b = board("usb2_hs")
    full = [CopperArea(layer, "GND", b.outline, "zone", layer) for layer in ("F.Cu", "B.Cu")]
    found = pairs(replace(b, areas=b.areas + full))
    assert [c.layers for c in found] == [("F.Cu", "In1.Cu"), ("F.Cu", "B.Cu"), ("In1.Cu", "In2.Cu"),
                                         ("In2.Cu", "B.Cu")]
    between = shapely.union_all([a.polygon for a in b.areas if a.layer in ("In1.Cu", "In2.Cu")])
    ring = b.outline.area - between.intersection(b.outline).area  # F faces B only where In1 and In2 stop short
    assert found[1].region.area == pytest.approx(ring, rel=0.02)  # about 51 mm²
    (outer,) = pairs(replace(b, areas=full))  # In1 and In2 bare: F.Cu faces B.Cu through both dielectrics
    slabs = [s for s in zstack(b.stackup, b.copper_layers) if s.kind == "dielectric"]
    d = sum(s.z1 - s.z0 for s in slabs)
    assert outer.d == pytest.approx(d) and outer.eps_r == pytest.approx(d / sum((s.z1 - s.z0) / s.eps_r for s in slabs))


@pytest.mark.parametrize(("side", "count"), [(4.0, 0), (5.0, 1)])  # 16 and 25 mm²
def test_cavities_under_20_mm2_are_dropped(side, count):  # design 5.4
    b = board("usb2_hs")
    x, y = b.outline.centroid.coords[0]
    patch = CopperArea("F.Cu", "GND", box(x, y, x + side, y + side), "zone", "p")
    assert sum(c.layers == ("F.Cu", "In1.Cu") for c in pairs(replace(b, areas=b.areas + [patch]))) == count
