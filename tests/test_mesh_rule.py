# SPDX-License-Identifier: GPL-3.0-or-later
from functools import cache
from pathlib import Path

import numpy as np
import pytest
import shapely

from kicad_rf_studio.core.geometry import Geometry
from kicad_rf_studio.core.geometry.copper import copper_pieces
from kicad_rf_studio.core.geometry.mask import mask_model
from kicad_rf_studio.core.geometry.region import build_region, lambda_min
from kicad_rf_studio.core.geometry.sections import Section, cross_section, sections, staircase_gap
from kicad_rf_studio.core.geometry.vias import via_rods
from kicad_rf_studio.core.geometry.zstack import substrate_h, zstack
from kicad_rf_studio.core.kicad import classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.tracer import Chain
from kicad_rf_studio.core.mesh import Mesh, build_mesh
from kicad_rf_studio.core.mesh.protect import protected_set
from kicad_rf_studio.core.mesh.rule import (RATIO, _grade, _patterns, cell_size, dz0, edge_lines, merge, xy_lines,
                                            z_lines)
from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines

FIX = Path(__file__).parent / "fixtures"
GRID_TOL = 3e-6  # mm: the 1e-6 mm grid moves big − 1.3·small by up to 2.3e-6 mm (T9 fix ruling)
FIXTURES = [("coupon_gcpw", "", ""), ("coupon_gcpw_masked", "", ""), ("coupon_gcpw_pads", "", ""),
            ("coupon_gcpw_45", "", ""), ("coupon_gcpw_arc", "", ""), ("coupon_ms", "", ""),
            ("coupon_ms_masked", "", ""), ("coupon_dense", "", ""), ("lpf915", "U1.1", "J1.1"),
            ("lpf915-45", "U1.1", "J1.1")]


def section(width, gap):
    return Section("LINE", "F.Cu", "x", (0.0, 0.0), (10.0, 0.0), width, gap, 10.0, (5.0, 0.0))


def build(path, start="", end=""):
    """The board's geometry as build_geometry (Task 12) assembles it from Tasks 2-6 at a 3 GHz top of band, and its
    protected set. The coupons have no pads to trace a chain between (R-P2-1), so their chain is LINE alone."""
    b = load_board(path)
    chain = trace_chain(b, start, end) if start else Chain("", "", ("LINE",), (), ())
    zs = zstack(b.stackup, b.copper_layers)
    region = build_region(b, chain, [], zs, 3e9)
    pieces, notes = copper_pieces(b, region.crop, {s.copper: s.z1 - s.z0 for s in zs if s.kind == "copper"})
    prot = protected_set(b, chain, classify(b), pieces, substrate_h(zs))
    secs, more = sections(b, chain.nets, pieces)
    width = min(t.width for t in b.tracks if t.net in chain.nets)
    return Geometry(region, zs, pieces, via_rods(b, region.crop, zs, prot), mask_model(b, pieces, zs, region.crop, "F"),
                    secs, None, notes + more, width, staircase_gap(b, chain.nets, pieces)), prot


@cache
def geometry(name, start="", end=""):
    return build(FIX / f"{name}.kicad_pcb", start, end)


def variant(tmp_path, name, old, new, count=1):
    """The geometry of fixture `name` with a token of its file changed, `count` times: a synthetic variant of a
    synthetic board."""
    text = (FIX / f"{name}.kicad_pcb").read_text(encoding="utf-8")
    assert text.count(old) == count
    path = tmp_path / f"{name}.kicad_pcb"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return build(path)


@cache
def mesh(name, start="", end="", n=2):
    return build_mesh(*geometry(name, start, end), n)


def slab(zs, copper):
    return next(s for s in zs if s.copper == copper)


def z_fixed(zs, dz):
    """Markers in the z cells the rule fixes: each copper cell and the dz0 cell outside each of its faces."""
    return [v for s in zs if s.kind == "copper" for v in ((s.z0 + s.z1) / 2, s.z0 - dz / 2, s.z1 + dz / 2)]


