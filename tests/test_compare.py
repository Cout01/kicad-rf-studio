# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import os
import shutil
from pathlib import Path

import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS, DELTA_COLUMNS
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import antenna_project
from test_match_antenna import pi_run
from test_run import lpf_project


def twin(pj, folder):
    """A copy of the project folder of `pj` at `folder`: the same results and run folder, its own project.json."""
    shutil.copytree(pj.parent, folder)
    return folder / "project.json"


def compared(base, variant, out):
    lines = []
    assert pipeline.compare_projects(base, variant, out, lambda code, params: lines.append((code, params))) == 0
    return lines


def edited(pj, **results):
    d = load_project(pj)
    save_project(pj, {**d, "results": {**d["results"], **results}})


def test_compare_two_runs_with_the_same_settings(tmp_path, calibrated, capsys):  # design 5.8
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b, run_dir = twin(a, tmp_path / "b"), load_project(a)["results"]["run_dir"]
    lines = compared(a, b, tmp_path / "out")
    codes = [code for code, _ in lines]
    assert lines[:3] == [("I_ANTENNA_RELATIVE", {}),
                         ("I_COMPARE_BASIS", {"role": "T_BASE", "path": str(a), "source": "T_RUN", "run_dir": run_dir}),
                         ("I_COMPARE_BASIS", {"role": "T_VARIANT", "path": str(b), "source": "T_RUN",
                                              "run_dir": run_dir})]
    assert lines[3] == ("I_COMPARE_RESONANCE", {**lines[3][1], "shift_mhz": "+0.0", "verdict": "T_NOT_RESOLVED"})
    assert codes.count("I_COMPARE_ETA") == 3 and "I_COMPARE_GAIN" in codes
    assert {p["verdict"] for _, p in lines if "verdict" in p} == {"T_NOT_RESOLVED"}  # a project against its copy
    assert codes[-6:] == ["I_OUTPUTS", *ANTENNA_LIMITS]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["compare.csv", "compare.png"]
    rows = list(csv.reader(io.StringIO((tmp_path / "out" / "compare.csv").read_text(encoding="utf-8"))))
    assert rows[0] == list(DELTA_COLUMNS) and len(rows) == 7
    capsys.readouterr()
    assert main(["compare", str(a), str(b), "-o", str(tmp_path / "cli")]) == 0
    assert render("I_ANTENNA_RELATIVE") in capsys.readouterr().out.splitlines()


def test_compare_refuses_other_settings_another_kind_and_no_result(tmp_path, calibrated, capsys):  # 5.8; RF 4, 5
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b, old, stale = twin(a, tmp_path / "b"), twin(a, tmp_path / "old"), twin(a, tmp_path / "stale")
    edited(b, fingerprint={**load_project(b)["results"]["fingerprint"], "preset": "strict", "air_gap_mm": 62.5,
                           "openems": "0.36.0"})
    d = load_project(old)
    del d["results"]["fingerprint"]  # a result made before this version
    save_project(old, d)
    save_project(stale, {**load_project(stale), "t_max_s": 31e-9})  # T_max is in the model: its results are stale
    lpf, fresh = lpf_project(tmp_path), antenna_project(tmp_path / "fresh")
    for variant, code, params in [(b, "E_COMPARE_SETTINGS", {"fields": "air_gap_mm, openems, preset"}),
                                  (lpf, "E_COMPARE_KIND", {"path": str(lpf)}),
                                  (fresh, "E_COMPARE_NO_RESULT", {"path": str(fresh)}),
                                  (old, "E_COMPARE_NO_RESULT", {"path": str(old)}),
                                  (stale, "E_COMPARE_NO_RESULT", {"path": str(stale)})]:
        with pytest.raises(KrsError) as e:
            pipeline.compare_projects(a, variant, tmp_path / "out")
        assert (e.value.code, e.value.params) == (code, params)
    assert not (tmp_path / "out").exists()  # a refusal writes nothing
    capsys.readouterr()
    assert main(["compare", str(a), str(b), "-o", str(tmp_path / "cli")]) == 2
    assert capsys.readouterr().err == render("E_COMPARE_SETTINGS", fields="air_gap_mm, openems, preset") + "\n"


def test_compare_reads_a_part_port_projects_verify_at_its_values(tmp_path, calibrated, monkeypatch):  # 5.8; RF 4
    a = pi_run(tmp_path, monkeypatch)
    with pytest.raises(KrsError) as e:  # part ports and no verify: the retune alone is what-if
        pipeline.compare_projects(a, a, tmp_path / "out")
    assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(a)})
    assert pipeline.verify(a) == 0
    b, other, verify_dir = twin(a, tmp_path / "b"), twin(a, tmp_path / "other"), load_project(a)["verify"]["run_dir"]
    lines = compared(a, b, tmp_path / "out")
    assert [(p["source"], p["run_dir"]) for c, p in lines if c == "I_COMPARE_BASIS"] == [("T_VERIFY", verify_dir)] * 2
    assert pipeline.retune(b, ["C3=1.2pF"]) == 0  # applied after its verify, which no longer holds b's values
    d = load_project(other)
    save_project(other, {**d, "verify": {**d["verify"], "base_hash": "0" * 64}})  # a verify of another run
    for project in (b, other):
        with pytest.raises(KrsError) as e:
            pipeline.compare_projects(a, project, tmp_path / "out")
        assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(project)})
    shutil.rmtree(verify_dir)  # verify's folder deleted: the base, read first, has nothing to compare either
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(a, b, tmp_path / "out")
    assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(a)})


def test_compare_refuses_a_run_whose_folder_is_gone(tmp_path, calibrated):  # final review; the ruling
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b = twin(a, tmp_path / "b")
    shutil.rmtree(load_project(a)["results"]["run_dir"])  # both projects' run folder
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(a, b, tmp_path / "out")
    assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(a)})
    assert not (tmp_path / "out").exists()


def test_compare_without_a_far_field_on_one_side_compares_s11_alone(tmp_path, calibrated):  # design 5.8; RF 5
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b = twin(a, tmp_path / "b")
    edited(b, far_field=None)  # its transform failed
    codes = [code for code, _ in compared(a, b, tmp_path / "out")]
    assert "I_COMPARE_NO_FAR_FIELD" in codes and not {"I_COMPARE_ETA", "I_COMPARE_GAIN"} & set(codes)


def test_compare_writes_to_the_working_folder_by_default_and_a_held_file_is_an_e_line(
        tmp_path, calibrated, monkeypatch):  # r2 Q4; Stage 1 7.5
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b = twin(a, tmp_path / "b")
    (tmp_path / "cwd").mkdir()
    monkeypatch.chdir(tmp_path / "cwd")
    assert main(["compare", str(a), str(b)]) == 0
    assert sorted(p.name for p in (tmp_path / "cwd").iterdir()) == ["compare.csv", "compare.png"]
    real = os.replace

    def replace(src, dst):  # a viewer holds compare.png
        if Path(dst).name == "compare.png":
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    lines = []
    assert pipeline.compare_projects(a, b, tmp_path / "out", lambda code, params: lines.append((code, params))) == 2
    (err,) = [params for code, params in lines if code == "E_RESULTS_WRITE"]
    assert (err["path"], err["command"]) == (str(tmp_path / "out" / "compare.png"), pipeline.command_line(
        "kicad-rf-studio", "compare", str(a), str(b), "-o", str(tmp_path / "out")))
    codes = [code for code, _ in lines]
    assert "I_OUTPUTS" not in codes and codes[-5:] == list(ANTENNA_LIMITS)  # the lines still printed
