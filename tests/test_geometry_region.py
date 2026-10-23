# SPDX-License-Identifier: GPL-3.0-or-later
import math
from dataclasses import replace
from pathlib import Path

import pytest

from kicad_rf_studio.core.geometry.region import WALL_CELLS, WALL_MM, build_region, coarse_cell, f_max
from kicad_rf_studio.core.geometry.zstack import substrate_h, zstack
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.stackup import Stackup, kicad_default, preset
from kicad_rf_studio.core.kicad.tracer import Chain, ChainPart
from kicad_rf_studio.core.messages import KrsError
from test_gates import project_of

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