def bad_pairs(lines, fixed=()):
    """Neighbouring cells more than RATIO apart (on the 1e-6 mm grid), unless the larger one holds a `fixed` marker:
    a protected copper edge in x and y, a copper or dz0 cell in z (Task 10 ruling)."""
    c = np.diff(lines)
    held = np.zeros(len(c), bool)
    i = np.searchsorted(lines, np.asarray(fixed, float)) - 1
    held[i[(i >= 0) & (i < len(c))]] = True
    big, small = np.maximum(c[1:], c[:-1]), np.minimum(c[1:], c[:-1])
    exempt = np.where(c[1:] >= c[:-1], held[1:], held[:-1])
    return [(lines[k + 1], c[k], c[k + 1]) for k in np.flatnonzero(~exempt & (big > RATIO * small + GRID_TOL))]


def lint(lines, edges, d):
    """The edge lint of spec 5.5, as Task 12 will run it: the edges with a line on them, their nearest inside line
    closer than d/8, or their first outside line no farther than the nearest inside one (T7 carry: a tie fails)."""
    hits = []
    for e, inside in edges:
        off = (lines - e) * inside  # > 0 inside the metal
        near_in, near_out = off[off > 0].min(initial=np.inf), -off[off < 0].max(initial=-np.inf)
        if (off == 0).any() or near_in < d / 8 or near_out <= near_in:
            hits.append((e, inside))
    return hits


def shared_nodes(m, geom, layer, a, b):
    """The grid nodes of `layer` that nets `a` and `b` both hold: a conductor holds both ends of every grid edge whose
    middle lies in it, boundary included (T7 ruling), so FDTD joins the two nets there."""
    held = []
    for net in (a, b):
        g = shapely.union_all([pc.polygon for pc in geom.pieces if pc.layer == layer and pc.net == net])
        shapely.prepare(g)
        nodes = np.zeros((len(m.x), len(m.y)), bool)
        along_x = shapely.intersects_xy(g, *np.meshgrid((m.x[1:] + m.x[:-1]) / 2, m.y, indexing="ij"))
        along_y = shapely.intersects_xy(g, *np.meshgrid(m.x, (m.y[1:] + m.y[:-1]) / 2, indexing="ij"))
        nodes[1:] |= along_x
        nodes[:-1] |= along_x
        nodes[:, 1:] |= along_y
        nodes[:, :-1] |= along_y
        held.append(nodes)
    return int((held[0] & held[1]).sum())


def test_cell_size_rule():
    s = [section(width=0.6, gap=0.15)]
    assert cell_size(s, 0.6, 2, 1e9) == pytest.approx(0.075)
    assert cell_size(s, 0.6, 3, 1e9) == pytest.approx(0.05)
    lam = lambda_min(100e9, 4.5)
    assert cell_size(s, 0.6, 2, lam) == pytest.approx(0.9 * lam / 20)


def test_cell_size_takes_the_narrowest_track():
    # Review Focus 4: a net with no straight section still gets a width. Task 10 ruling: the narrowest track always
    # counts (spec 5.4: "the smallest width or gap of the measured nets"), so a narrower 45° part of the net does too
    assert cell_size([], 0.3, 2, 1e9) == pytest.approx(0.15)
    assert cell_size([section(width=1.35, gap=None)], 1.35, 2, 1e9) == pytest.approx(0.675)  # microstrip: no gap
    assert cell_size([section(width=0.6, gap=0.5)], 0.2, 2, 1e9) == pytest.approx(0.1)


def test_cell_size_takes_the_gap_no_section_measures():
    # verifier: a net of 45° tracks has no section, so its gap never counted; Geometry.track_gap carries it
    assert cell_size([], 0.6, 2, 1e9, 0.15) == pytest.approx(0.075)
    assert cell_size([section(width=0.6, gap=0.5)], 0.6, 2, 1e9, None) == pytest.approx(0.25)


def test_staircased_net_gets_d_from_its_gap():
    # verifier: on coupon_gcpw_45 d came from the 0.6 mm width alone, 0.3, and the mesh joined LINE and GND at 40 grid
    # nodes, a short in FDTD (T7 ruling) that no gate saw: no section for fit2d, no axis-aligned edge for the lint
    geom, _ = geometry("coupon_gcpw_45")
    m = mesh("coupon_gcpw_45")
    assert m.d == pytest.approx(0.1505 / 2, abs=1e-3) and not shared_nodes(m, geom, "F.Cu", "LINE", "GND")


