# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.post.outputs import LIMITS, grid_lines
from kicad_rf_studio.core.post.waves import grid, layout
from kicad_rf_studio.core.project import load_project, parts, save_project
from networks import C_BOX, read_s, star, terminate_np
from test_cli_cost import FIX, fail
from test_run import coupon, lpf_loads, lpf_project, lpf_run, result_codes

F, _ = grid(915e6, 3, 1.1)


def verified(tmp_path, monkeypatch):
    """lpf915 run on the network fake, its run's operator dump stood in for (the fake writes none) and the cell C
    read as 6e-16 F: the project file."""
    pj = lpf_run(tmp_path, monkeypatch)  # tests/test_run.py
    (Path(load_project(pj)["results"]["run_dir"]) / "job-0-setup" / "operator_dump.vtr").write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    return pj


def test_verify_runs_the_parts_in_the_grid_and_compares(tmp_path, calibrated, monkeypatch, capsys):  # spec 7.6
    pj = verified(tmp_path, monkeypatch)
    before = load_project(pj)["results"]
    assert main(["verify", str(pj)]) == 0
    d = load_project(pj)
    v = d["verify"]
    assert d["results"] == before and v["base_hash"] == before["model_hash"] != v["model_hash"]
    assert set(v) == {"model_hash", "base_hash", "values", "run_dir", "jobs", "compare"}
    assert v["values"] == {"C1": "100pF", "L1": "15nH", "C2": "3.3pF", "C3": "3.3pF"}
    assert [(j["port"], j["verdict"]) for j in v["jobs"]] == [("P1", "converged"), ("P2", "converged")]  # C-38: P jobs
    model = json.loads((Path(v["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert [g["name"] for g in model["grid"]] == ["C1", "L1", "C2", "C3"] and [q["name"] for q in model["ports"]] == [
        "P1", "P2"]
    assert (model["grid"][0]["C"], model["grid"][1]["L"], model["grid"][1]["C"]) == (
        pytest.approx(100e-12 + C_BOX), 15e-9, 6e-16)
    retuned = terminate_np(star(F, 6), [0, 1], lpf_loads(None))  # ideal values ∥ C_box (C-38)
    assert v["compare"]["ds_max"] == pytest.approx(np.abs(star(F, 2) - retuned).max(), abs=1e-4)
    file = pj.parent / "results" / "verify.s2p"
    assert np.abs(read_s(file) - star(F, 2)).max() <= 1e-5
    assert b"in grid: L1 15nH as L 1.5e-08 H with the cell's C 6e-16 F" in file.read_bytes()
    assert result_codes(v["run_dir"]) == ["I_VERIFY_RESULTS", "I_VERIFY_COMPARE", "I_VERIFY_NO_NULLS", "I_PASSIVITY",
                                          "I_RECIPROCITY", "W_VERIFY_LOSS_BUDGET", "I_OUTPUTS", "I_VERIFY_SCOPE",
                                          *LIMITS]
    assert (pj.parent / "results" / "chain.s2p").is_file()  # retune's files stay


def test_verify_stores_nothing_when_a_job_keeps_no_s(tmp_path, calibrated, monkeypatch):  # C-38
    pj = verified(tmp_path, monkeypatch)
    monkeypatch.setenv("KRS_FAKE", "nan")
    assert main(["verify", str(pj)]) == 4 and "verify" not in load_project(pj)


@pytest.mark.parametrize("case", ["no results", "single trace", "rotated"])
def test_verify_refuses_before_any_run(tmp_path, calibrated, capsys, case):  # C-36
    if case == "no results":
        pj, line = lpf_project(tmp_path), render("E_NO_RESULTS")
    elif case == "single trace":
        pj, line = coupon(tmp_path), render("E_VERIFY_NO_PARTS")
    else:
        out = tmp_path / "lpf915-45"
        assert main(["new", str(FIX / "lpf915-45.kicad_pcb"), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz",
                     "-o", str(out)]) == 0
        pj = out / "project.json"
        save_project(pj, {**load_project(pj), "allow_curve_port": True, "lid_height_mm": 2.5})
        line = render("E_VERIFY_CURVE", ref="L1")
    capsys.readouterr()
    assert main(["verify", str(pj)]) == 2 and capsys.readouterr().err == line + "\n"
    assert not (calibrated / "runs").exists()


@pytest.mark.parametrize(("edit", "line"), [
    ({"t_max_s": 30e-9}, render("E_RESULTS_STALE")),
    ("value", render("E_VERIFY_VALUE", ref="C2", value="x"))])
def test_verify_refuses_stale_results_and_unreadable_values(tmp_path, calibrated, monkeypatch, capsys, edit, line):
    pj = verified(tmp_path, monkeypatch)
    d = load_project(pj)
    if edit == "value":
        parts(d)["C2"]["value"] = "x"  # not in the model hash
    else:
        d.update(edit)
    save_project(pj, d)
    capsys.readouterr()
    assert main(["verify", str(pj)]) == 2 and line in capsys.readouterr().out.splitlines()
    assert "verify" not in load_project(pj)


def test_verify_needs_two_external_ports(tmp_path, calibrated, monkeypatch, capsys):  # final review F3
    pj = lpf_project(tmp_path)
    d = load_project(pj)
    del d["ports"][1]  # a hand edit; run accepts it with W_NOT_TWO_PORT, but compare() reads S21 and S11
    save_project(pj, {**d, "results": {"jobs": []}})  # the refusal comes before the results are read
    monkeypatch.setattr(subprocess, "Popen", fail)  # tests/test_cli_cost.py: no worker starts
    capsys.readouterr()
    assert main(["verify", str(pj)]) == 2 and capsys.readouterr().err == render("E_VERIFY_PORTS", ports="1") + "\n"


# --- beyond the brief's tests ------------------------------------------------------------------------------------


def test_grid_lines_say_what_each_part_sat_in_the_grid_as():  # C-36, C-37: lpf915 has no R part port
    grid = [{"name": "R9", "R": 47.0, "C": None},  # a grid part of the run itself: not verify's, so no line
            {"name": "C1", "R": None, "C": 1.0002e-10}, {"name": "R1", "R": 0.0, "C": None},
            {"name": "L1", "R": None, "C": 6e-16, "L": 1.5e-08}]
    assert grid_lines(grid, {"C1": "100pF", "R1": "0R", "L1": "15nH"}) == [
        "in grid: C1 100pF as C 1.0002e-10 F (value + C_box)", "in grid: R1 0R as R 0 ohm",
        "in grid: L1 15nH as L 1.5e-08 H with the cell's C 6e-16 F"]


def test_verify_reports_each_null_and_its_shift(tmp_path, calibrated, monkeypatch):  # C-39: the star has no null
    pj = verified(tmp_path, monkeypatch)
    nulls = [{"f_hz": 1.83e9, "shift": 0.0123}, {"f_hz": 2.5e9, "shift": None}]
    monkeypatch.setattr(pipeline, "compare", lambda *a: {"ds21_db_f0": 0.0, "ds11_f0": 0.0, "ds_max": 0.0,
                                                          "nulls": nulls})
    assert main(["verify", str(pj)]) == 0
    v = load_project(pj)["verify"]
    a_db = layout(load_project(pj), v).a_db  # verify's own excitation level, at the grid point nearest each null
    at = [f"{a_db[np.abs(F - n['f_hz']).argmin()]:.1f}" for n in nulls]
    events = (Path(v["run_dir"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [(e["code"], e["params"]) for e in map(json.loads, events) if e["kind"] == "result"][2:4] == [
        ("I_VERIFY_NULL", {"f_mhz": "1830.0", "a_db": at[0], "shift_pct": "+1.23"}),
        ("W_VERIFY_NULL_UNMATCHED", {"f_mhz": "2500.0", "a_db": at[1]})]
