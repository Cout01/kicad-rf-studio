# SPDX-License-Identifier: GPL-3.0-or-later
"""The antenna's lines and files that the CLI and the GUI share (Stage 3 design 5.5–5.7, 5.10; plan 5)."""
import csv
import io

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import antenna_project
from test_match_antenna import pi_run


def test_an_antenna_csv_holds_the_projects_exact_far_field_frequencies(tmp_path, calibrated):  # ruling 8
    pj = antenna_project(tmp_path / "p")
    d = load_project(pj)
    save_project(pj, {**d, "far_field": {**d["far_field"], "f_hz": [2.44175e9, 2.4e9, 2.45e9]}})
    assert pipeline.run(pj) == 0  # the fake's transform records 2.45 GHz as float32: 2449999872 Hz
    summary = (pj.parent / "results" / "antenna_summary.csv").read_text(encoding="utf-8")
    assert [row["f_hz"] for row in csv.DictReader(io.StringIO(summary))] == ["2400000000.0", "2450000000.0"]
    far = (pj.parent / "results" / "farfield.csv").read_text(encoding="utf-8").splitlines()
    assert (far[1].split(",")[0], far[-1].split(",")[0]) == ("2400000000.0", "2450000000.0")


def test_every_far_field_read_takes_the_projects_frequencies(tmp_path, calibrated, monkeypatch):  # ruling 8
    pj = pi_run(tmp_path, monkeypatch)
    seen, real = [], pipeline.far_field_of
    monkeypatch.setattr(pipeline, "far_field_of",
                        lambda paths, waves, f_hz=(): seen.append(list(f_hz)) or real(paths, waves, f_hz))
    assert pipeline.verify(pj) == 0  # verify_farfield.csv and verify_summary.csv
    assert pipeline.retune(pj, [], lambda code, params: None) == 0  # the what-if η_tot
    assert pipeline.antenna_result(pj)["source"] == "T_VERIFY"  # compare.csv
    assert seen == [load_project(pj)["far_field"]["f_hz"]] * 3