def test_edge_pattern():
    d = 0.075
    assert edge_lines(1.0, -1, d) == pytest.approx((1.0 - d / 4, 1.0 + 3 * d / 4))  # metal at x < 1
    assert edge_lines(1.0, +1, d) == pytest.approx((1.0 + d / 4, 1.0 - 3 * d / 4))


def test_dz0():
    assert dz0(0.010, 0.075, 1.5) == pytest.approx(0.025)
    assert dz0(0.010, 0.015, 1.5) == pytest.approx(0.010)
    assert dz0(0.010, 0.9, 0.1) == pytest.approx(0.025)


def test_one_z_cell_across_copper_then_dz0():
    geom, _ = geometry("coupon_gcpw_masked")
    zs, walls, coarse = geom.zs, geom.region.walls[4:], geom.region.coarse
    z = z_lines(zs, 0.075, 0.010, substrate_h(zs), walls, coarse=coarse)  # Task 10 ruling: z_lines takes coarse
    top, bottom = slab(zs, "F.Cu"), slab(zs, "B.Cu")
    i = np.flatnonzero(np.isclose(z, top.z0))[0]
    assert z[i + 1] == pytest.approx(top.z1) and z[i + 2] - z[i + 1] == pytest.approx(0.025)
    assert z[i] - z[i - 1] == pytest.approx(0.025)
    j = np.flatnonzero(np.isclose(z, bottom.z0))[0]
    assert z[j + 1] == pytest.approx(bottom.z1) and z[j] - z[j - 1] == pytest.approx(0.025)
    assert (z[0], z[-1]) == walls and np.diff(z).max() <= coarse + GRID_TOL
    # Task 10 ruling: 35 µm of copper beside a 25 µm dz0 is 1.4, which the rule fixes; every other pair grades
    c = np.diff(z)
    assert max(c[i] / c[i - 1], c[i] / c[i + 1]) == pytest.approx(1.4) and not bad_pairs(z, z_fixed(zs, 0.025))


def test_copper_faces_never_merge():
    # dz0/3 can exceed the copper's thickness (a 1.35 mm microstrip: d = 0.675, dz0 = h/4 = 0.1775); one z-cell per
    # copper thickness must survive the dz0/3 merge
    geom, _ = geometry("coupon_ms")
    z = z_lines(geom.zs, 0.675, 0.010, substrate_h(geom.zs), geom.region.walls[4:], coarse=geom.region.coarse)
    for s in geom.zs:
        if s.kind == "copper":
            i = np.flatnonzero(np.isclose(z, s.z0))[0]
            assert z[i + 1] == pytest.approx(s.z1)


def test_protected_region_filled_at_d_or_finer_and_graded_outside():
    geom, prot = geometry("coupon_gcpw")
    m = mesh("coupon_gcpw")
    assert m.d == pytest.approx(0.1505 / 2)  # R-P2-5: KiCad's zone fill leaves a 0.1505 mm gap
    _, lo, _, hi = shapely.total_bounds(list(prot.area.values()))
    inside = m.y[(m.y >= lo) & (m.y <= hi)]
    assert np.diff(inside).max() <= m.d + 1e-6
    for axis in "xy":
        lines = getattr(m, axis)
        assert not bad_pairs(lines, [e for e, _ in m.edges[axis]])
        assert np.diff(lines).max() <= geom.region.coarse + GRID_TOL


def test_merge_thresholds_and_pinned_lines_stay():
    out = merge(np.array([0, 0.01, 0.5, 0.51]), pinned={0.0, 0.5}, tol=0.075 / 3)
    assert list(out) == [0.0, 0.5]


def test_colliding_pinned_lines_keep_the_nearer_edge():
    # Decisions: two protected lines closer than d/3 become the one whose copper edge is nearer
    d = 0.075
    inner, outer = (round(v, 6) for v in edge_lines(1.0, -1, d))
    other = round(outer + 0.02, 6)  # another edge's inside line
    assert list(merge([inner, outer, other], {inner: d / 4, outer: 3 * d / 4, other: d / 4}, d / 3)) == [inner, other]


