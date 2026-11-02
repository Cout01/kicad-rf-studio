# SPDX-License-Identifier: GPL-3.0-or-later
import math
from dataclasses import replace
from pathlib import Path

import pytest

from kicad_rf_studio.core.geometry.region import (WALL_CELLS, WALL_MM, air_cell, air_gap, band, board_region,
                                                  build_region, coarse_cell, f_max)
from kicad_rf_studio.core.geometry.zstack import Slab, substrate_h, zstack
from kicad_rf_studio.core.kicad import load_board, trace_chain
from kicad_rf_studio.core.kicad.stackup import Stackup, kicad_default, preset
from kicad_rf_studio.core.kicad.tracer import Chain, ChainPart, adopt
from kicad_rf_studio.core.messages import KrsError
from test_gates import project_of
from test_project import antenna_dict

FIX = Path(__file__).parent / "fixtures"


def stackup_with_duplicate_copper_names() -> Stackup:
    """KiCad's 2-layer rule with both copper layers called F.Cu, as copper sub-layers may be named."""
    s = kicad_default(0.8)
    return replace(s, layers=tuple(replace(x, name="F.Cu") if x.kind == "copper" else x for x in s.layers))


def load_fixture_project(name):
    """The board and its project, built by hand (ruling R-P2-1): coupon_ms has no pads for `new` to trace."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    return b, {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "stackup": b.stackup.to_json(),
               "chain": {"start": "", "end": "", "nets": ["LINE"], "series": [], "shunt": []}, "ports": []}


def chain_of(p) -> Chain:
    c = p["chain"]
    series, shunt = (tuple(ChainPart(x["ref"], tuple(x["pads"]), tuple(x["nets"])) for x in c[key])
                     for key in ("series", "shunt"))
    return Chain(c["start"], c["end"], tuple(c["nets"]), series, shunt)


def zstack_of(p, b):
    return zstack(Stackup.from_json(p["stackup"]), b.copper_layers)


def test_zstack_by_position():  # two copper layers both named "F.Cu" in the stackup (sub-layer naming)
    zs = zstack(stackup_with_duplicate_copper_names(), ("F.Cu", "B.Cu"))
    assert [s.copper for s in zs if s.kind == "copper"] == ["B.Cu", "F.Cu"]
    assert zs[0].kind == "mask" and zs[0].z1 == 0.0


def test_zstack_count_mismatch():  # Task 2 ruling: str(KrsError) is the rendered message, so match= cannot see the code
    with pytest.raises(KrsError) as e:
        zstack(preset("jlcpcb-2l", 1.6, 2), ("F.Cu", "In1.Cu", "B.Cu"))
    assert e.value.code == "E_STACKUP_LAYERS" and e.value.params == {"stackup": 2, "board": 3}


def test_zstack_heights_from_the_bottom_copper():
    zs = zstack(kicad_default(0.8), ("F.Cu", "B.Cu"))
    assert [(s.kind, s.z0, s.z1) for s in zs] == [
        ("mask", -0.01, 0.0), ("copper", 0.0, 0.035), ("dielectric", 0.035, 0.745), ("copper", 0.745, 0.78),
        ("mask", 0.78, 0.79)]
    assert (zs[2].eps_r, zs[2].tan_d, zs[1].eps_r, zs[0].eps_r) == (4.5, 0.02, None, 3.3) and substrate_h(zs) == 0.71


def test_coarse_cell():
    assert coarse_cell(3.0195e9, 4.5) == pytest.approx(299.792458 / 3.0195 / math.sqrt(4.5) / 20, rel=1e-9)


def test_roi_on_coupon_ms():
    b, p = load_fixture_project("coupon_ms")
    r = build_region(b, chain_of(p), p["ports"], zs := zstack_of(p, b), f_max(p))
    h = substrate_h(zs)
    x0, y0, x1, y1 = r.roi.bounds
    assert (x0, x1) == pytest.approx((99, 121))  # R-P2-1: the capped LINE (99.325..120.675) + 3h passes the outline
    assert y1 - y0 == pytest.approx(min(1.35 + 6 * h, 10), abs=1e-6)  # 3h each side, clipped to the 10 mm board
    margin = 4 + 8 * r.coarse
    assert r.walls[0] == pytest.approx(x0 - margin) and r.walls[1] == pytest.approx(x1 + margin)
    assert r.crop.bounds == pytest.approx((r.walls[0] - 1, r.walls[2] - 1, r.walls[1] + 1, r.walls[3] + 1))
    assert r.walls[4] == pytest.approx(zs[0].z0 - margin) and r.walls[5] == pytest.approx(zs[-1].z1 + margin)


def test_roi_covers_net_areas_part_pads_and_port_references(mini_board):
    # y points down in the file: C1 shunts the SIG track to a GND pad 20 mm up, SIG has a pour below the track, and
    # the two ports take J1's GND pad and a copper point as references. No outline, so nothing is clipped.
    b = mini_board(
        '(segment (start 0 0) (end 10 0) (width 0.2) (layer "F.Cu") (net "SIG") (uuid "t1")) '
        '(zone (net "SIG") (layer "F.Cu") (uuid "z1") (polygon (pts (xy 0 2) (xy 4 2) (xy 4 6) (xy 0 6))) '
        '(filled_polygon (layer "F.Cu") (pts (xy 0 2) (xy 4 2) (xy 4 6) (xy 0 6)))) '
        '(footprint "Lib:C" (layer "F.Cu") (uuid "f1") (at 10 0) (property "Reference" "C1") '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "SIG") (uuid "p1")) '
        '(pad "2" smd rect (at 0 -20) (size 1 1) (layers "F.Cu") (net "GND") (uuid "p2"))) '
        '(footprint "Lib:J" (layer "F.Cu") (uuid "f2") (at -20 0) (property "Reference" "J1") '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "GND") (uuid "p3")))')
    chain = Chain("C1.1", "C1.1", ("SIG",), (), (ChainPart("C1", ("C1.1", "C1.2"), ("SIG", "GND")),))
    ports = [{"signal": "C1.1", "reference": {"pad": "J1.1", "uuid": "p3"}},
             {"signal": "C1.1", "reference": {"point": [30.0, 0.0], "layer": "F.Cu"}}]
    zs = zstack(kicad_default(0.8), b.copper_layers)
    g = 3 * substrate_h(zs)
    roi = build_region(b, chain, ports, zs, 1e9).roi
    assert roi.bounds == pytest.approx((-20.5 - g, -6 - g, 30 + g, 20.5 + g))


def test_margin_scale_multiplies_the_wall_margin():  # D-12, spec 9.4 criterion 4
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    zs = zstack(Stackup.from_json(p["stackup"]), board.copper_layers)
    one, two = (build_region(board, chain_of(p), p["ports"], zs, 3.0195e9, 3.0, s) for s in (1.0, 2.0))
    margin = WALL_MM + WALL_CELLS * one.coarse
    assert one.walls[1] - one.roi.bounds[2] == pytest.approx(margin, abs=2e-6)
    assert two.walls[1] - two.roi.bounds[2] == pytest.approx(2 * margin, abs=2e-6)


# --- Stage 3 plan 2, task 3: an antenna's band and region ------------------------------------------------------


def test_the_band_of_an_antenna_is_its_pulse_band():  # design 5.2, 5.4
    d = antenna_dict()
    assert band(d) == (1.84e9, 2.99e9) and f_max(d) == 2.99e9 and air_cell(2.99e9) == pytest.approx(5.01325, abs=1e-5)
    assert air_gap(2.4e9) == 31.228381  # λ/4 at f_lo, to 1e-6 mm
    v1 = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1}
    assert band(v1) == (457.5e6, pytest.approx(3.0195e9)) and f_max(v1) == band(v1)[1]


def test_an_antennas_region_is_the_whole_board_with_the_measured_region_as_its_roi():  # design 5.2, 5.3
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    adopt(b, "AE1", "RF")
    zs = zstack(b.stackup, b.copper_layers)
    r = board_region(b, trace_chain(b, "U1.1", "AE1.1", antenna="AE1"),
                     [{"signal": "U1.1", "reference": {"pad": "U1.2", "uuid": ""}}], zs, 2.99e9)
    c = coarse_cell(2.99e9, 4.5)
    assert r.coarse == c and r.walls == tuple(round(v, 6) for v in (87 - c, 127 + c, -124 - c, -94 + c,
                                                                     zs[0].z0 - c, zs[-1].z1 + c))
    assert r.crop.bounds == (r.walls[0], r.walls[2], r.walls[1], r.walls[3])
    # the antenna, the feed and U1's pins 1-2, 6 substrate heights past them, cut at the outline (the prototype's)
    assert r.roi.bounds == pytest.approx((87.0, -117.21, 106.81, -94.0), abs=1e-6)


# --- Stage 4 plan 1, task 4: the dielectric next to each layer -------------------------------------------------
SIX = (Slab("copper", 0.0, 0.035, None, None, "B.Cu"), Slab("dielectric", 0.035, 0.235, 4.3, 0.02, None),
       Slab("copper", 0.235, 0.27, None, None, "In4.Cu"), Slab("dielectric", 0.27, 0.57, 4.5, 0.02, None),
       Slab("copper", 0.57, 0.605, None, None, "In3.Cu"), Slab("dielectric", 0.605, 0.755, 4.3, 0.02, None),
       Slab("copper", 0.755, 0.79, None, None, "In2.Cu"), Slab("dielectric", 0.79, 1.09, 4.5, 0.02, None),
       Slab("copper", 1.09, 1.125, None, None, "In1.Cu"), Slab("dielectric", 1.125, 1.325, 4.3, 0.02, None),
       Slab("copper", 1.325, 1.36, None, None, "F.Cu"))  # bottom up: 0.2, 0.3, 0.15, 0.3 and 0.2 mm between coppers


def test_an_si_lines_substrate_is_the_thinnest_dielectric_next_to_its_layers():  # Stage 4 design 5.3
    assert substrate_h(SIX) == substrate_h(SIX, ["F.Cu"]) == 0.2  # v1's and the antenna's: the top layer's
    assert substrate_h(SIX, ["B.Cu"]) == 0.2  # a bottom microstrip: the dielectric above it
    assert substrate_h(SIX, ["In3.Cu"]) == 0.15  # a stripline 0.3 mm over In4.Cu and 0.15 mm under In2.Cu
    assert substrate_h(SIX, ["In4.Cu"]) == 0.2 and substrate_h(SIX, ["F.Cu", "In3.Cu"]) == 0.15
    with pytest.raises(KeyError):
        substrate_h(SIX, ["In5.Cu"])
