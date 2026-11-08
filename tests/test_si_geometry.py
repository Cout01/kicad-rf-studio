# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace

import numpy as np
import pytest
import shapely

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.geometry import chain_of
from kicad_rf_studio.core.geometry.vias import Rod
from kicad_rf_studio.core.mesh import VIA_MARGIN_MM, build_mesh
from kicad_rf_studio.core.mesh.gates import mesh_with_lint
from kicad_rf_studio.core.project import load_project, parts, save_project
from test_cli_si import FIX, QSPI, si_project

LEGS = (frozenset({"USB_D+", "MCU_D+"}), frozenset({"USB_D-", "MCU_D-"}))
# the SI rule's cell, λ/40 at 10 GHz on usb2_hs's 2D εeff: new's until gate P4-C made the d fill its default
# (docs/validation/2026-11-07-p4-c.md), and a set mesh.max_cell_mm's value, which the SI mesh grades to
CELL = 0.414074


@pytest.fixture(scope="module")
def usb(tmp_path_factory):
    return pipeline.load(si_project(tmp_path_factory.mktemp("usb")))


@pytest.fixture(scope="module")
def qspi(tmp_path_factory):
    return pipeline.load(si_project(tmp_path_factory.mktemp("qspi"), QSPI))


def extent(geom):
    return shapely.total_bounds(list(geom.protected.area.values()))


def over_d(held, m, axis):
    """The cells between `held`'s lines wider than d that hold no protected edge of `axis`: d fills a span, and only
    an edge's cell, which its pattern fixes, may be wider (Stage 1's d fill has the same cells)."""
    at = np.array([e for e, _ in m.edges[axis]])
    return [(a, b) for a, b in zip(held, held[1:]) if b - a > m.d + 1e-6 and not ((at > a) & (at < b)).any()]


def test_an_si_projects_lines_are_one_chain_of_measured_copper(usb):  # design 5.1, 5.2
    project, board, geom, notes = usb
    c = chain_of(project)
    assert (c.start, c.end, c.nets) == ("J1.3", "U1.3", ("USB_D+", "MCU_D+", "USB_D-", "MCU_D-", "AUX"))
    assert [p.ref for p in c.series] == ["R1", "R2"] and list(parts(project)) == ["R1", "R2", "C1"]
    assert (geom.layers, geom.legs, geom.stairs) == (("F.Cu",), LEGS, ())
    assert geom.partners("MCU_D-") == LEGS[0] and geom.partners("AUX") == frozenset()
    assert geom.protected.nets == frozenset(c.nets)
    assert not {"E_OPEN_IN_ROI", "E_SHORT_IN_ROI", "W_STAIRCASED", "W_OFF_TOP_LAYER"} & {code for code, _ in notes}
    # every line's copper and parts, J1's pins to U1's exposed pad and the test points, 6 × 0.2 mm past them
    assert geom.region.roi.bounds == pytest.approx((96.5875, -102.85, 132.05, -97.55), abs=1e-6)


def test_an_si_line_on_two_layers_takes_both(qspi):  # design 5.3: the dielectric next to each layer; Review Focus 1
    project, board, geom, notes = qspi
    assert (geom.layers, geom.legs, list(parts(project))) == (("F.Cu", "B.Cu"), None, ["R1", "C1"])
    assert "W_OFF_TOP_LAYER" not in {code for code, _ in notes}  # v1's warning: the region took the top layer's h
    assert geom.region.roi.bounds == pytest.approx((97.95, -102.05, 121.7, -97.95), abs=1e-6)  # U1.17 within it