def test_equally_near_pinned_lines_meet_halfway():
    # Task 10 ruling: lpf915's RF_C edge and a GND edge lie 24.5 µm apart with their metal on opposite sides; either
    # inside line, d/4 from its own edge, is 6 µm inside the other, while their mean is 12 µm from both (> d/8)
    assert list(merge([1.0, 1.013], {1.0: 0.01875, 1.013: 0.01875}, 0.025)) == [1.0065]


def test_lines_quantised():
    m = mesh("lpf915", "U1.1", "J1.1")
    assert all(np.array_equal(np.round(a, 6), a) for a in (m.x, m.y, m.z))


def test_curve_vias_snap_to_lines():
    geom, _ = geometry("lpf915", "U1.1", "J1.1")  # 15 curves: the RF_SMA fence (14, Task 4) and one more barrel
    m = mesh("lpf915", "U1.1", "J1.1")
    assert len(m.snapped_rods) == len(geom.rods) and sum(not r.solid for r in m.snapped_rods) == 15
    assert all(r.at[0] in m.x and r.at[1] in m.y for r in m.snapped_rods if not r.solid)
    assert [r for r in m.snapped_rods if r.solid] == [r for r in geom.rods if r.solid]


def test_mesh_takes_no_rods_by_default():  # Task 12 builds meshes by hand for its lint and dt tests
    m = Mesh(np.array([0.98, 1.06]), np.array([0.0, 1]), np.array([0.0, 1]), 0.08, 0.01, {}, {"x": [], "y": []})
    assert m.snapped_rods == ()


@pytest.mark.parametrize("n", [2, 3])  # verifier: lpf915 failed the lint at n = 3, which P0-B (spec 9.3) measures
@pytest.mark.parametrize(("name", "start", "end"), FIXTURES)
def test_every_fixture_axis_grades_and_passes_the_edge_lint(name, start, end, n):
    # T9 fix ruling: build_mesh holds every neighbour within 1.3 on its final lines; Task 10 ruling: except beside a
    # cell the rule fixes
    geom, _ = geometry(name, start, end)
    m = mesh(name, start, end, n)
    for axis, (lo, hi) in zip("xy", (geom.region.walls[:2], geom.region.walls[2:4])):
        lines, edges = getattr(m, axis), m.edges[axis]
        assert not bad_pairs(lines, [e for e, _ in edges])
        assert (lines[0], lines[-1]) == (lo, hi) and np.diff(lines).max() <= geom.region.coarse + GRID_TOL
        # spec 5.4 merges in-plane below d/3; Task 10 ruling: vertex lines at a fixed d gave lpf915 17 µm cells (0.22d)
        assert np.diff(lines).min() >= m.d / 3 - GRID_TOL
        assert not lint(lines, edges, m.d)
        assert np.isin(m.pinned[axis], lines).all()
    assert not bad_pairs(m.z, z_fixed(geom.zs, m.dz0))
    assert np.isin(m.pinned["z"], m.z).all()


def test_protected_edges_come_from_copper_outlines():
    def same(found, expected, tol):  # one physical edge may come as segments the simplification tilted apart
        def near(a, b):
            return a[1] == b[1] and abs(a[0] - b[0]) < tol
        return all(any(near(f, e) for e in expected) for f in found) and all(any(near(f, e) for f in found)
                                                                            for e in expected)

    m = mesh("coupon_gcpw_masked")
    # the 10 µm simplification tilts the LINE's top edge by 1.4 µm over 20 mm (T6 ruling); it is still an edge
    assert same(m.edges["y"], [(-100.4505, -1), (-100.3, 1), (-99.7, -1), (-99.5495, 1)], 1e-3)
    assert same(m.edges["x"], [(99.5005, 1), (120.4995, -1)], 1e-3)  # the pours' ends (B.Cu's sheet ends there too)
    # the vertical cuts of the hole split are not edges: lpf915's GND pour was cut at x = 101.833481
    assert 101.833481 not in [e for e, _ in mesh("lpf915", "U1.1", "J1.1").edges["x"]]


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize(("name", "start", "end"), FIXTURES)
def test_both_edges_of_every_section_are_protected_edges(name, start, end, n):
    # R-P2-18: every protected in-plane copper edge, solid or sheet, takes the edge pattern. The lint runs over
    # Mesh.edges alone, so coupon_ms's strip, a sheet (spec 5.3: wide everywhere), had no edge and passed it vacuously
    geom, _ = geometry(name, start, end)
    m = mesh(name, start, end, n)
    for sec in geom.sections:
        c, top = sec.cut[1] if sec.axis == "x" else sec.cut[0], slab(geom.zs, sec.layer).z1
        strips = cross_section(sec, geom.pieces, geom.zs, None, "none").conductors
        lo, hi = next((r.x0, r.x1) for r in strips if r.role == "signal" and r.z1 == top and r.x0 <= c <= r.x1)
        edges = m.edges["y" if sec.axis == "x" else "x"]
        # an edge sits at its segment's middle, and the 10 µm simplification tilts a segment: 1.8 µm at lpf915-45's cuts
        assert all(any(s == side and abs(v - e) < 2e-3 for v, s in edges) for e, side in ((lo, 1), (hi, -1)))


