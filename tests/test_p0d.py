# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import re
import shutil
from pathlib import Path

import numpy as np
import pytest

import p0
import p0a
import p0c
import p0d
from kicad_rf_studio import runs
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.pipeline import records
from networks import star
from p0b import emerge_app, harness
from test_p0 import TWO, in_process

F, _ = grid(915e6, 3, 1.1)
C0 = 299792458.0


def test_judge_applies_criterion_1_against_the_windows_reference():  # D-47, D-48
    ref = {"f": F, "S": star(F, 6), "t_cut": np.full(6, 4e-9), "spec_hash": np.array("abc")}
    same = p0d.judge(ref, star(F, 6), "abc")
    assert same["criterion1"]["pass"] and same["spec_hash_equal"]
    bent = star(F, 6).copy()
    bent[100, 2, 3] += 0.05
    assert p0d.judge(ref, bent, "abd")["criterion1"]["ds_max"] is False


def test_models_writes_each_spec_and_the_matrix(tmp_path, monkeypatch):  # D-47; PF-49, PF-50
    monkeypatch.setattr("kicad_rf_studio.core.project.REACH_H", 6.0)  # a later default (D-37) must not move the models
    assert p0d.models(tmp_path, ["coupon_ms", "coupon_gcpw_pads"]) == [
        {"model": "coupon_ms", "port": 1}, {"model": "coupon_gcpw_pads", "port": 1}, {"model": "coupon_gcpw_pads", "port": 2}]
    assert len((tmp_path / "matrix.json").read_text(encoding="utf-8").splitlines()) == 1  # the models job's output
    coupon = json.loads((tmp_path / "coupon_ms.json").read_text(encoding="utf-8"))
    assert coupon["probes"]
    assert load_project(tmp_path / "coupon_gcpw_pads" / "project.json")["mesh"]["reach_h"] == 3.0  # PIN
    monkeypatch.undo()
    assert spec_hash(coupon) == spec_hash(p0a.coupon_model("coupon_ms", 2)[0].spec)  # PIN, on the coupons too


def test_excite_runs_one_port_at_draft_and_compare_judges_it(p0_out, tmp_path):  # D-47: one job per excitation
    spec = tmp_path / "two.json"
    spec.write_text(json.dumps(TWO), encoding="utf-8")
    run = p0d.excite(spec, 1, p0_out)
    assert [j["port"] for j in run["jobs"]] == ["P1"] and (p0_out / "result.json").is_file()
    job = p0.run_path(run["run_dir"]) / run["jobs"][0]["job"]
    s, cuts = p0.s_of([(records(job, 2, run["setup"]["dt"]), 0, TWO["excitation"], None)], F, "draft")
    refs, runs_dir = tmp_path / "refs", tmp_path / "runs"
    refs.mkdir()
    np.savez(refs / "two.npz", f=F, S=s, t_cut=cuts, spec_hash=np.array(spec_hash(TWO)))
    shutil.copytree(p0_out, runs_dir / "two-k1")
    shutil.rmtree(p0_out / "data")  # PF-47: compare reads the copy, never the data folder of the run
    assert p0d.compare_runs(runs_dir, refs, tmp_path)["pass"]
    np.savez(refs / "two.npz", f=F, S=s + 0.05, t_cut=cuts, spec_hash=np.array(spec_hash(TWO)))
    assert not p0d.compare_runs(runs_dir, refs, tmp_path)["pass"]
    report = tmp_path / "report" / "compare.json"
    argv = ["compare", "--runs", str(runs_dir), "--refs", str(refs), "--models", str(tmp_path), "--out", str(report)]
    assert p0d.main(argv) == 1  # the workflow's compare step fails
    assert json.loads(report.read_text(encoding="utf-8"))["models"]["two"]["pass"] is False
    shutil.rmtree(runs_dir / "two-k1")  # a failed excitation uploads nothing
    assert p0d.compare_runs(runs_dir, refs, tmp_path)["models"] == {"two": {"missing": ["two-k1"], "pass": False}}


def pulse(job: Path, probes: list[dict], z0: float) -> None:
    """coupon_ms's probe files in the job folder `job`, which the fake worker never writes: a forward pulse along x on a
    line of `z0` Ω and εeff 2.7, as test_p0a writes them."""
    t, v = np.arange(0, 6e-9, 1e-11), C0 / math.sqrt(2.7)
    for q in probes:
        tt, x = t + (5e-12 if q["type"] else 0.0), (q["start"][0] - probes[0]["start"][0]) * 1e-3
        value = np.exp(-((tt - x / v - 1e-9) / 0.15e-9) ** 2) / (z0 if q["type"] else 1.0)
        (job / q["name"]).write_text("% t/s\tvalue\n" + "".join(
            f"{a!r}\t{b!r}\n" for a, b in zip(tt.tolist(), value.tolist())), encoding="utf-8")


