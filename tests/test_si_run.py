# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import numpy as np
import pytest
import skrf

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.si import uniform_grid
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.stoprule import KEPT
from networks import star
from test_cli_si import QSPI, si_project
from test_run import result_codes


def test_an_si_run_writes_its_layout_on_the_grid_from_dc(tmp_path, calibrated, monkeypatch):  # design 5.12 item 2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    results = p["results"]
    assert [j["port"] for j in results["jobs"]] == ["P1", "P2", "P3", "P4", "P5", "P6", "R1", "R2"]  # Stage 1 7.1
    assert {j["verdict"] for j in results["jobs"]} <= KEPT and results["loss_expected"] is None  # no loss budget (5.6)
    out = pj.parent / "results"
    assert sorted(f.name for f in out.iterdir()) == ["layout.s8p"]
    n = skrf.Network(str(out / "layout.s8p"))
    assert (n.f[0], n.f[-1], len(n.f)) == (0.0, 10e9, 2001) and np.abs(n.s - star(n.f, 8)).max() <= 1e-5
    assert "port 1 P1: external, signal J1.3, reference plane In1.Cu, as built" in (out / "layout.s8p").read_text()
    assert result_codes(results["run_dir"]) == ["I_RESULTS", "I_BASIS", "I_OUTPUTS"]  # the SI results are plan 3's
    codes = {e["code"] for e in map(json.loads,
                                    (Path(results["run_dir"]) / "events.jsonl").read_text("utf-8").splitlines())}
    assert not {"W_GATE_LIMITS", "W_GATE_LIMITS_SI"} & codes  # every verdict judged against GATES_SI
    lay = layout(p, results)
    assert lay.f.tolist() == uniform_grid(10e9).tolist() and lay.markers == [48]  # 240 MHz on the 5 MHz grid
    assert pipeline.retune(pj, []) == 0 and sorted(f.name for f in out.iterdir()) == ["layout.s8p"]
    with pytest.raises(KrsError) as e:  # a part value would be stored and change nothing until plan 3
        pipeline.retune(pj, ["R1=33"])
    assert (e.value.code, e.value.params) == ("E_RETUNE_SI", {}) and load_project(pj) == p


def test_a_marker_off_the_grid_takes_its_nearest_point(tmp_path, calibrated, monkeypatch):  # se50's 133 MHz
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    assert layout(p, p["results"]).markers == [27]  # 135 MHz: round(133/5)


def test_verify_waits_for_the_si_results_and_preview_takes_an_si_project(tmp_path, calibrated, monkeypatch):
    pj = si_project(tmp_path / "p")
    with pytest.raises(KrsError) as e:
        pipeline.verify(pj)
    assert (e.value.code, e.value.params) == ("E_VERIFY_SI", {})
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(pj, pj)
    assert e.value.code == "E_COMPARE_KIND"  # compare comes with the SI results (plan 3)
    opened = []
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append(job))
    assert pipeline.preview(pj) == 0
    assert json.loads((Path(opened[0]).parent / "model.json").read_text(encoding="utf-8"))["excitation"]["f1"] == 0.0