@pytest.mark.parametrize("n", [2, 3])
def test_a_sheet_strip_carries_the_edge_pattern(n):
    # R-P2-18: coupon_ms's y lines fell wherever the fill put them, and fit2d read −27 % at n = 2
    m = mesh("coupon_ms", n=n)
    edges = [e for e in m.edges["y"] if -101 < e[0] < -99]
    assert [s for _, s in edges] == [1, -1]
    for e in edges:
        assert all(np.isclose(m.y, v, rtol=0, atol=1.5e-6).any() for v in edge_lines(*e, m.d))


def test_extra_edges_get_a_pattern():  # Task 12 re-meshes once with the edges its lint failed
    geom, prot = geometry("coupon_gcpw")
    m = build_mesh(geom, prot, 2, {"x": [(110.0, -1)], "y": []})
    assert (110.0, -1) in m.edges["x"] and not lint(m.x, [(110.0, -1)], m.d)
    assert {round(v, 6) for v in edge_lines(110.0, -1, m.d)} <= set(m.x)


@pytest.mark.parametrize("lines", [
    [0.0, 1.0, 2.4, 3.4],  # T9: 1 | 1.4 | 1, which no split of the 1.4 alone fixes and plain halving never ends
    np.cumsum([0] + [1] * 8 + [1.33] + [1] * 8),  # 1.33 next to 1: no piece beside the 1 can be within 1.3 of it
    smooth_mesh_lines(np.array([0, 0.1, 0.9, 1.05]), 1.0),  # T9: smooth_mesh_lines leaves 8
    smooth_mesh_lines(np.array([0, 1, 2.01, 2.9]), 1.0),  # T9: 1.98
    smooth_mesh_lines(np.array([-5, -0.1, 0.1, 5]), 1.0),  # T9: an even-symmetric axis's centre gap, 4.9
])
def test_grading_refines_both_sides_of_a_jump(lines):
    lines = np.round(np.asarray(lines, float), 6)
    out = _grade(lines, [], 1.0)
    assert set(lines) <= set(out) and not bad_pairs(out) and np.diff(out).max() <= 1.0 + GRID_TOL


def test_grading_converges_between_wide_neighbours():
    # verifier: a cell between two cells far above RATIO·cap had no piece ≤ cap within RATIO of either, and the halving
    # that followed ratcheted down: RuntimeError after 10,000 rounds on real boards, or thousands of µm cells here
    lines = np.array([2.090114, 4.778241, 7.418406, 10.079351])
    out = _grade(lines, [], 0.075)
    assert set(lines) <= set(out) and not bad_pairs(out) and np.diff(out).max() <= 0.075 + GRID_TOL
    assert len(out) < 1.2 * (lines[-1] - lines[0]) / 0.075


def test_mesh_converges_on_a_thin_45_degree_line(tmp_path):
    geom, prot = variant(tmp_path, "coupon_gcpw_45", "(width 0.6)", "(width 0.124)")  # verifier: RuntimeError
    m = build_mesh(geom, prot, 2)
    for axis in "xy":
        lines = getattr(m, axis)
        assert not bad_pairs(lines, [e for e, _ in m.edges[axis]]) and np.diff(lines).min() >= m.d / 3 - GRID_TOL


