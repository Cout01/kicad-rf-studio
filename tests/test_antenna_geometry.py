# SPDX-License-Identifier: GPL-3.0-or-later
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import shapely

import p0
from kicad_rf_studio import cli, pipeline
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import load_project, save_project
from test_antenna_kicad import fp
from test_cli_antenna import FIX, IFA, antenna_project
from test_tracer import smd

LOCAL_X = (-11.85, -11.35, -9.65, -9.15, -7.15, -6.65, -4.95, -4.45, -2.45, -1.95, -0.25, 0.25, 1.65, 2.55)  # SWRA117D


def model_of(pj: Path):
    project, board, geom, notes = pipeline.load(pj)
    return pipeline.build_model(project, board, geom), geom, notes


@pytest.mark.parametrize("name", ["ifa2g4", "ifa2g4_pi", "meander915", "ifa2g4_pi_shift", "ifa2g4_pi_dxp",
                                  "ifa2g4_pi_dxm", "ifa2g4_pi_pour"])
def test_each_antenna_fixture_builds_its_model(tmp_path, name):  # design 5.3; RF 3
    model, geom, notes = model_of(antenna_project(tmp_path, FIX / f"{name}.kicad_pcb"))
    assert model.blocked == [] and model.mesh.d == 0.3 and pipeline.stops(notes) == 0 and geom.antenna
    staircased = [p for code, p in notes if code == "W_STAIRCASED"]
    assert staircased == ([{"net": "RF"}] if name == "meander915" else [])  # SWRA416's 18 diagonals: a warning


def test_the_two_layer_exemption_is_the_antennas_alone(tmp_path):  # design 5.3; v1 byte for byte; RF 3
    project, board, geom, _ = pipeline.load(antenna_project(tmp_path, FIX / "meander915.kicad_pcb"))
    blocked = pipeline.build_model(project, board, replace(geom, antenna=False)).blocked  # v1's lint, as before
    assert [code for code, _ in blocked] == ["E_EDGE_LINT"] and pipeline.build_model(project, board, geom).blocked == []


def test_the_inverted_f_join_is_accepted_and_tied_to_its_pads(tmp_path):  # design 5.3; RF 2
    pj = antenna_project(tmp_path)
    assert pipeline.load(pj)[3] == []  # no W_NETLESS_COPPER, no short, no W_AIR_BOX
    data = load_project(pj)
    data["antenna"]["join"] = []
    save_project(pj, data)
    assert ("E_SHORT_IN_ROI", {"nets": "GND, RF"}) in pipeline.load(pj)[3]


def test_fit2d_measures_the_feed_line_and_never_the_radiator(tmp_path):  # design 5.3
    _, geom, _ = model_of(antenna_project(tmp_path))
    assert [(s.net, s.width, s.length) for s in geom.sections] == [("RF", 0.6, 1.975), ("RF", 1.35, 10.0)]


def test_the_antenna_is_in_the_fine_set_and_its_edges_move_with_it(tmp_path):  # design 5.3: placement
    moved = tmp_path / "moved.kicad_pcb"
    text = IFA.read_text(encoding="utf-8")
    i = text.index("(at 100 100)", text.index('(footprint "RF_Antenna:'))
    moved.write_text(text[:i] + "(at 100.3 100)" + text[i + len("(at 100 100)"):], encoding="utf-8")  # AE1 one d along x
    for board, x in ((IFA, 100.0), (moved, 100.3)):
        model, _, _ = model_of(antenna_project(tmp_path / board.stem, board, (2.4e9, 2.4835e9)))
        assert {round(x + v, 6) for v in LOCAL_X} <= {e for e, _ in model.mesh.edges["x"]}


def test_every_shield_is_a_lid_candidate_and_one_gets_it(tmp_path):  # design 5.3; the "one lid" ruling
    def frame(ref, x, y, s):  # a shield: GND pads at the corners of an s mm square
        pads = (smd(k, "GND", x=dx, y=dy) for k, (dx, dy) in enumerate(((0, 0), (s, 0), (0, s), (s, s)), 1))
        return fp(ref, "Lib:Shield", *pads, at=f"{x} {y}")

    lib = "Resistor_SMD:R_0402_1005Metric"
    shields = (frame("SH1", 108, 104, 8) + fp("R9", lib, smd(1, "N9"), smd(2, "GND", x=1), at="112 108", value="1k")
               + frame("SH2", 116, 116, 4) + fp("R8", lib, smd(1, "N8"), smd(2, "GND", x=1), at="117.5 118", value="1k"))
    board = tmp_path / "shields.kicad_pcb"
    board.write_text(IFA.read_text(encoding="utf-8").rstrip()[:-1] + shields + ")\n", encoding="utf-8")
    pj, notes = cli.new_antenna(board, "U1.1", "AE1", (2.4e9, 2.4835e9), output=tmp_path / "p")
    assert ("W_LID_HEIGHT_MISSING", {"refs": "SH1, SH2"}) in notes  # both, far outside the measured region
    save_project(pj, {**load_project(pj), "lid_height_mm": 1.5})
    _, _, geom, notes = pipeline.load(pj)
    assert geom.lid.ref == "SH1" and ("W_LIDS_LEFT_OUT", {"ref": "SH1", "refs": "SH2"}) in notes


