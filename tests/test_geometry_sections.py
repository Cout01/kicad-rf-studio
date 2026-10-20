# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from kicad_rf_studio.core.geometry.copper import SIMPLIFY, copper_pieces
from kicad_rf_studio.core.geometry.mask import mask_model, smeared_epsilon
from kicad_rf_studio.core.geometry.sections import cross_section, sections
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import load_board

FIX = Path(__file__).parent / "fixtures"
T = {"F.Cu": .035, "B.Cu": .035}
BIG = box(-1000, -1000, 1000, 1000)  # a crop that holds every test board


def pieces_of(b):
    return copper_pieces(b, BIG, T)[0]


def coupon(name):
    """`name`'s board, its pieces over BIG, its z-stack and its F mask."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    pieces, zs = pieces_of(b), zstack(b.stackup, b.copper_layers)
    return b, pieces, zs, mask_model(b, pieces, zs, BIG, "F")


def test_gcpw_section():
    s, w = sections(b := load_board(FIX / "coupon_gcpw.kicad_pcb"), ("LINE",), pieces_of(b))
    assert len(s) == 1 and not w
    assert (s[0].axis, s[0].layer) == ("x", "F.Cu")
    assert (s[0].width, s[0].length) == pytest.approx((0.6, 20.0), abs=1e-6)
    assert s[0].gap == pytest.approx(0.15, abs=1e-3)  # R-P2-5: KiCad's zone fill leaves 0.1505 mm


def test_microstrip_section_has_no_gap():
    s, _ = sections(b := load_board(FIX / "coupon_ms.kicad_pcb"), ("LINE",), pieces_of(b))
    assert s[0].width == pytest.approx(1.35) and s[0].gap is None


def test_diagonal_net_has_no_sections():
    s, w = sections(b := load_board(FIX / "coupon_gcpw_45.kicad_pcb"), ("LINE",), pieces_of(b))
    assert s == [] and ("W_STAIRCASED", {"net": "LINE"}) in w


def test_arc_coupon_keeps_straight_parts():  # coupon_gcpw_arc: two straights either side of the arc
    s, w = sections(b := load_board(FIX / "coupon_gcpw_arc.kicad_pcb"), ("LINE",), pieces_of(b))
    assert len(s) == 2 and ("W_STAIRCASED", {"net": "LINE"}) in w


def test_cross_section_layers():
    # R-P2-5: the mask-present cut uses coupon_gcpw_masked; coupon_gcpw opens the mask over its whole board
    b, pieces, zs, mask = coupon("coupon_gcpw_masked")
    s, _ = sections(b, ("LINE",), pieces)
    cs = cross_section(s[0], pieces, zs, mask, "exact")
    sig = [r for r in cs.conductors if r.role == "signal"]
    # Task 6 ruling: the cut is through the pieces, whose 10 µm simplification tilts LINE's top edge: 0.599279 here
    assert len(sig) == 1 and sig[0].x1 - sig[0].x0 == pytest.approx(0.6, abs=1e-3)
    assert sig[0].z1 - sig[0].z0 == pytest.approx(0.035)
    assert any(r.eps_r == pytest.approx(3.3) for r in cs.dielectrics)  # mask present
    assert not any(r.eps_r == pytest.approx(3.3) for r in cross_section(s[0], pieces, zs, None, "none").dielectrics)


# --- beyond the brief's five tests -------------------------------------------------------------


def test_runs_merge_by_width_and_gap_is_the_nearer_copper(mini_board):
    # LINE along x: two touching 0.5 mm runs merge, a 0.3 mm run and a separate run do not; a run along y; a 45°
    # segment and an arc give one warning. GND tracks 0.5 mm from the first run and from the y run, 2.5 mm on the far
    # side of the first: the gap is the nearer one, measured across the cut at the midpoint, on the pieces, whose
    # simplification moves a round-capped track's straight edge by a micrometre or two (0.501801 for the y run)
    seg = '(segment (start {} {}) (end {} {}) (width {}) (layer "F.Cu") (net "{}") (uuid "s{}"))'
    runs = [(0, 0, 5, 0, .5, "LINE"), (5, 0, 10, 0, .5, "LINE"), (10, 0, 12, 0, .3, "LINE"), (14, 0, 16, 0, .5, "LINE"),
            (16, 0, 17, 1, .5, "LINE"), (20, 1, 20, 4, .5, "LINE"),
            (0, 1, 10, 1, .5, "GND"), (0, -3, 10, -3, .5, "GND"), (21, 1, 21, 4, .5, "GND")]
    arc = '(arc (start 30 0) (mid 31 1) (end 32 0) (width 0.5) (layer "F.Cu") (net "LINE") (uuid "a"))'
    b = mini_board("".join(seg.format(*r, i) for i, r in enumerate(runs)) + arc)
    s, w = sections(b, ("LINE",), pieces_of(b))
    assert [(x.axis, x.start, x.end, x.width, x.length) for x in s] == [
        ("x", (0.0, 0.0), (10.0, 0.0), .5, 10.0), ("x", (10.0, 0.0), (12.0, 0.0), .3, 2.0),
        ("x", (14.0, 0.0), (16.0, 0.0), .5, 2.0), ("y", (20.0, -4.0), (20.0, -1.0), .5, 3.0)]
    assert [x.gap for x in s] == pytest.approx([0.5, None, None, 0.5], abs=SIMPLIFY)
    assert w == [("W_STAIRCASED", {"net": "LINE"})]


def test_cross_section_cuts_every_conductor_and_places_the_mask():
    b, pieces, zs, mask = coupon("coupon_gcpw_masked")
    (sec,), _ = sections(b, ("LINE",), pieces)
    exact, smeared = (cross_section(sec, pieces, zs, mask, mode, dz0=0.025) for mode in ("exact", "smeared"))
    # the cut at x = 110 across y: the line, the F.Cu pours 0.1505 mm either side and the B.Cu plane, all ground but
    # the line (its top edge 0.7 µm low, as in test_cross_section_layers); the box (Task 6 ruling) runs 10 h past the
    # line's edges and past the stack, h = 0.71
    got = sorted((r.role, r.x0, r.x1, r.z0, r.z1) for r in exact.conductors)
    assert [g[0] for g in got] == ["ground", "ground", "ground", "signal"]
    assert np.array([g[1:] for g in got]) == pytest.approx(np.array([
        (-104.4995, -100.4505, 0.745, 0.78), (-104.4995, -95.5005, 0.0, 0.035), (-99.5495, -95.5005, 0.745, 0.78),
        (-100.3, -99.7, 0.745, 0.78)]), abs=1e-3)
    assert exact.box == pytest.approx((-107.4, -92.6, -7.11, 7.89))
    # the substrate spans the box; the mask fills the gaps over F.Cu's z-cell and coats the board above it, t_m thick
    # (exact) or smeared over dz0 (smeared)
    assert (-107.4, -92.6, 0.035, 0.745, 4.5) in [(r.x0, r.x1, r.z0, r.z1, r.eps_r) for r in exact.dielectrics]
    fill = sorted((r.x0, r.x1) for r in exact.dielectrics if (r.z0, r.z1, r.eps_r) == (0.745, 0.78, 3.3))
    assert np.array(fill) == pytest.approx(np.array(
        [(-105.0, -104.4995), (-100.4505, -100.3), (-99.7, -99.5495), (-95.5005, -95.0)]), abs=1e-3)
    assert [(r.x0, r.x1, r.z0, r.z1, r.eps_r) for r in exact.dielectrics if r.z0 == 0.78] == [
        (-105.0, -95.0, 0.78, 0.79, 3.3)]
    coat = [r for r in smeared.dielectrics if r.z0 == 0.78]
    assert [(r.x0, r.x1, r.z1) for r in coat] == [(-105.0, -95.0, 0.805)]
    assert coat[0].eps_r == pytest.approx(smeared_epsilon(0.01, 3.3, 0.025))
    assert sorted((r.x0, r.x1) for r in smeared.dielectrics if (r.z0, r.z1) == (0.745, 0.78)) == fill
    # on B the coat runs down from B.Cu's outer face (Task 5 ruling), and the fill takes B.Cu's z-cell
    back = cross_section(sec, pieces, zs, mask_model(b, pieces, zs, BIG, "B"), "smeared", dz0=0.025)
    assert {(r.z0, r.z1) for r in back.dielectrics if r.eps_r != 4.5} == {(-0.025, 0.0), (0.0, 0.035)}