@pytest.mark.parametrize("d", [0.15, 0.1])  # a 0.3 mm strip at n = 2 and 3
@pytest.mark.parametrize("gaps", [(), (0.3,), (0.45,)])  # no edge, or same-side edges sharing a cell over 1.3d wide
def test_fill_beside_wide_cells_stays_near_d(d, gaps):
    # verifier: the fill matched the 23 mm cells outside the extent (and a shared cell over 1.3d), which no piece ≤ d
    # can match, and halved down to 2.3 µm: 2335 lines on a 21 mm extent; spec 5.4 merges in-plane below d/3
    edges = [(110.0, -1)] * bool(gaps) + [(round(110.0 + s * d, 6), -1) for s in gaps]
    lines, _ = xy_lines(edges, (99.5005, 120.4995), (76.156864, 143.843136), [], d, 2.355392)
    assert np.diff(lines).min() >= d / 3 - GRID_TOL and not bad_pairs(lines, [e for e, _ in edges])
    assert len(lines) < 21 / d + 60


@pytest.mark.parametrize(("size", "n"), [(0.652, 2), (0.634, 3)])
def test_pads_a_step_wider_than_their_track_keep_cells_over_d_over_3(tmp_path, size, n):
    # verifier (B): LINE pads 26-32 µm wider each side than the 0.6 mm track make a step 0.34-0.43d wide, split by its
    # shallow d/8 inside line into cells of 0.34-0.39d; the fill beside them was scaled down to 0.306d and 0.314d
    pad = '(pad "1" smd rect\n\t\t\t(at 0 0)\n\t\t\t(size 1 1)'
    geom, prot = variant(tmp_path, "coupon_gcpw_pads", pad, pad.replace("(size 1 1)", f"(size {size} {size})"), 2)
    m = build_mesh(geom, prot, n)
    for axis in "xy":
        lines = getattr(m, axis)
        assert np.diff(lines).min() >= m.d / 3 - GRID_TOL and not lint(lines, m.edges[axis], m.d)


def test_the_fill_beside_a_pad_step_stays_over_d_over_3():
    # verifier (B): _pieces scaled a run down with no d/3 floor (spec 5.4 merges below it) from the small cells of a
    # split step: 0.27d. A track w·d wide, its pad's edge s·d past it on one side or both, GND g·d past the pad
    fails = []
    for d in (0.075, 0.05):
        for s in np.arange(0.30, 0.501, 0.01):
            for w, g in ((2.0, 2.0), (3.0, 2.0), (4.0, 3.0), (8.0, 3.0)):
                for both in (False, True):
                    t, e = 110.0, (s + g) * d
                    edges = [(round(t - w * d, 6), 1), (t, -1), (round(t + s * d, 6), -1), (round(t + e, 6), 1)]
                    edges += [(round(t - (w + s) * d, 6), 1), (round(t - w * d - e, 6), -1)] * both
                    lines, _ = xy_lines(sorted(edges), (100.0, 120.0), (80.0, 140.0), [], d, 2.36)
                    if np.diff(lines).min() < d / 3 - GRID_TOL or lint(lines, sorted(edges), d):
                        fails.append((d, round(float(s), 2), w, g, both))
    assert not fails


@pytest.mark.parametrize("n", [2, 3])
def test_narrow_solid_microstrip_has_no_cell_under_d_over_3(tmp_path, n):
    geom, prot = variant(tmp_path, "coupon_ms", "(width 1.35)", "(width 0.6)")  # solid: 0.6 mm is under 30·t
    m = build_mesh(geom, prot, n)  # verifier: 685 x lines at n = 2, 615 cells under d/3, the smallest 0.041d
    for axis in "xy":
        lines = getattr(m, axis)
        assert np.diff(lines).min() >= m.d / 3 - GRID_TOL and not bad_pairs(lines, [e for e, _ in m.edges[axis]])


