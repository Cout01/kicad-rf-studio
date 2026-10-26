# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_cost import fail, half_its_error, new_project


def test_preview_writes_the_xml_in_a_job_folder_and_opens_it(tmp_path, capsys, fake, monkeypatch):  # C-34
    opened = []
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append((exe, job)))
    assert main(["preview", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    (exe, job), = opened
    assert job.name == "job-0-xml" and (job / "model.xml").is_file()
    assert capsys.readouterr().out.splitlines()[-1] == render("I_PREVIEW", path=str(job / "model.xml"))


def test_the_viewer_opens_a_relative_file_from_the_job_folder(tmp_path, monkeypatch):  # Review Focus 2
    seen = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: seen.append((cmd, kw["cwd"])))
    pipeline.open_viewer("AppCSXCAD", tmp_path)
    assert seen == [(["AppCSXCAD", "model.xml"], tmp_path)]


def test_a_missing_appcsxcad_names_the_file_and_the_install(tmp_path, fake, monkeypatch):  # final review M4
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: None)
    with pytest.raises(KrsError) as e:  # setup-openems is for Windows only: the install command of this OS
        pipeline.preview(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))
    xml = str(next(fake.glob("runs/*/job-0-xml")) / "model.xml")
    assert (e.value.code, e.value.params) == ("E_APPCSXCAD_MISSING", {"path": xml, "command": runs.install_command()})


@pytest.mark.openems
def test_preview_writes_a_real_model_xml(tmp_path, monkeypatch):  # tier b: the XML write, no GUI
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    opened = []
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append(job))
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    assert main(["preview", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    root = ET.parse(opened[0] / "model.xml").getroot()
    assert root.tag == "openEMS" and root.find("FDTD/BoundaryCond").get("xmin") == "MUR"
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


# --- beyond the brief's tests: the real lookup, which they patch, and the branches they leave open ---------------


def test_appcsxcad_is_found_in_the_recorded_openems_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("CSXCAD_INSTALL_PATH", raising=False)
    assert pipeline.appcsxcad({}) is None
    exe = tmp_path / ("AppCSXCAD.exe" if sys.platform == "win32" else "AppCSXCAD")
    exe.write_text("")
    exe.chmod(0o755)
    assert Path(pipeline.appcsxcad({"openems_dir": str(tmp_path)})) == exe


def test_a_refusal_stops_preview_before_any_worker(tmp_path, capsys, fake, monkeypatch):
    pj = new_project(tmp_path, "lpf915")  # a shield and no lid_height_mm: E_LID_HEIGHT
    monkeypatch.setattr(subprocess, "Popen", fail)
    assert main(["preview", str(pj)]) == 2
    assert capsys.readouterr().out.splitlines()[-1] == render("E_LID_HEIGHT", refs="SH1")


def test_a_blocked_gate_is_printed_and_the_model_still_opens(tmp_path, capsys, fake, monkeypatch):
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: None)
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    save_project(pj, {**load_project(pj), "gates": {"fit2d_limit": half_its_error(pj), "dt_floor": 0.8}})
    assert main(["preview", str(pj)]) == 0
    out = capsys.readouterr().out
    assert "misses the 2D reference on net LINE" in out and out.splitlines()[-1].startswith("Opened ")
