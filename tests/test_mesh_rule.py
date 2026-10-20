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
from kicad_rf_studio.core.geometry.sections import Section, sections
from kicad_rf_studio.core.geometry.vias import via_rods
from kicad_rf_studio.core.geometry.zstack import substrate_h, zstack
from kicad_rf_studio.core.kicad import classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.tracer import Chain
from kicad_rf_studio.core.mesh import Mesh, build_mesh
from kicad_rf_studio.core.mesh.protect import protected_set
from kicad_rf_studio.core.mesh.rule import (RATIO, _grade, cell_size, dz0, edge_lines, merge, z_lines)
from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines

FIX = Path(__file__).parent / "fixtures"
GRID_TOL = 3e-6  # mm: the 1e-6 mm grid moves big − 1.3·small by up to 2.3e-6 mm (T9 fix ruling)
FIXTURES = [("coupon_gcpw", "", ""), ("coupon_gcpw_masked", "", ""), ("coupon_gcpw_pads", "", ""),
            ("coupon_gcpw_45", "", ""), ("coupon_gcpw_arc", "", ""), ("coupon_ms", "", ""),
            ("coupon_ms_masked", "", ""), ("coupon_dense", "", ""), ("lpf915", "U1.1", "J1.1"),
            ("lpf915-45", "U1.1", "J1.1")]


def section(width, gap):
    return Section("LINE", "F.Cu", "x", (0.0, 0.0), (10.0, 0.0), width, gap, 10.0, (5.0, 0.0))


@cache
def geometry(name, start="", end=""):
    """`name`'s geometry as build_geometry (Task 12) assembles it from Tasks 2-6 at a 3 GHz top of band, and its
    protected set. The coupons have no pads to trace a chain between (R-P2-1), so their chain is LINE alone."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    chain = trace_chain(b, start, end) if start else Chain("", "", ("LINE",), (), ())
    zs = zstack(b.stackup, b.copper_layers)
    region = build_region(b, chain, [], zs, 3e9)
    pieces, notes = copper_pieces(b, region.crop, {s.copper: s.z1 - s.z0 for s in zs if s.kind == "copper"})
    prot = protected_set(b, chain, classify(b), pieces, substrate_h(zs))
    secs, more = sections(b, chain.nets, pieces)
    width = min(t.width for t in b.tracks if t.net in chain.nets)
    return Geometry(region, zs, pieces, via_rods(b, region.crop, zs, prot), mask_model(b, pieces, zs, region.crop, "F"),
                    secs, None, notes + more, width), prot


@cache
def mesh(name, start="", end=""):
    return build_mesh(*geometry(name, start, end), 2)


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
    closer than d/8, or their first outside line nearer than the nearest inside one."""
    hits = []
    for e, inside in edges:
        off = (lines - e) * inside  # > 0 inside the metal
        near_in, near_out = off[off > 0].min(initial=np.inf), -off[off < 0].max(initial=-np.inf)
        if (off == 0).any() or near_in < d / 8 or near_out < near_in:
            hits.append((e, inside))
    return hits


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


@pytest.mark.parametrize(("name", "start", "end"), FIXTURES)
def test_every_fixture_axis_grades_and_passes_the_edge_lint(name, start, end):
    # T9 fix ruling: build_mesh holds every neighbour within 1.3 on its final lines; Task 10 ruling: except beside a
    # cell the rule fixes
    geom, _ = geometry(name, start, end)
    m = mesh(name, start, end)
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


def test_protected_edges_come_from_solid_copper_outlines():
    def same(found, expected, tol):  # one physical edge may come as segments the simplification tilted apart
        def near(a, b):
            return a[1] == b[1] and abs(a[0] - b[0]) < tol
        return all(any(near(f, e) for e in expected) for f in found) and all(any(near(f, e) for f in found)
                                                                            for e in expected)

    m = mesh("coupon_gcpw_masked")
    # the 10 µm simplification tilts the LINE's top edge by 1.4 µm over 20 mm (T6 ruling); it is still an edge
    assert same(m.edges["y"], [(-100.4505, -1), (-100.3, 1), (-99.7, -1), (-99.5495, 1)], 1e-3)
    assert same(m.edges["x"], [(99.5005, 1), (120.4995, -1)], 1e-3)  # the F.Cu pour's ends; B.Cu's is a sheet
    assert not mesh("coupon_ms").edges["y"]  # a 1.35 mm microstrip alone on its layer is a sheet
    # the vertical cuts of the hole split are not edges: lpf915's GND pour was cut at x = 101.833481
    assert 101.833481 not in [e for e, _ in mesh("lpf915", "U1.1", "J1.1").edges["x"]]


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


def test_grading_never_splits_a_fixed_cell():
    lines = np.array([0.0, 1.0, 1.035, 1.06, 3.0])  # 35 µm of copper, then its 25 µm dz0 cell
    out = _grade(lines, [1.0175, 1.0475], 2.36)
    i = np.flatnonzero(out == 1.0)[0]
    assert list(out[i:i + 3]) == [1.0, 1.035, 1.06] and not bad_pairs(out, [1.0175, 1.0475])
