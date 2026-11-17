# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import pytest

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.emission import EMISSION_COLUMNS
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_emission import LPF, emission_project
from test_project import VIA
from test_run_antenna import events


def test_the_emission_fingerprint_leaves_out_the_lid_the_overrides_and_the_board(tmp_path, monkeypatch):  # 5.10
    monkeypatch.setattr(runs, "openems_versions", lambda: ("0.37.0", "0.7.0"))
    base = load_project(emission_project(tmp_path / "a"))
    fp = pipeline.fingerprint(base)
    assert fp["ends"] == [["TP1.1", 50.0], ["TP2.1", 50.0]] and {"lid", "overrides", "board", "results"}.isdisjoint(fp)
    for same in ({"lid": False}, {"overrides": [VIA]}, {"board": {"path": "b.kicad_pcb", "sha256": "0" * 64}}):
        assert pipeline.fingerprint({**base, **same}) == fp
    for other in ({"lid_height_mm": 2.0}, {"near_field": True}, {"t_max_s": 40e-9}, {"preset": "strict"},
                  {"ports": [base["ports"][0], {**base["ports"][1], "R": 75.0}]}):
        assert pipeline.fingerprint({**base, **other}) != fp


def test_an_emission_run_is_three_jobs_in_one_folder_and_writes_its_csvs(tmp_path, calibrated):  # 5.6, 5.8
    pj = emission_project(tmp_path / "e")
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    r, run_dir = d["results"], Path(d["results"]["run_dir"])
    project, board, geom, _ = pipeline.load(pj)
    spec = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    driven = json.loads((run_dir / "driven.json").read_text(encoding="utf-8"))
    assert r["model_hash"] == spec_hash(spec) == spec_hash(pipeline.build_model(project, board, geom).spec)
    assert "nf2ff" not in spec and driven["nf2ff"]["f_hz"] == d["far_field"]["f_hz"] and driven["excitation"]["emission"]
    spec_of = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))["spec"] for p in run_dir.glob("job-*/job.json")}
    assert (spec_of.pop("job-0-setup"), spec_of.pop("job-1-P1")) == ("../model.json", "../driven.json")
    assert list(spec_of.values()) == ["../driven.json"]  # the transform reads the driven job's spec
    assert [j["port"] for j in r["jobs"]] == ["P1"] and isinstance(r["jobs"][0]["rings"], list)
    assert set(r["far_field"]) == {"sphere", "elevation", "azimuth"} and r["loss_expected"] is None
    assert r["fingerprint"] == pipeline.fingerprint(d)
    results = pj.parent / "results"
    assert sorted(f.name for f in results.iterdir()) == ["emission.csv", "emission_rings.csv"]
    header = (results / "emission.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:9] == list(EMISSION_COLUMNS) and "p_term_P2_w" in header
    ev = [json.loads(x) for x in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    start = next(e for e in ev if e["code"] == "I_RUN_START")
    assert (start["params"]["runs"], start["params"]["pool"]) == (1, 1)
    codes = events(run_dir)
    assert "I_GATES_PASSED_PML" in codes and codes.index("I_EMISSION_RELATIVE") < codes.index("I_OUTPUTS")
    assert codes[-1] == "I_LIMIT_EMISSION"


def test_a_failed_transform_keeps_the_job_and_says_so(tmp_path, calibrated, monkeypatch):  # as Stage 3 5.5
    def fail(*_, **__):
        raise KrsError("E_WORKER_FAILED", job="T_JOB_FAR_FIELD", exit_code=1, log="log.txt")

    monkeypatch.setattr(pipeline, "far_field", fail)
    pj = emission_project(tmp_path / "e")
    assert pipeline.run(pj) == 2
    r = load_project(pj)["results"]
    assert r["far_field"] is None and {"E_WORKER_FAILED", "I_EMISSION_NO_FAR_FIELD"} <= set(events(r["run_dir"]))


def test_a_refused_write_advises_run_since_retune_refuses_the_kind(tmp_path, calibrated):  # AR-12; Stage 1 7.5
    pj = emission_project(tmp_path / "e")
    (pj.parent / "results").write_bytes(b"")  # a file where results/ goes: the write is refused
    assert pipeline.run(pj) == 2
    run_dir = Path(load_project(pj)["results"]["run_dir"])
    ev = [json.loads(x) for x in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    refused = next(e for e in ev if e["code"] == "E_RESULTS_WRITE")
    assert refused["params"]["command"] == pipeline.command_line("kicad-rf-studio", "run", str(pj))


def test_a_part_the_grid_cannot_hold_is_refused_before_any_job(tmp_path, calibrated):  # AR-12
    pj = emission_project(tmp_path / "e", LPF, "U1.1", "J1.1", lid_height=2.5)
    d = load_project(pj)
    next(q for q in d["chain"]["shunt"] if q["ref"] == "C2")["value"] = "C_Small"
    save_project(pj, d)
    run_dir = tmp_path / "r"
    assert pipeline.run(pj, run_dir) == 2
    assert "E_EMISSION_PART" in events(run_dir) and not (run_dir / "job-0-setup").exists()
    ev = [json.loads(x) for x in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert next(e["params"] for e in ev if e["code"] == "E_EMISSION_PART") == {"ref": "C2", "value": "C_Small"}


def test_a_curve_port_or_an_unread_value_is_refused_but_a_bypass_is_not():  # AR-12; Task 4's ruling
    def refused(**q):
        part = {"ref": "C1", "role": "port", "value": "100n", **q}
        try:
            pipeline.emission_parts({"chain": {"series": [part], "shunt": []}, "others": []})
        except KrsError as err:
            return err.code, err.params
        return None

    assert [refused(value=v) for v in ("100n", "0R", "open")] == [None] * 3  # 0R copper, open left out
    assert refused(value="0") == ("E_EMISSION_PART", {"ref": "C1", "value": "0"})  # a C of 0 is no value
    assert refused(role="curve_port") == ("E_EMISSION_PART", {"ref": "C1", "value": "100n"})
    assert refused(role="copper", value="C_Small") is None  # not a port: the grid never holds it


def test_retune_and_verify_refuse_an_emission_project_and_compare_stays_two_kinds(tmp_path):  # 5.6; plan 4
    pj = emission_project(tmp_path / "e")
    for command, call in (("retune", lambda: pipeline.retune(pj, [])), ("verify", lambda: pipeline.verify(pj))):
        with pytest.raises(KrsError) as e:
            call()
        assert e.value.code == "E_EMISSION_ONE_RUN" and e.value.params == {"path": str(pj), "command": command}
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(pj, pj)
    assert e.value.code == "E_COMPARE_KIND"
