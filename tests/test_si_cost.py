# SPDX-License-Identifier: GPL-3.0-or-later
import json
from dataclasses import replace
from functools import partial

import pytest

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.cs2d import pair
from kicad_rf_studio.core.geometry.sections import BOX_H, cross_section
from kicad_rf_studio.core.geometry.zstack import substrate_h
from kicad_rf_studio.core.mesh.gates import check_fit2d, fit2d
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import GATES, GATES_SI, load_project, save_project
from test_cli_si import FIX, QSPI, si_project


def events(run_dir):
    return [(e["code"], e["params"]) for e in map(json.loads, (run_dir / "events.jsonl").read_text("utf-8").splitlines())]


def readout(tmp_path, board):
    project, board, geom, _ = pipeline.load(si_project(tmp_path, board))
    return pipeline.si_readout(board, geom, project)


def test_the_si_cost_lists_the_2d_table_and_the_runs(tmp_path, calibrated):  # design 5.9
    (tmp_path / "cost").mkdir()
    assert pipeline.cost(si_project(tmp_path / "p"), tmp_path / "cost") == 0
    ev = events(tmp_path / "cost")
    codes = {c for c, _ in ev}
    assert "I_SI_2D_HEADER" in codes and not {"I_2D_HEADER", "W_GATE_LIMITS", "W_GATE_LIMITS_SI",
                                              "I_SI_SHORT_ROUTE"} & codes
    long = [p for c, p in ev if c == "I_SI_2D_PAIR" and p["length_mm"] == "17.490"]  # the long run, a 0.25 mm gap
    assert {p["net"] for p in long} == {"USB_D+", "USB_D-"}
    assert all(p["verdict"] == "T_IN_BAND" and 81 <= float(p["z_diff"]) <= 99 for p in long)
    assert {p["net"] for c, p in ev if c == "I_SI_2D_PAIR"} >= {"MCU_D+", "MCU_D-"}  # legs microns apart still pair
    legs = [p for c, p in ev if c == "I_SI_2D_LEG"]  # the four jogs to and from U2's rows, each partner elsewhere
    assert len(legs) == 4 and all(float(p["z_diff"]) == pytest.approx(2 * float(p["z0"]), abs=0.011) for p in legs)
    assert dict(ev)["I_SI_COST_JOBS"] == {"lines": 4, "victims": 2, "parts": 2}
    assert dict(ev)["I_SI_COST_SPEED"] == {"ratio": f"{runs.SI_SPEED:g}"}
    assert dict(ev)["I_SI_COST_RING"]["ceiling_ns"] == "36"
    assert [p["verdict"] for c, p in ev if c == "I_SI_2D_LINE"] == ["T_VICTIM"]  # AUX, the victim's one section


def test_the_neck_down_reads_out_of_the_band(tmp_path):  # design 5.9; P4-F's fixture
    neck = [p for c, p in readout(tmp_path, FIX / "usb2_hs_neck.kicad_pcb") if c == "I_SI_2D_PAIR"
            and p["width_mm"] == "0.200"]
    assert len(neck) == 2 and all(p["verdict"] == "T_OUT_OF_BAND" and float(p["z_diff"]) > 99 for p in neck)


def test_a_short_route_is_said_so_and_the_clock_reads_in_band(tmp_path):  # design 5.9: under a sixth of 1 ns
    rows = readout(tmp_path, QSPI)
    lines = dict(rows)
    assert lines["I_SI_SHORT_ROUTE"]["net"] == "QSPI_CLK" and float(lines["I_SI_SHORT_ROUTE"]["delay_ps"]) < 1000 / 6
    assert {p["verdict"] for c, p in rows if c == "I_SI_2D_LINE"} == {"T_IN_BAND"}  # 50.0 Ω, its B.Cu run too