def test_a_coupons_reference_holds_its_line_constants_and_compare_limits_them(p0_out, tmp_path,
                                                                              monkeypatch):  # spec L541; PF-46
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-coupon_ms-n2"]) == 0
    res = p0.records(p0_out, ["p0a-coupon_ms-n2"])[0]["result"]
    spec = json.loads((p0.run_path(res["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    pulse(p0.run_path(res["run_dir"]) / res["jobs"][0]["job"], spec["probes"], 50.0)
    (ref,) = p0d.references(p0_out, tmp_path / "refs", models=("coupon_ms",))
    with np.load(ref) as z:
        assert set(z.files) == {"f", "S", "t_cut", "spec_hash", "z0", "eeff"} and z["S"].shape == (len(F), 2, 1)
        assert z["z0"].shape == z["eeff"].shape == (1, len(F)) and z["z0"][0, 71] == pytest.approx(50.0, rel=1e-6)
    copy = tmp_path / "runs" / "coupon_ms-k1"  # the Linux side: the same records, read where CI puts them
    shutil.copytree(p0_out / "data", copy / "data")
    p0.save(copy / "result.json", res)
    (tmp_path / "coupon_ms.json").write_text(json.dumps(spec), encoding="utf-8")
    same = p0d.compare_runs(tmp_path / "runs", tmp_path / "refs", tmp_path)["models"]["coupon_ms"]
    assert same["pass"] and same["spec_hash_equal"] and same["dz0_pct"] <= 1e-9
    pulse(copy / "data" / "kicad-rf-studio" / "runs" / res["run_dir"] / res["jobs"][0]["job"], spec["probes"], 50.4)
    off = p0d.compare_runs(tmp_path / "runs", tmp_path / "refs", tmp_path)["models"]["coupon_ms"]
    assert off["dz0_pct"] == pytest.approx(0.8, rel=1e-6) and off["criterion1"]["pass"] and not off["pass"]


def test_references_and_traces_come_from_a_p0_folder(p0_out, tmp_path, monkeypatch):  # D-40, D-48; PF-43
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-pad"]) == 0
    monkeypatch.setattr(p0, "code_id", lambda: "other")  # P0-B ran on other product code than P0-A
    assert harness.main(["--out", str(p0_out), "--only", "B1"]) == 0
    refs = p0d.references(p0_out, tmp_path / "refs", models=("coupon_gcpw_pads", "lpf915"))
    assert [p.name for p in refs] == ["coupon_gcpw_pads.npz", "lpf915.npz"]
    with np.load(refs[1]) as z:
        assert set(z.files) == {"f", "S", "t_cut", "spec_hash"} and z["S"].shape == (len(F), 6, 6)
    traces = p0d.traces(p0_out, tmp_path / "traces")
    assert sorted(p.name for p in traces)[:3] == ["coupon_gcpw_pads-k1.npz", "coupon_gcpw_pads-k2.npz", "lpf915-k1.npz"]
    assert p0.load_trace(traces[0])[1] in (0, 1)
    path = p0_out / "steps" / "p0b-B1.json"  # D-40: the fixtures are the live converged branch
    record = json.loads(path.read_text(encoding="utf-8"))
    record["result"]["jobs"][3]["verdict"] = "t_max"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        p0d.traces(p0_out, tmp_path / "refused")
    assert "lpf915-k4" in str(e.value) and not (tmp_path / "refused").exists()


@pytest.mark.parametrize(("run", "argv", "folder"), [
    ("p0a", ["--out", "{p0}"], "p0"), ("harness", ["--out", "{p0}"], "p0"), ("emerge_app", ["run", "--out", "{p0}"], "p0"),
    ("p0c", ["--board", "{board}", "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "--out", "{p0}"], "p0"),
    ("p0d", ["references", "--p0", "{p0}", "--out", "{out}"], "p0"), ("p0d", ["traces", "--p0", "{p0}", "--out", "{out}"], "p0"),
    ("p0d", ["excite", "--spec", "{board}", "--port", "1", "--out", "{out}"], "out")])
def test_every_tool_enters_its_p0_folder_first(tmp_path, monkeypatch, run, argv, folder):  # D-7, D-46
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    seen = []

    def enter(out):
        seen.append(Path(out))
        raise RuntimeError("entered")

    monkeypatch.setattr(p0, "enter", enter)
    monkeypatch.setattr(runs, "data_dir", lambda: pytest.fail("runs used before p0.enter"))
    paths = {"p0": tmp_path / "p0", "out": tmp_path / "out", "board": board}
    main = {"p0a": p0a.main, "harness": harness.main, "emerge_app": emerge_app.main, "p0c": p0c.main,
            "p0d": p0d.main}[run]
    with pytest.raises(RuntimeError):
        main([a.format(**paths) for a in argv])
    assert seen == [paths[folder]]


def test_the_linux_workflow_is_prepared():  # D-47
    text = (p0.ROOT / ".github" / "workflows" / "linux-openems.yml").read_text(encoding="utf-8")
    assert text.splitlines()[0] == "# SPDX-License-Identifier: GPL-3.0-or-later"
    assert "\npermissions:\n  contents: read\n" in text
    for needle in ("schedule:", "workflow_dispatch:", "debian:12", "ubuntu:24.04", "fedora:44", "--branch v0.37.0",
                   "install_deps.sh --auto --python", "update_openEMS.sh /opt/openEMS --python", "startswith('0.37.')",
                   "import openEMS, CSXCAD", "fail-on-cache-miss: true", "if: always()", 'pip install -e ".[dev]"',
                   "tools/p0d.py excite", "tools/p0d.py compare", "pytest -m openems"):
        assert needle in text, needle
    assert "needs: build" in text.split("openems-tests:")[1]
    assert max(int(m) for m in re.findall(r"timeout-minutes: (\d+)", text)) <= 350