def test_an_air_box_outside_the_tested_setting_is_warned(tmp_path):  # design 5.2; P3-A's MUR twin; RF 5
    pj = antenna_project(tmp_path)
    save_project(pj, {**load_project(pj), "boundary": "mur", "air_gap_mm": 20.0})
    assert ("W_AIR_BOX", {"gap_mm": "20.0", "quarter_mm": "31.2", "boundary": "mur"}) in pipeline.load(pj)[3]


def test_load_refuses_an_antenna_ref_that_is_no_longer_an_antenna(tmp_path):  # final review G3
    pj = antenna_project(tmp_path / "p")
    data = load_project(pj)
    save_project(pj, {**data, "antenna": {**data["antenna"], "ref": "C1"}})
    with pytest.raises(KrsError) as e:
        pipeline.load(pj)
    assert (e.value.code, e.value.params) == ("E_NOT_AN_ANTENNA", {"ref": "C1", "candidates": "AE1"})


BAND = (2.4e9, 2.4835e9)
D = 0.3  # make_fixtures.D_MOVE: one fine cell of the pi board at P3-C's n, which stayed 2 (2026-11-01-p3-c.md)
EDITS: dict = {"copper": "solid"}  # P3-C's edits_2g4 for the 2.4 GHz boards, from its p3c.json


def built(tmp_path, name):
    pj = antenna_project(tmp_path / name, FIX / f"{name}.kicad_pcb", BAND)
    save_project(pj, p0.edit(load_project(pj), EDITS))
    return model_of(pj)[0]


def centres(name):  # pcbnew's pad centres by name, y up (the uuids differ: each board's seed is its name)
    return {v["name"]: v["center"] for v in json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8")).values()}


def test_one_fine_cell_is_the_pi_boards_d(tmp_path):  # ruling 8: d is the fine cell at the copper under P3-C's n
    assert D == round(built(tmp_path, "ifa2g4_pi").mesh.d, 6)


def test_the_shifted_board_is_the_base_translated(tmp_path):  # design 5.11 P3-D; ruling 8
    base, shift = built(tmp_path, "ifa2g4_pi"), built(tmp_path, "ifa2g4_pi_shift")
    for axis, d in (("x", D), ("y", -D), ("z", 0.0)):  # KiCad's +D in y is -D with y up
        a, b = getattr(base.mesh, axis), getattr(shift.mesh, axis)
        assert len(a) == len(b) and np.abs(b - (a + d)).max() <= 1e-6 + 1e-9  # one 1e-6 mm quantum, float slack
    c0, c1 = centres("ifa2g4_pi"), centres("ifa2g4_pi_shift")
    assert c0.keys() == c1.keys() and len(c0) == 18
    assert all(abs(c1[k][0] - c0[k][0] - D) <= 1e-6 and abs(c1[k][1] - c0[k][1] + D) <= 1e-6 for k in c0)
    assert shift.blocked == []


def test_the_moved_front_end_keeps_the_ground_the_fence_and_the_mesh_across(tmp_path):  # ruling 8; r3 Q3
    base = built(tmp_path, "ifa2g4_pi")
    vias = {name: {tuple(v.at) for v in load_board(FIX / f"{name}.kicad_pcb").vias}
            for name in ("ifa2g4_pi", "ifa2g4_pi_dxp", "ifa2g4_pi_dxm")}
    for name, d in (("ifa2g4_pi_dxp", D), ("ifa2g4_pi_dxm", -D)):
        m = built(tmp_path, name)
        assert m.blocked == [] and np.array_equal(m.mesh.y, base.mesh.y) and np.array_equal(m.mesh.z, base.mesh.z)
        assert {round(100 + d + v, 6) for v in LOCAL_X} <= {e for e, _ in m.mesh.edges["x"]}  # AE1 moved by d
        gone, new = vias["ifa2g4_pi"] - vias[name], vias[name] - vias["ifa2g4_pi"]
        assert len(gone) == 3 and sorted((round(x + d, 6), y) for x, y in gone) == sorted(new)  # the to_gnd vias
        assert m.dt_ref == pytest.approx(base.dt_ref, rel=0.01)


def test_the_pour_stays_a_millimetre_from_the_antenna(tmp_path):  # design 5.11 P3-E; r3 Q4
    def gnd(name, layer):  # the GND zone fills on `layer`
        return shapely.union_all([a.polygon for a in load_board(FIX / f"{name}.kicad_pcb").areas
                                  if a.source == "zone" and a.net == "GND" and a.layer == layer])
    b = load_board(FIX / "ifa2g4_pi_pour.kicad_pcb")
    antenna = shapely.union_all([a.polygon for a in b.areas if a.ref == "AE1"] + [p.polygon for p in b.pads("AE1.1")])
    for layer in ("F.Cu", "B.Cu"):
        pour = gnd("ifa2g4_pi_pour", layer).difference(gnd("ifa2g4_pi", layer))
        assert 6.4 <= pour.area <= 6.7 and pour.distance(antenna) >= 0.999  # 8.65 × 0.76 mm above the main zone
    assert built(tmp_path, "ifa2g4_pi_pour").blocked == []