def test_fit2d_checks_a_pairs_coupled_sections(tmp_path):  # design 5.3, 5.9
    project, board, geom, _ = pipeline.load(si_project(tmp_path))
    mesh = pipeline.build_model(project, board, geom).mesh
    coupled = [f for f in fit2d(geom, mesh) if f.z0_ref > 70]  # a Zdiff of about 90 Ω, beside each leg's own 51 Ω
    table = {p["net"]: float(p["z_diff"]) for c, p in pipeline.si_readout(board, geom, project)
             if c == "I_SI_2D_PAIR" and p["length_mm"] == "17.490"}
    long = [f for f in coupled if f.section.length == 17.49]
    assert {f.section.net for f in long} == {"USB_D+", "USB_D-"} and max(f.err for f in coupled) <= 0.03
    assert all(f.z0_ref == pytest.approx(table[f.section.net], abs=0.006) for f in long)  # cs2d's pair, not the mesh
    fits = fit2d(geom, replace(mesh, y=mesh.y[(mesh.y <= -100.125) | (mesh.y >= -99.875)]))  # no line in the gap
    assert max(f.err for f in fits if f.z0_ref > 70) > 0.03
    with pytest.raises(KrsError) as e:
        check_fit2d(fits, 0.03, 2)
    assert e.value.code == "E_FIT2D"


def test_a_widely_spaced_pairs_box_runs_past_both_legs(tmp_path):  # final review F1
    _, _, geom, _ = pipeline.load(si_project(tmp_path))
    sec = next(s for s in geom.sections if s.net == "USB_D+" and s.width == 0.6 and s.length == 5)  # through U2
    h = substrate_h(geom.zs, (sec.layer,))
    cut = partial(cross_section, sec, geom.pieces, geom.zs, geom.masks.get(sec.layer), "exact", h=h,
                  partners=geom.partners(sec.net))  # as si_readout cuts it
    cs = cut()
    assert pair(cs).z_diff == pytest.approx(pair(cut(box_h=40)).z_diff, rel=0.005)  # the legs 1.3 mm apart
    p, n = (r for r in cs.conductors if r.role == "signal")
    assert min(min(p.x0, n.x0) - cs.box[0], cs.box[1] - max(p.x1, n.x1)) >= BOX_H * h - 1e-6  # on the 1e-6 mm grid


def test_an_si_cost_past_two_hours_is_warned_and_its_gates_are_its_own(tmp_path):  # design 5.9; A-43
    project, board, geom, _ = pipeline.load(si_project(tmp_path))
    model, setup = pipeline.build_model(project, board, geom), {"dt": 1e-13, "node": [0, 1, 2, 3]}
    assert "W_SI_LONG_RUN" in dict(pipeline.cost_notes(model, project, setup, 4, 1, 1.0))  # 1 MC/s: days
    assert "W_SI_LONG_RUN" not in dict(pipeline.cost_notes(model, project, setup, 4, 8, 1e9))
    assert pipeline.gate_lines(GATES_SI, GATES_SI) == [] and pipeline.gate_lines(GATES) == []
    assert pipeline.gate_lines(GATES, GATES_SI) == [("W_GATE_LIMITS_SI", {"fit2d_limit": "0.03", "dt_floor": "0.8"})]


def test_a_debye_models_cost_counts_its_cells_at_their_weight(tmp_path):  # design 5.9; ruling D-4
    setup = {"dt": 1e-13, "node": [0, 1, 2, 3]}
    pj = si_project(tmp_path / "d")
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    project, board, geom, _ = pipeline.load(pj)
    notes = dict(pipeline.cost_notes(pipeline.build_model(project, board, geom), project, setup, 8, 2, 100.0))
    assert runs.DEBYE_WEIGHT == 108.8  # gate P4-D's D2 run at the calibration's 4 threads a job (Task 15's refit)
    assert notes["I_SI_COST_DEBYE"] == {"mcells": "1.11", "weight": f"{runs.DEBYE_WEIGHT:g}", "poles": 4}
    weighted = 3745434 + (runs.DEBYE_WEIGHT - 1) * 1110091  # at the d fill (gate P4-C)
    assert notes["I_COST_TIME"]["time"] == pipeline.duration(4 * weighted * (9e-9 / 1e-13) / 100e6)  # 8 runs, 2 at once
    p, b, g, _ = pipeline.load(si_project(tmp_path / "l"))
    assert "I_SI_COST_DEBYE" not in dict(pipeline.cost_notes(pipeline.build_model(p, b, g), p, setup, 8, 2, 100.0))
