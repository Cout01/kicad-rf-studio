# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

import pytest

from kicad_rf_studio import cli, pipeline
from kicad_rf_studio.core.project import load_project, save_project
from test_antenna_kicad import fp
from test_cli_antenna import FIX, IFA, antenna_project
from test_tracer import smd

LOCAL_X = (-11.85, -11.35, -9.65, -9.15, -7.15, -6.65, -4.95, -4.45, -2.45, -1.95, -0.25, 0.25, 1.65, 2.55)  # SWRA117D


def model_of(pj: Path):
    project, board, geom, notes = pipeline.load(pj)
    return pipeline.build_model(project, board, geom), geom, notes


@pytest.mark.parametrize("name", ["ifa2g4", "ifa2g4_pi", "meander915"])
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
