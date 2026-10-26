# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString, Point, box

from kicad_rf_studio.core.cs2d import solve
from kicad_rf_studio.core.geometry.copper import SIMPLIFY, copper_pieces
from kicad_rf_studio.core.geometry.mask import mask_model, smeared_epsilon
from kicad_rf_studio.core.geometry.sections import cross_section, sections, staircase_gap
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.mesh.rule import cell_size

FIX = Path(__file__).parent / "fixtures"
T = {"F.Cu": .035, "B.Cu": .035}
BIG = box(-1000, -1000, 1000, 1000)  # a crop that holds every test board
FR4 = '(thickness 0.2) (material "FR4") (epsilon_r 4.3) (loss_tangent 0.02)'
SEG = '(segment (start 5 10) (end 35 10) (width {}) (layer "{}") (net "SIG") (uuid "s")) '


def pieces_of(b):
    return copper_pieces(b, BIG, T)[0]


def four_layer(mini_board_file, body, top=FR4):
    """A mini board of four 35 µm copper layers between three 0.2 mm dielectrics of εr 4.3, the top one given by `top`
    (its properties), and no mask."""
    cu = "(thickness 0.035)"
    layers = [("F.Cu", "copper", cu), ("dielectric 1", "prepreg", top), ("In1.Cu", "copper", cu),
              ("dielectric 2", "core", FR4), ("In2.Cu", "copper", cu), ("dielectric 3", "prepreg", FR4),
              ("B.Cu", "copper", cu)]
    path = mini_board_file(body, stackup="(stackup " + "".join(f'(layer "{n}" (type "{t}") {p})' for n, t, p in layers)
                           + ")")
    text = path.read_text(encoding="utf-8").replace('(2 "B.Cu" signal)', '(2 "B.Cu" signal) (4 "In1.Cu" signal) '
                                                    '(6 "In2.Cu" signal)')
    path.write_text(text, encoding="utf-8")
    return path


def plane(layer):
    """A filled GND zone over the 40 × 20 mm of a mini board's lines, on `layer`."""
    pts = "(pts (xy 0 0) (xy 40 0) (xy 40 20) (xy 0 20))"
    return f'(zone (net "GND") (layer "{layer}") (polygon {pts}) (filled_polygon (layer "{layer}") {pts})) '


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


def test_staircase_gap_is_the_gap_no_section_measures():
    # verifier: the d rule never saw the gap of a net with no axis-aligned run (Review Focus 4)
    b = load_board(FIX / "coupon_gcpw_45.kicad_pcb")
    assert staircase_gap(b, ("LINE",), pieces_of(b)) == pytest.approx(0.1505, abs=1e-3)
    b = load_board(FIX / "coupon_gcpw.kicad_pcb")
    assert staircase_gap(b, ("LINE",), pieces_of(b)) is None  # its one track is a section
    b = load_board(FIX / "coupon_gcpw_arc.kicad_pcb")
    assert staircase_gap(b, ("LINE",), pieces_of(b)) == pytest.approx(0.1505, abs=1e-3)  # the arc's gap


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
    # segment and an arc give one W_STAIRCASED. GND tracks 0.5 mm from the first run and from the y run, 2.5 mm on the
    # far side of the first: the gap is the nearer one, measured across the cut at the midpoint, on the pieces, whose
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


def test_cut_misses_junctions_of_its_own_net_at_the_middle_of_a_run(mini_board):
    # Task 6 fix: the middle of a run can hold a junction of its own net, here the centre node of a T (two collinear
    # 0.5 mm tracks and a stub) and then a 0.6 mm via on a 0.3 mm line. The cut is taken on bare line instead, so the
    # cross-section holds the track alone (not 3.5 mm of stub, nor the via's rings on both layers) and the gap is the
    # design one (0.6, not 0.45 to the via's ring). So too past a 1.2 mm wide patch of the net's copper over 6 of the
    # line's 10 mm: the copper does not change along it, but it is not the track
    seg = '(segment (start {} {}) (end {} {}) (width {}) (layer "F.Cu") (net "{}") (uuid "s{}"))'
    tee = [(0, 0, 5, 0, .5, "LINE"), (5, 0, 10, 0, .5, "LINE"), (5, 0, 5, 3, .5, "LINE"), (0, -1, 10, -1, .5, "GND")]
    line = [(0, 0, 10, 0, .3, "LINE"), (0, -1, 10, -1, .5, "GND")]
    via = '(via (at 5 0) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "LINE") (uuid "v"))'
    patch = '(gr_rect (start 2 -0.6) (end 8 0.6) (stroke (width 0)) (fill yes) (layer "F.Cu") (net "LINE"))'
    zs = zstack(kicad_default(0.8), ("F.Cu", "B.Cu"))
    for rows, extra, width, gap in [(tee, "", .5, .5), (line, via, .3, .6), (line, patch, .3, .6)]:
        b = mini_board("".join(seg.format(*r, i) for i, r in enumerate(rows)) + extra)
        sec = sections(b, ("LINE",), pieces := pieces_of(b))[0][0]
        sig = [r for r in cross_section(sec, pieces, zs, None, "none").conductors if r.role == "signal"]
        assert len(sig) == 1 and sig[0].x1 - sig[0].x0 == pytest.approx(width, abs=2 * SIMPLIFY)
        assert sec.gap == pytest.approx(gap, abs=SIMPLIFY)


