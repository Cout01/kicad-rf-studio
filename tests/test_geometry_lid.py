# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from functools import cache
from pathlib import Path

import numpy as np
import pytest
import shapely
from shapely.geometry import MultiPolygon, Point, box

from kicad_rf_studio.core.geometry.lid import find_lid, snap_lid
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.mesh import build_mesh
from kicad_rf_studio.core.messages import render
from test_mesh_rule import bad_pairs, geometry, z_fixed

FIX = Path(__file__).parent / "fixtures"
LPF = ("lpf915", "U1.1", "J1.1")
P = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "lid_height_mm": 2.0}  # the project fields find_lid reads
GAP = Point(116.825, -106.25)  # where RF_SMA leaves SH1 through the gap in its right side, past R2, for J2


@cache
def setup(name, start="", end=""):
    """find_lid's inputs but the project: the board, its classes, and the region (3 GHz top of band) and z-stack of
    the mesh tests' geometry."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    geom, _ = geometry(name, start, end)
    return b, classify(b), geom.region, geom.zs


def test_lpf915_lid_found():  # lpf915: SH1 frame around the chain, gap in the right side for R2
    lid, notes = find_lid(*setup(*LPF), {**P, "lid_height_mm": 2.0, "harmonics": 3})
    assert lid.ref == "SH1" and lid.z1 == pytest.approx(lid.z0 + 2.0) and notes == []
    assert not lid.walls.intersects(GAP)  # the frame gap stays open
    # the plate, the convex hull of the frame pads, spans the gap; the walls are the pads; z0 is F.Cu's top face
    assert lid.plate.contains(GAP) and lid.plate.bounds == (95.825, -110.75, 117.325, -89.25)
    assert lid.walls.area == pytest.approx(43.2) and lid.z0 == 0.78  # the area of SH1's 20 pads


def test_no_height_reports():
    lid, notes = find_lid(*setup(*LPF), {**P, "lid_height_mm": None})
    assert lid is None and notes[0][0] == "E_LID_HEIGHT"
    assert notes == [("E_LID_HEIGHT", {"refs": "SH1"})] and render("E_LID_HEIGHT", refs="SH1") == (
        "Shield SH1 covers the simulated region but project.json has no lid_height_mm. Set it, or re-create the "
        "project with --lid-height.")


@pytest.mark.parametrize("height", [0, -1.0, np.nan, np.inf])  # 0 put the plate on F.Cu's traces, NaN on the MUR
def test_a_height_that_is_not_finite_and_above_0_is_missing(height):  # as `new --lid-height` refuses it (cli._positive)
    assert find_lid(*setup(*LPF), {**P, "lid_height_mm": height}) == (None, [("E_LID_HEIGHT", {"refs": "SH1"})])


def test_lid_off_for_fundamental_only():
    assert find_lid(*setup(*LPF), {**P, "lid_height_mm": 2.0, "harmonics": 1})[0] is None
    assert find_lid(*setup(*LPF), {**P, "lid_height_mm": None, "harmonics": 1}) == (None, [])  # off, it needs none


def test_project_lid_overrides_the_harmonics():  # plan Decisions: on with harmonics unless project["lid"] says otherwise
    assert find_lid(*setup(*LPF), {**P, "harmonics": 1, "lid": True})[0].ref == "SH1"
    assert find_lid(*setup(*LPF), {**P, "lid_height_mm": None, "lid": False}) == (None, [])


def test_snap_adds_no_line():
    lid, _ = find_lid(*setup(*LPF), P)
    snapped = snap_lid(lid, z := np.array([0, 1.6, 3.55, 3.7, 6]))
    assert snapped.z1 in z
    assert snapped == replace(lid, z1=3.55)  # 2.78 lies nearest 3.55, and nothing else moves


def test_frame_outside_roi_ignored():  # coupon boards have no shield
    assert find_lid(*setup("coupon_gcpw"), P)[0] is None


def test_a_shield_off_the_roi_is_ignored():  # and so is its missing height
    b, classes, region, zs = setup(*LPF)
    off = replace(region, roi=box(118, -101, 122, -99))  # right of SH1, by J2
    assert find_lid(b, classes, off, zs, {**P, "lid_height_mm": None}) == (None, [])


@pytest.mark.parametrize("kind, layers", [("smd", ("B.Cu",)), ("thru_hole", ("F.Cu", "B.Cu"))])  # THT legs: *.Cu
def test_a_shield_on_the_bottom_side_has_no_lid(kind, layers):  # the lid stands on the top copper: z0 is its top face
    b, classes, region, zs = setup(*LPF)
    sh1 = b.footprints["SH1"]
    flipped = replace(sh1, layer="B.Cu", pads=tuple(replace(p, kind=kind, layers=layers) for p in sh1.pads))
    under = replace(b, footprints={**b.footprints, "SH1": flipped})
    assert find_lid(under, classes, region, zs, {**P, "lid_height_mm": None}) == (None, [])


def test_a_peg_hole_is_not_frame():  # an np_thru_hole with no copper neither widens the plate nor stands as a wall
    b, classes, region, zs = setup(*LPF)
    sh1 = b.footprints["SH1"]
    peg = replace(sh1.pads[0], kind="np_thru_hole", layers=(), polygon=Point(94, -100).buffer(0.5))  # left of SH1
    pegged = replace(b, footprints={**b.footprints, "SH1": replace(sh1, pads=(*sh1.pads, peg))})
    assert find_lid(pegged, classes, region, zs, P) == find_lid(b, classes, region, zs, P)


def test_the_lid_is_clipped_to_the_crop_and_on_the_grid():
    b, classes, region, zs = setup(*LPF)
    lid, _ = find_lid(b, classes, region, zs, {**P, "lid_height_mm": 2.0000004})
    xy = shapely.get_coordinates([lid.plate, lid.walls])
    assert np.array_equal(np.round(xy, 6), xy) and lid.z1 == 2.78  # some pad corners lie off it (99.12500000000001)
    crop = box(100, -105, 130, -95)  # through the frame: two pads of its right side reach into it
    lid, _ = find_lid(b, classes, replace(region, crop=crop), zs, P)
    assert lid.plate.equals(box(100, -105, 117.325, -95))
    assert lid.walls.equals(MultiPolygon([box(116.325, -97.55, 117.325, -95), box(116.325, -105, 117.325, -102.45)]))


def test_the_lid_puts_lines_on_its_walls():  # Task 10's build_mesh takes the lid's vertices as free coordinates
    geom, prot = geometry(*LPF)
    lid, _ = find_lid(*setup(*LPF), P)
    bare, lidded = build_mesh(geom, prot, 2), build_mesh(replace(geom, lid=lid), prot, 2)
    faces = {95.825, 96.825, 116.325, 117.325}  # SH1's sides; its pads sit in the GND pour, so no copper vertex there
    assert faces <= set(lidded.x) and not faces & set(bare.x)


@pytest.mark.parametrize("height", [2.0, 30.0])  # 30 mm reaches past the top wall, 22.8 mm over the board at 3 GHz
def test_build_mesh_grows_the_top_wall_over_the_lid(height):  # R-P2-3; spec 5.2: the lid is never the boundary
    geom, prot = geometry(*LPF)
    lid, _ = find_lid(*setup(*LPF), {**P, "lid_height_mm": height})
    m, walls = build_mesh(replace(geom, lid=lid), prot, 2), geom.region.walls
    # the top wall keeps its distance from the lid's top, 4 mm + 8 coarse cells, as it does from the board's
    assert m.z[0] == walls[4] and m.z[-1] == pytest.approx(walls[5] + lid.z1 - geom.zs[-1].z1, abs=1e-7)
    assert m.z[-1] in m.pinned["z"] and not bad_pairs(m.z, z_fixed(geom.zs, m.dz0))
    z1 = snap_lid(lid, m.z).z1  # then the plate snaps to a line near its height
    assert z1 in m.z and abs(z1 - lid.z1) <= geom.region.coarse / 2