@pytest.mark.parametrize("s", [0.2, 0.3, 0.375, 0.45, 0.5, 0.52, 0.55, 0.6, 0.65, 2 / 3, 0.7, 0.9, 1, 1.2, 4 / 3, 1.5])
@pytest.mark.parametrize("side", [-1, 1])
def test_same_side_edges_pass_the_lint_at_any_spacing(s, side):
    # verifier: one pattern shared by edges more than d/2 apart put the outer edge's outside line nearer than its inside
    # one (a track entering a pad 38-50 µm wider each side; lpf915 at n = 3)
    d = 0.075
    edges = sorted([(110.0, side), (round(110.0 - side * s * d, 6), side)])  # the second edge lies outside the first
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], d, 2.36)
    assert not lint(lines, edges, d)


@pytest.mark.parametrize("steps", [(0.3, 0.3), (0.2, 0.2, 0.2, 0.2), (0.3, 0.6), (0.45, 0.45), (0.391, 0.392, 1.254)])
def test_a_staircase_of_close_edges_passes_the_lint(steps):
    d = 0.075  # verifier: three edges 0.3d apart chained into one pattern, the far edge 0.85d inside and 0.75d outside
    edges = [(round(110.0 + v * d, 6), -1) for v in np.cumsum([0, *steps])]
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], d, 2.36)
    assert not lint(lines, edges, d)


def test_a_shared_cell_spans_d_at_most():
    # Task 10 fix ruling: steps under 5d/16 leave no room for a line, so a staircase joins one cell, and each join
    # widens it for its far edge; uncapped, such joins chained into cells many d wide that passed the lint (9.6d in a
    # probe). Past d the far edge fails it instead: E_EDGE_LINT, whose advice (the strict preset, 2d/3) passes
    edges = [(round(110.0 + v * 0.075, 6), -1) for v in (0, 0.3, 0.6, 0.9, 1.2)]
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], 0.075, 2.36)
    assert lint(lines, edges, 0.075) and np.diff(lines[(lines > 109.8) & (lines < 110.4)]).max() < 2 * 0.075
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], 0.05, 2.36)
    assert not lint(lines, edges, 0.05)


@pytest.mark.parametrize("g", [0.1, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.3, 1.5, 1.7, 2.0])
def test_facing_edges_across_a_gap_pass_the_lint(g):
    # copper below one edge and above the next, g·d apart: their own outside lines, 3d/4 out, cross in a gap under 1.5d
    # and one lands inside the other edge's cell (gaps of 0.6d to d failed the lint before the fix round)
    d = 0.075
    edges = [(110.0, -1), (round(110.0 + g * d, 6), 1)]
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], d, 2.36)
    assert not lint(lines, edges, d)


@pytest.mark.parametrize("edges", [[(110.0, -1), (110.010125, 1), (110.094875, -1)],
                                   [(110.0, -1), (110.048, 1), (110.0855, -1)]])
def test_the_facing_gap_step_keeps_the_next_cells_inside_line(edges):
    # verifier (A): a's outside line was also the next same-side cell's inside line, and the facing-gap step moved both,
    # so that cell's edge got its inside line 0.88d away against an outside line 0.75d away
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], 0.075, 2.36)
    assert not lint(lines, edges, 0.075)


def test_facing_gaps_beside_a_narrow_strip_pass_the_lint():
    # verifier (A): metal below a, a gap g·d, then a strip w·d wide; 139 configs (gaps under 0.83d, each way round)
    # failed after the round-1 fix only. Here every config passes; 1d066c2 failed 1842 of the 0.02d grid's 17,820
    d, fails = 0.075, []
    for g in np.arange(0.02, 2.2, 0.06):
        for w in np.arange(0.4, 2.01, 0.1):
            for way in (1, -1):
                edges = sorted([(110.0, -way), (round(110.0 + way * g * d, 6), way),
                                (round(110.0 + way * (g + w) * d, 6), -way)])
                lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], d, 2.36)
                fails += [(round(float(g), 2), round(float(w), 2), way)] * bool(lint(lines, edges, d))
    assert not fails


def test_extra_edges_keep_their_own_pattern():
    # the lint's one re-mesh (spec 5.5) passes the failing edges back; their own pattern then wins over every line that
    # sharing or merging put in its cell, so the re-mesh changes something (verifier: it rebuilt the same lines)
    d = 0.075
    edges = [(110.0, 1), (round(110.0 + 0.2 * d, 6), -1)]  # metal overlapping by 0.2d: no line lies d/8 inside both
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], d, 2.36)
    assert lint(lines, edges, d)
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], d, 2.36, force=edges[:1])
    assert not lint(lines, edges[:1], d) and {round(v, 6) for v in edge_lines(*edges[0], d)} <= set(lines)