def test_cuts_on_lpf915_miss_parts_and_other_tracks():
    # Task 6 fix: three of lpf915's eight run middles land on parts. RF_B's and RF_C's fall on a shunt pad, whose mask
    # opening takes the coat off the line; RF_OUT's falls on the DNP R2, so the cut runs along R2's RF_SMA pad and
    # track, a "ground" 0.457 mm from the line where the pour is 0.1505 mm away on bare line. Every cut is on bare
    # line now: one strip of the track's width, the coat over it, no pad at it
    b, pieces, zs, mask = coupon("lpf915")
    s, _ = sections(b, ("RF_A", "RF_B", "RF_C", "RF_OUT", "RF_SMA", "VDD"), pieces)
    assert len(s) == 8
    for sec in s:
        cs = cross_section(sec, pieces, zs, mask, "exact")
        (sig,) = [r for r in cs.conductors if r.role == "signal"]
        assert sig.x1 - sig.x0 == pytest.approx(sec.width, abs=2 * SIMPLIFY)
        assert any(r.z0 == mask.z_coat0 and r.x0 <= sig.x0 and sig.x1 <= r.x1 for r in cs.dielectrics), sec
    out = next(sec for sec in s if sec.net == "RF_OUT")
    cs = cross_section(out, pieces, zs, None, "none")
    (sig,) = [r for r in cs.conductors if r.role == "signal"]
    top = [r for r in cs.conductors if r.role == "ground" and r.z0 == sig.z0]
    assert min(sig.x0 - r.x1 for r in top if r.x1 <= sig.x0) == pytest.approx(0.1505, abs=1e-3)
    assert min(r.x0 - sig.x1 for r in top if r.x0 >= sig.x1) == pytest.approx(0.1505, abs=1e-3)
    # the cut itself lies on no pad of any net, and RF_OUT's is the cut on bare line at x = 110.45, which meets no
    # RF_SMA copper in its box
    assert not [(sec.net, p.name) for sec in s for p in b.all_pads() if p.polygon.intersects(Point(sec.cut))]
    ref = replace(out, cut=(110.45, -100.0))
    across = LineString([(110.45, cs.box[0]), (110.45, cs.box[1])])
    assert not any(pc.polygon.intersects(across) for pc in pieces if pc.net == "RF_SMA")
    assert cross_section(out, pieces, zs, mask, "exact") == cross_section(ref, pieces, zs, mask, "exact")


def test_a_stripline_embedded_in_one_eps_r_reads_that_eps_r(mini_board_file):
    # final review: only the dielectric slabs spanned the cut, so an inner copper slab was air beside its copper. SIG,
    # 0.15 mm on In1.Cu between GND planes on F.Cu and In2.Cu with 0.2 mm of εr 4.3 either side, is a TEM line in one
    # dielectric: εeff 4.3 and Z0 49.0 Ω (Wheeler's thick stripline gives 49.03); it read 3.913 and 51.29 Ω. The resin
    # of a pressed board fills an inner copper layer's gaps, so its slab spans the cut too, at its neighbours' mean εr
    def solved(body):
        b = load_board(four_layer(mini_board_file, body))
        zs = zstack(b.stackup, b.copper_layers)
        pieces = copper_pieces(b, BIG, {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.kind == "copper"})[0]
        (sec,), _ = sections(b, ("SIG",), pieces)
        return solve(cross_section(sec, pieces, zs, None, "none"))

    line = solved(SEG.format(0.15, "In1.Cu") + plane("F.Cu") + plane("In2.Cu"))
    assert line.eps_eff == pytest.approx(4.3, rel=0.005)
    assert line.z0 == pytest.approx(49.0, rel=0.01)
    # control: a 0.35 mm line on F.Cu over a solid In1 plane reads as it did (outer copper stays air, but for the mask)
    top = solved(SEG.format(0.35, "F.Cu") + plane("In1.Cu"))
    assert (top.z0, top.eps_eff) == pytest.approx((50.344, 3.0965), rel=1e-4)


def test_copper_that_touches_the_line_is_no_gap(mini_board):
    # final review: _gap took copper that touches the track for a gap of 0, and d = 0 ran build_mesh into a
    # MemoryError after about 60 s. A GND rectangle abuts one edge of SIG and a netless one the other, where the 10 µm
    # simplification leaves 0.36 µm between them at the cut. Touching copper is a short (E_SHORT_IN_ROI) or floating
    # copper, never a gap, as in staircase_gap: the gap is the nearest copper that does not touch, a GND track
    rect = '(gr_rect (start 5 {}) (end 35 {}) (stroke (width 0)) (fill yes) (layer "F.Cu") {})'
    far = '(segment (start 5 12) (end 35 12) (width 0.3) (layer "F.Cu") (net "GND") (uuid "g"))'
    b = mini_board(SEG.format(0.3, "F.Cu") + rect.format(10.15, 11, '(net "GND")') + rect.format(9, 9.85, "") + far)
    (sec,), _ = sections(b, ("SIG",), pieces_of(b))
    assert sec.gap == pytest.approx(1.7, abs=SIMPLIFY)
    assert cell_size([sec], sec.width, 2, 1e9) > 0
