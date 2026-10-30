# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np
import pytest

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.geometry.region import air_cell
from kicad_rf_studio.core.mesh.gates import edge_lint
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.csx import PML_CELLS
from kicad_rf_studio.core.model.spec import far_field_box, metal_in_pml, verify_spec
from kicad_rf_studio.core.project import load_project, parts, save_project
from kicad_rf_studio.stoprule import flat_window
from test_antenna_geometry import model_of
from test_cli_antenna import FIX, antenna_project


def test_an_antennas_model_sits_in_an_air_box_under_pml_8(tmp_path):  # design 5.2, 5.3
    model, geom, _ = model_of(antenna_project(tmp_path))
    s, w = model.spec, geom.region.walls
    assert s["boundary"] == "pml_8" and metal_in_pml(s) == [] and edge_lint(model.mesh) == []  # the board's lines kept
    for k, a in enumerate("xyz"):
        v = np.array(s["mesh"][a])
        steps = np.diff(v)
        assert np.allclose(steps[:PML_CELLS], steps[0]) and np.allclose(steps[-PML_CELLS:], steps[-1])
        assert v[PML_CELLS] == pytest.approx(w[2 * k] - 31.228381, abs=2e-6)  # the gap past the walls
        assert v[-1 - PML_CELLS] == pytest.approx(w[2 * k + 1] + 31.228381, abs=2e-6)
        assert steps.max() <= air_cell(2.99e9) + 1e-6
    assert [len(s["mesh"][a]) for a in "xyz"] == [135, 137, 71]  # the prototype's


def test_the_far_field_box_join_and_flat_window_are_the_antennas(tmp_path):  # design 5.3-5.5
    model, geom, _ = model_of(pj := antenna_project(tmp_path))
    s, zs = model.spec, geom.zs
    assert s["nf2ff"] == {"f_hz": load_project(pj)["far_field"]["f_hz"],
                          "center": [107.0, -109.0, round((zs[0].z0 + zs[-1].z1) / 2, 6)]}  # the board's centre
    cu = [z for z in zs if z.kind == "copper"]
    assert s["join"] == [[[101.35, -100.55, cu[0].z0], [102.85, -99.45, cu[-1].z1]]]  # AE1.2 grown by d = 0.3
    exc = s["excitation"]
    assert (exc["f1"], exc["f2"], exc["t_max"]) == (1.84e9, 2.99e9, 30e-9)
    assert exc["flat_s"] == flat_window(2.44175e9) == pytest.approx(8.19085e-9, rel=1e-5)


def test_part_ports_record_no_far_field_and_mur_adds_no_pml(tmp_path):  # design 5.5, 5.2
    model, _, _ = model_of(antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb"))
    assert "nf2ff" not in model.spec and model.spec["boundary"] == "pml_8"  # 1 + 3 jobs: a part-port run
    pj = antenna_project(tmp_path / "mur")
    save_project(pj, {**load_project(pj), "boundary": "mur"})
    model, _, _ = model_of(pj)
    # provisional: MUR is the untested fallback (W_AIR_BOX), which plan 4's P3-C tests and may re-pin
    assert "boundary" not in model.spec and [len(model.spec["mesh"][a]) for a in "xyz"] == [119, 121, 55]


def test_verify_puts_an_antennas_network_in_the_grid_and_records_its_far_field(tmp_path, monkeypatch):  # 5.5, 5.7
    project, board, geom, _ = pipeline.load(antenna_project(tmp_path, FIX / "ifa2g4_pi.kicad_pcb"))
    spec = pipeline.build_model(project, board, geom).spec
    box = far_field_box(project, board, geom)
    assert box == {"f_hz": project["far_field"]["f_hz"], "center": [107.0, -109.0, 0.39]}  # the board's centre
    m0, b0, g0, _ = pipeline.load(antenna_project(tmp_path / "m0"))
    assert far_field_box(m0, b0, g0) == pipeline.build_model(m0, b0, g0).spec["nf2ff"]  # model_spec's, factored out
    by_ref = parts(project)
    by_ref["L1"]["value"], by_ref["C2"]["value"] = "0R", "open"  # the series part shorted, a shunt removed
    dump = tmp_path / "operator_dump.vtr"
    dump.write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    out = verify_spec(spec, by_ref, dump, 1e-13, far_field=box)
    assert [q["name"] for q in out["ports"]] == ["P1"] and [g["name"] for g in out["grid"]] == ["C3"]
    assert (out["nf2ff"], out["boundary"], out["join"]) == (box, "pml_8", spec["join"])
    l1 = next(q for q in spec["ports"] if q["name"] == "L1")
    lo, hi = ([f(a, b) for a, b in zip(l1["start"], l1["stop"])] for f in (min, max))
    assert out["metal"]["copper"][len(spec["metal"]["copper"])] == {  # L1 at 0 Ω: copper over its whole box
        "x": [lo[0], hi[0], hi[0], lo[0]], "y": [lo[1], lo[1], hi[1], hi[1]], "z": [lo[2], hi[2]]}
    with pytest.raises(KrsError) as e:  # a bypass is an antenna's: without the far-field box, v1's refusal
        verify_spec(spec, by_ref, dump, 1e-13)
    assert (e.value.code, e.value.params) == ("E_VERIFY_VALUE", {"ref": "L1", "value": "0R"})
    by_ref["C2"]["s2p"] = {"file": "c2.s2p", "connection": "shunt"}  # a placeholder given an S2P file is fitted
    with pytest.raises(KrsError) as e:  # and has no value verify can place, as v1 refuses one
        verify_spec(spec, by_ref, dump, 1e-13, far_field=box)
    assert (e.value.code, e.value.params) == ("E_VERIFY_VALUE", {"ref": "C2", "value": "open"})
    by_ref["C2"]["s2p"], by_ref["C3"]["value"] = None, "open"
    dump.unlink()  # nothing left in the grid, so no cell C to read
    assert verify_spec(spec, by_ref, dump, 1e-13, far_field=box)["grid"] == []


def codes(run_dir):
    return [json.loads(line)["code"] for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_an_antenna_runs_its_gates_with_the_absorber_and_leaves_the_calibration(tmp_path, calibrated):  # P3-A
    project, board, geom, _ = pipeline.load(antenna_project(tmp_path / "p"))
    model = pipeline.build_model(project, board, geom)
    before = runs.load_settings()
    done, _, _ = pipeline.simulate(model, project, tmp_path / "run")
    seen = codes(tmp_path / "run")
    assert "I_GATES_PASSED_PML" in seen and "I_GATES_PASSED" not in seen and "I_COST_SPLIT" in seen
    assert [j["verdict"] for j in done] == ["converged"] and runs.load_settings() == before


def test_cost_and_preview_take_an_antenna_project(tmp_path, calibrated, monkeypatch):  # design 5.1
    pj = antenna_project(tmp_path / "p")
    assert pipeline.cost(pj, tmp_path / "cost") == 0 and "I_COST_SPLIT" in codes(tmp_path / "cost")
    opened = []
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append(job))
    assert pipeline.preview(pj) == 0
    assert "boundary" in json.loads((opened[0].parent / "model.json").read_text(encoding="utf-8"))
