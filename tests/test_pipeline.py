# SPDX-License-Identifier: GPL-3.0-or-later
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.mesh import gates
from kicad_rf_studio.core.mesh.gates import dt_floor_reference
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.pipeline import build_model, load, project_path, stops
from test_cli_cost import EDGE, FIX, SEG, by_hand, zone
from test_cli_new import run_new
from test_gates import BAD_Y


def lpf(tmp_path, **edits):
    _, pj = run_new(tmp_path, "--lid-height", "2.5")  # tests/test_cli_new.py
    save_project(pj, {**load_project(pj), **edits})
    return pj


def test_a_folder_stands_for_its_project_json(tmp_path):  # O-5
    assert project_path(str(tmp_path)) == tmp_path / "project.json"
    assert project_path(str(tmp_path / "p.json")) == tmp_path / "p.json"


def test_load_warns_when_the_board_changed_since_new(tmp_path):  # C-30
    board = tmp_path / "b.kicad_pcb"
    board.write_bytes((FIX / "coupon_gcpw_pads.kicad_pcb").read_bytes())
    main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    board.write_bytes(board.read_bytes() + b"\n")
    assert load(tmp_path / "p" / "project.json")[3][0] == ("W_BOARD_CHANGED", {"path": str(board.resolve())})


def test_a_section_off_the_top_copper_warns(tmp_path, mini_board_file):  # C-9
    path = mini_board_file(EDGE + SEG.format(5, 10, 35, 10, 0.6, "B.Cu", "SIG", "s")
                           + zone("F.Cu", "GND", 0, 0, 40, 20))
    pj = by_hand(tmp_path / "p" / "project.json", path, nets=("SIG",), stackup=kicad_default(0.8))
    assert ("W_OFF_TOP_LAYER", {"net": "SIG", "layer": "B.Cu"}) in load(pj)[3]


def test_the_lpf915_model(tmp_path):
    p, board, g, notes = load(lpf(tmp_path))
    m = build_model(p, board, g)
    assert stops(notes) == 0 and m.blocked == []
    assert [(q["name"], q["part"]) for q in m.spec["ports"]] == [
        ("P1", False), ("P2", False), ("C1", True), ("L1", True), ("C2", True), ("C3", True)]
    assert m.dt_ref == dt_floor_reference(m.mesh)


def test_an_off_chain_part_made_a_port_adds_a_run_and_changes_the_hash(tmp_path):  # spec 5.7, S-4
    p, board, g, _ = load(lpf(tmp_path))
    q = {**p, "others": [{**p["others"][0], "role": "port"}]}
    m, n = build_model(p, board, g), build_model(q, board, build_geometry(board, q))
    assert [x["name"] for x in n.spec["ports"]] == [x["name"] for x in m.spec["ports"]] + ["C4"]
    assert spec_hash(n.spec) != spec_hash(m.spec)


def test_a_grid_part_goes_to_the_grid_with_its_value_and_is_no_port(tmp_path):  # beyond the brief: its one branch
    p, board, g, _ = load(lpf(tmp_path))
    shunt = p["chain"]["shunt"]
    q = {**p, "chain": {**p["chain"], "shunt": [{**shunt[0], "role": "grid"}, *shunt[1:]]}}
    m = build_model(q, board, build_geometry(board, q))
    assert [x["name"] for x in m.spec["ports"]] == ["P1", "P2", "C1", "L1", "C3"]
    assert [(x["name"], x["R"], x["C"]) for x in m.spec["grid"]] == [("C2", None, 3.3e-12)]


def test_lpf915_at_mesh_n_3_stops_at_fit2d_but_keeps_its_model(tmp_path):  # O-3, R-P2-21
    p, board, g, _ = load(lpf(tmp_path, mesh={"n": 3}))
    m = build_model(p, board, g)
    (code, params), = m.blocked
    assert (code, params["net"], params["n"]) == ("E_FIT2D_FINE", "RF_B", 3) and m.spec is not None


def test_a_failed_edge_lint_leaves_no_model(tmp_path, monkeypatch):
    p, board, g, _ = load(lpf(tmp_path))
    monkeypatch.setattr(gates, "build_mesh", lambda *a, **k: BAD_Y)  # tests/test_gates.py
    m = build_model(p, board, g)
    assert (m.mesh, m.spec, [c for c, _ in m.blocked]) == (None, None, ["E_EDGE_LINT"])


def test_a_missing_lid_height_is_a_refusal(tmp_path):
    assert stops(load(lpf(tmp_path, lid_height_mm=None))[3]) == 2