def test_extent_end_just_past_an_edge_is_no_line():
    d = 0.075  # verifier: an extent end d/12 to d/4 outside an edge was a line nearer than the edge's inside line
    edges = [(100.01, 1)]
    lines, _ = xy_lines(edges, (100.0, 120.0), (80.0, 140.0), [], d, 2.36)
    assert not lint(lines, edges, d)


def test_extent_end_in_an_edge_cell_is_no_line(tmp_path):
    # verifier: TP1 moved by 20 µm made the extent's end (the pour's end at 99.5005) a line on that edge, which shares a
    # cell with the pad's edge at 99.52; the lint failed at n = 2 and 3 and the re-mesh rebuilt the same lines
    geom, prot = variant(tmp_path, "coupon_gcpw_pads", "(at 100 100)", "(at 100.02 100)")
    for n in (2, 3):
        m = build_mesh(geom, prot, n)
        assert not lint(m.x, m.edges["x"], m.d) and not lint(m.y, m.edges["y"], m.d)


def test_colliding_inside_lines_keep_one_where_the_lint_allows():
    d = 0.075
    pad, gnd = (-100.5, 1), (-100.4505, -1)  # coupon_gcpw_pads: a pad's edge 49.5 µm past the facing GND edge
    pins = _patterns([pad, gnd], d, prefer={gnd})
    assert round(edge_lines(*gnd, d)[0], 6) in pins and round(edge_lines(*pad, d)[0], 6) not in pins
    assert not lint(np.array(sorted(pins)), [pad, gnd], d)
    line, other = (1.0, 1), (1.0245, -1)  # lpf915: metal overlapping by 24.5 µm; either line is under d/8 in the other
    pins = _patterns([line, other], d, prefer={line})
    assert 1.01225 in pins and not lint(np.array(sorted(pins)), [line, other], d)


def test_a_shallow_inside_line_wins_its_collision_as_the_nearer_edges_line():
    # R-P2-21: lpf915's GND pour steps 20 µm by the pads (0.4d at n = 3), so its edges share one cell whose inside line
    # sits d/8 + GRID_TOL inside the deepest edge; on the 1e-6 mm grid that line read 0.2 nm under the collision check's
    # d/8 + GRID_TOL, lost to the facing edge's d/4 line, and the section's GND edge got its inside line 0.66d in
    d = 0.05008166666666666  # lpf915 at n = 3
    stair = [(-100.4705, -1), (-100.469115, -1), (-100.4555, -1), (-100.454091, -1), (-100.450658, -1), (-100.4505, -1)]
    edges = [(-100.496202, 1), *stair]  # metal above -100.496202 overlaps the pour's by 26 µm
    pins = _patterns(edges, d)
    assert round(-100.4705 - (d / 8 + GRID_TOL), 6) in pins and not lint(np.array(sorted(pins)), edges, d)


def test_section_edges_keep_their_lines_on_coupon_gcpw_pads():
    # verifier: the pads' edges pulled the GND inside lines to the mean along the whole line, at the section's cut too:
    # fit2d read +3.38 % (over 3 %), and +2.47 % with the GND lines kept
    m = mesh("coupon_gcpw_pads")
    for edge in [(-100.4505, -1), (-99.5495, 1)]:  # the GND edges facing the LINE at its cut
        assert np.isclose(m.y, edge_lines(*edge, m.d)[0], rtol=0, atol=1.5e-6).any()
    assert not lint(m.y, m.edges["y"], m.d)


def test_grading_never_splits_a_fixed_cell():
    lines = np.array([0.0, 1.0, 1.035, 1.06, 3.0])  # 35 µm of copper, then its 25 µm dz0 cell
    out = _grade(lines, [1.0175, 1.0475], 2.36)
    i = np.flatnonzero(out == 1.0)[0]
    assert list(out[i:i + 3]) == [1.0, 1.035, 1.06] and not bad_pairs(out, [1.0175, 1.0475])
