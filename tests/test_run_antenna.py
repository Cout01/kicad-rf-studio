# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import json
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import FIX, antenna_project

FOUR = ["antenna_summary.csv", "antenna_summary.png", "farfield.csv", "layout.s1p"]


def events(run_dir):
    return [json.loads(line)["code"] for line in (Path(run_dir) / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def files(pj):
    return sorted(f.name for f in (pj.parent / "results").iterdir())


def test_an_antenna_run_records_its_far_field_and_writes_its_files(tmp_path, calibrated):  # design 5.5, 5.6
    pj = antenna_project(tmp_path / "p")
    data = load_project(pj)
    save_project(pj, {**data, "far_field": {**data["far_field"], "step_deg": 10}})
    assert pipeline.run(pj) == 0
    results = load_project(pj)["results"]
    assert list(results["far_field"]) == ["sphere", "elevation", "azimuth"]
    assert all((Path(results["run_dir"]) / v).is_file() for v in results["far_field"].values())
    job, = Path(results["run_dir"]).glob("job-0-nf2ff-*/job.json")
    assert json.loads(job.read_text(encoding="utf-8"))["step_deg"] == 10  # the project's step reaches the transform
    assert files(pj) == FOUR
    codes = events(results["run_dir"])
    assert "W_NOT_TWO_PORT" not in codes and "I_LOSS_BUDGET" not in codes  # no loss budget (design 5.6)
    assert codes.index("I_ANTENNA_RELATIVE") < codes.index("I_ANTENNA_FAR_FIELD") and codes[-5:] == list(ANTENNA_LIMITS)
    assert pipeline.retune(pj, []) == 0 and files(pj) == FOUR  # retune rewrites them from the stored transform


def test_a_failed_transform_keeps_s_and_says_so(tmp_path, calibrated, monkeypatch):  # design 5.5
    def fail(*_, **__):
        raise KrsError("E_WORKER_FAILED", job="T_JOB_FAR_FIELD", exit_code=1, log="log.txt")

    monkeypatch.setattr(pipeline, "far_field", fail)
    pj = antenna_project(tmp_path / "p")
    assert pipeline.run(pj) == 2
    results = load_project(pj)["results"]
    assert results["far_field"] is None and "E_WORKER_FAILED" in events(results["run_dir"])
    assert files(pj) == ["antenna_summary.png", "layout.s1p"]


def test_a_stopped_transform_keeps_the_runs_s(tmp_path, calibrated, monkeypatch):  # Stage 1 7.8: a kept run is saved
    def stop(*_, **__):
        raise KeyboardInterrupt  # STOP or Ctrl+C during the transform

    monkeypatch.setattr(pipeline, "far_field", stop)
    pj = antenna_project(tmp_path / "p")
    with pytest.raises(KeyboardInterrupt):
        pipeline.run(pj)
    results = load_project(pj)["results"]
    assert [j["verdict"] for j in results["jobs"]] == ["converged"] and results["far_field"] is None
    assert files(pj) == ["antenna_summary.png", "layout.s1p"]


def test_a_part_port_antenna_run_has_s11_and_no_far_field(tmp_path, calibrated):  # design 5.5; plan 3's branch
    pj = antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb")
    assert pipeline.run(pj) == 0
    assert load_project(pj)["results"]["far_field"] is None
    assert files(pj) == ["antenna_summary.png", "chain.s1p", "layout.s4p"]


# --- beyond the brief's tests ------------------------------------------------------------------------------------


def test_the_summary_csv_gives_each_far_field_frequency_its_own_s11(tmp_path, calibrated):  # design 5.6
    pj = antenna_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    project = load_project(pj)
    text = (pj.parent / "results" / "antenna_summary.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [row["f_hz"] for row in rows] == ["2400000000.0", "2449999872.0"]  # the fixture's file leads with f0, 2450
    for row in rows:  # S11 there 1.4 dB apart: each row's own, the layout at that one frequency
        s11 = layout(project, project["results"], np.array([float(row["f_hz"])])).s[0, 0, 0]
        assert float(row["s11_db"]) == pytest.approx(20 * np.log10(abs(s11)), abs=1e-9)