def test_a_line_takes_its_own_dielectric_for_d_and_the_reach(tmp_path):  # design 5.3; Review Focus 4
    pj = si_project(tmp_path, QSPI)
    data = load_project(pj)
    data["stackup"]["layers"] = [{**x, "thickness_mm": {"dielectric 1": 0.3, "dielectric 3": 0.1}.get(
        x["name"], x["thickness_mm"])} for x in data["stackup"]["layers"]]  # 0.1 mm over B.Cu, the total unchanged
    save_project(pj, data)
    project, board, geom, _ = pipeline.load(pj)
    assert geom.region.roi.bounds == pytest.approx((98.55, -101.45, 121.1, -98.55), abs=1e-6)  # 6 × 0.1, not × 0.3
    assert build_mesh(geom, geom.protected, 2).d == pytest.approx(0.05)  # h/n
    assert geom.protected.area["In1.Cu"].bounds[2] == pytest.approx(121.096, abs=0.005)  # U2.6's edge + 0.6 mm


def test_the_si_mesh_fills_d_at_the_edges_and_grades_to_max_cell_between(usb):  # design 5.3
    geom = usb[2]
    si = mesh_with_lint(geom, geom.protected, 2, max_cell=CELL)  # E_EDGE_LINT would raise
    full = build_mesh(geom, geom.protected, 2)  # Stage 1's d fill
    box = extent(geom)
    mids = (si.x[1:] + si.x[:-1]) / 2
    steps = np.diff(si.x)[(mids > box[0]) & (mids < box[2])]
    assert len(si.x) < len(full.x) and 2 * si.d < steps.max() <= CELL + 1e-6


@pytest.mark.parametrize("name", ["usb2_hs", "qspi_clk"])
def test_every_solid_rod_keeps_its_lines(name, tmp_path):  # plan 1's carried item; Review Focus 3
    geom = pipeline.load(si_project(tmp_path, FIX / f"{name}.kicad_pcb"))[2]
    m = build_mesh(geom, geom.protected, 2, max_cell=CELL)
    solid = [r for r in geom.rods if r.solid]
    # U1.17's near column of vias (the far column's rings lie past the 1.2 mm reach, so those rods are snapped), with
    # U2.2's via and J1.6's shield hole, or with qspi_clk's two signal vias
    assert len(solid) == 4 and sum(r.net in geom.protected.nets for r in solid) == (2 if name == "qspi_clk" else 0)
    for r in solid:
        margin = VIA_MARGIN_MM if r.net in geom.protected.nets else r.radius
        for k, lines in enumerate((m.x, m.y)):
            held = lines[(lines >= r.at[k] - margin - 1e-6) & (lines <= r.at[k] + margin + 1e-6)]
            assert held.size >= 2 and not over_d(held, m, "xy"[k]), (r, k)


def test_a_rod_past_the_extent_on_one_axis_keeps_its_lines(usb):  # Review Focus 3: a fence via beside the route
    geom = usb[2]
    first = geom.rods[0]
    rod = Rod("GND", (114.0, round(extent(geom)[3] + 0.2, 6)), 0.15, first.z0, first.z1, True)  # x inside, y past
    m = build_mesh(replace(geom, rods=[*geom.rods, rod]), geom.protected, 2, max_cell=CELL)
    held = m.x[(m.x >= 114.0 - 0.15 - 1e-6) & (m.x <= 114.0 + 0.15 + 1e-6)]
    assert held.size >= 2 and np.diff(held).max() <= m.d + 1e-6  # graded to max_cell there, it would lose its nodes


def test_staircased_copper_is_filled_at_d(tmp_path):  # design 5.3; plan 1's ponytail on 45° copper
    _, _, geom, notes = pipeline.load(si_project(tmp_path, FIX / "usb2_hs_45.kicad_pcb"))
    assert ("W_STAIRCASED", {"net": "USB_D+"}) in notes and len(geom.stairs) == 4  # two 45° segments a line
    m = build_mesh(geom, geom.protected, 2, max_cell=CELL)
    for x0, y0, x1, y1 in geom.stairs:  # each segment's copper, its round ends too
        for axis, lines, lo, hi in (("x", m.x, x0, x1), ("y", m.y, y0, y1)):
            assert not over_d(lines[(lines >= lo) & (lines <= hi)], m, axis)
