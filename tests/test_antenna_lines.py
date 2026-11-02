# SPDX-License-Identifier: GPL-3.0-or-later
"""The antenna's lines and files that the CLI and the GUI share (Stage 3 design 5.5–5.7, 5.10; plan 5)."""
import csv
import io

import numpy as np
import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS
from kicad_rf_studio.core.post.waves import layout
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


def fail(*args, **kwargs):
    raise AssertionError("read again")


def gone(*args, **kwargs):  # a far-field file moved or deleted after current_verify looked
    raise KrsError("E_RESULTS_WAVES", path="P")


def test_the_antenna_lines_are_its_outputs_lines_and_read_nothing_given_their_far_field(
        tmp_path, calibrated, monkeypatch):  # Stage 3 design 5.7, 5.10; Review Focus 3
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.verify(pj) == 0
    d = load_project(pj)
    res = pipeline.chain_results(pj, d, errors_as_lines=True)
    lines, far, far_lay = pipeline.antenna_lines(pj, d, res, errors_as_lines=True)
    pngs, png = [], pipeline.antenna_png
    monkeypatch.setattr(pipeline, "antenna_png", lambda *args: pngs.append(args[3]) or png(*args))
    outputs = pipeline.antenna_outputs(pj, d, "x", errors_as_lines=True)
    assert outputs[:len(lines)] == lines and [c for c, _ in outputs[len(lines):]] == [
        "I_WHAT_IF", "I_OUTPUTS", *ANTENNA_LIMITS]
    assert pngs == [None]  # verify's far field goes into no file of the run's (design 5.7): two panels, as now
    assert [c for c, _ in lines].count("I_ANTENNA_ETA_WHAT_IF") == 2  # the fake verify's far field: 2 frequencies
    assert np.array_equal(far["sphere"].f, pipeline.far_of(d["verify"], d)["sphere"].f)
    assert far_lay.f.tolist() == sorted(far["sphere"].f.tolist())
    for name in ("far_of", "current_verify", "layout"):
        monkeypatch.setattr(pipeline, name, fail)
    again, same, lay = pipeline.antenna_lines(pj, d, res, far=far, far_lay=far_lay)
    assert again == lines and same is far and lay is far_lay
    assert pipeline.antenna_lines(pj, d, res, far=None)[0][-1] == (
        "I_ANTENNA_NO_FAR_FIELD", {"command": pipeline.command_line("kicad-rf-studio", "verify", str(pj))})


def test_a_runs_far_field_is_in_its_lines_and_one_that_cannot_be_read_is_a_line(tmp_path, calibrated, monkeypatch):
    pj = antenna_project(tmp_path / "m0")  # M = 0: its run is its far-field run (design 5.5)
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    res = pipeline.chain_results(pj, d)
    lines, far, far_lay = pipeline.antenna_lines(pj, d, res)
    assert [c for c, _ in lines].count("I_ANTENNA_FAR_FIELD") == 2 and far_lay is None and len(far["sphere"].f) == 2
    monkeypatch.setattr(pipeline, "far_of", gone)
    with pytest.raises(KrsError):
        pipeline.antenna_lines(pj, d, res)
    lines, far, _ = pipeline.antenna_lines(pj, d, res, errors_as_lines=True)
    assert lines[-1] == ("E_RESULTS_WAVES", {"path": "P"}) and far is None
    assert "I_ANTENNA_FAR_FIELD" not in [c for c, _ in lines]


def test_the_what_ifs_far_field_reads_in_its_try(tmp_path, calibrated, monkeypatch):  # plan 3's deferred minor
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.verify(pj) == 0
    monkeypatch.setattr(pipeline, "far_of", gone)
    lines = pipeline.antenna_outputs(pj, load_project(pj), "x", errors_as_lines=True)
    codes = [c for c, _ in lines]
    assert ("E_RESULTS_WAVES", {"path": "P"}) in lines and "I_ANTENNA_ETA_WHAT_IF" not in codes
    assert codes[-6:] == ["I_OUTPUTS", *ANTENNA_LIMITS]  # the files and the limits still come


def test_s11_at_takes_the_layout_it_is_given_and_current_verify_needs_results(tmp_path, calibrated, monkeypatch):
    pj = pi_run(tmp_path, monkeypatch)
    d = load_project(pj)
    f = np.array([2.45e9, 2.4e9])  # not ascending: the answer comes back in f's order
    s11, p = pipeline.s11_at(pj, d, f)
    lay = layout(d, d["results"], np.sort(f))
    monkeypatch.setattr(pipeline, "layout", fail)
    again = pipeline.s11_at(pj, d, f, lay)
    assert np.array_equal(again[0], s11) and np.array_equal(again[1], p)
    assert pipeline.current_verify({"verify": {"base_hash": "M", "values": {}}}) is None  # never a KeyError
