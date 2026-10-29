# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import shutil
import subprocess
import sys
import types
import xml.etree.ElementTree

import numpy as np
import pytest

from kicad_rf_studio import pipeline, worker
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.readers import pec_roots
from test_model_csx import TINY, fake_openems
from test_readers import DUMPS, LINES, PROBE, SETUP_LOG


def write_job(tmp_path, spec, mode, parent="run"):
    run = tmp_path / parent
    job = run / "job-1-P1"
    job.mkdir(parents=True)
    (run / "model.json").write_text(json.dumps(spec), encoding="utf-8")
    (job / "job.json").write_text(json.dumps({"spec": "../model.json", "port": 1, "mode": mode, "threads": 1,
                                              "t_max": spec["excitation"]["t_max"]}), encoding="utf-8")
    return job


SMOKE = {**TINY, "mesh": {a: LINES[k].tolist() for k, a in enumerate("xyz")}, "ports": [  # tests/test_readers.py
    {"name": f"P{k}", "kind": "lumped", "dir": "z", "start": [x, -0.5, 0.0], "stop": [x, 0.5, 0.5],
     "nodes": [[x, 0.0, 0.0], [x, 0.0, 0.5], [0.0, 2.0, 0.0], [0.0, 0.0, 0.535]], "part": k == 1}
    for k, x in ((1, -5.0), (2, 5.0))]}


@pytest.mark.parametrize(("mode", "parts", "kw"), [
    ("setup", False, {"setup_only": True, "verbose": 2, "numThreads": 3, "debug_PEC": True}),
    ("setup", True, {"setup_only": True, "verbose": 2, "numThreads": 3, "debug_PEC": True, "debug_operator": True}),
    ("run", False, {"numThreads": 3, "dump_statistics": True})])
def test_run_keywords_never_carry_false(mode, parts, kw):  # spec 11: False drops the options after it
    got = worker.run_kwargs(mode, 3, parts)
    assert got == kw and False not in got.values() and "exact_endcriteria" not in got


def test_setup_mode_reads_the_log_and_the_dumps(tmp_path, monkeypatch):  # C-15, C-17, C-18, Review Focus 2
    log = fake_openems(monkeypatch)
    job = write_job(tmp_path, SMOKE, "setup")
    (job / worker.LOG).write_text(SETUP_LOG, encoding="utf-8")
    (job / worker.ERR).write_text("", encoding="utf-8")
    for f in DUMPS.iterdir():
        shutil.copy(f, job)
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    s = json.loads((job / "setup.json").read_text(encoding="utf-8"))
    assert (s["dt"], s["cells"], s["node"], s["unused"]) == (1.73972e-13, [65, 33, 16], [2, 0, 0, 6], [])
    assert s["dumps"] == ["PEC_dump.vtp", "operator_dump.vtr"]
    assert s["pec"][0] == pec_roots(DUMPS / "PEC_dump.vtp", LINES, SMOKE["ports"][0]["nodes"])
    assert s["c_box"] == {"P1": pytest.approx(2.3796e-14, rel=1e-3)}
    assert ("Run", (".",), worker.run_kwargs("setup", 1, True)) in log


def test_the_c_box_of_a_curve_port_is_its_one_edge(tmp_path, monkeypatch):  # C-18 for a CurvePort
    fake_openems(monkeypatch)
    curve = {"name": "L1", "kind": "curve", "dir": None, "start": [-5.0, 0.0, 0.0], "stop": [-5.0, 0.0, 0.5],
             "nodes": [[-5.0, 0.0, 0.0], [-5.0, 0.0, 0.5]], "part": True}
    job = write_job(tmp_path, {**SMOKE, "ports": [*SMOKE["ports"], curve]}, "setup")
    (job / worker.LOG).write_text(SETUP_LOG, encoding="utf-8")
    (job / worker.ERR).write_text("", encoding="utf-8")
    for f in DUMPS.iterdir():
        shutil.copy(f, job)
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    c = json.loads((job / "setup.json").read_text(encoding="utf-8"))["c_box"]["L1"]
    assert c == pytest.approx(1.9037e-14, rel=1e-3)  # the z-edge at (−5, 0, 0.25): one substrate edge


def test_a_setup_log_with_no_timestep_is_a_crash(tmp_path, monkeypatch):
    fake_openems(monkeypatch)
    job = write_job(tmp_path, SMOKE, "setup")
    (job / worker.LOG).write_text(SETUP_LOG.replace("FDTD timestep", "FDTD step"), encoding="utf-8")
    (job / worker.ERR).write_text("", encoding="utf-8")
    monkeypatch.chdir(job)
    with pytest.raises(RuntimeError, match="timestep"):
        worker.main(["job.json"])
    assert not (job / "setup.json").exists()


@pytest.mark.parametrize("mode", ["setup", "run"])
def test_a_setup_error_code_is_setup_failed_in_either_mode(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(worker, "build_csx", lambda *_: (None, types.SimpleNamespace(Run=lambda *_, **__: 1), None))
    monkeypatch.chdir(write_job(tmp_path, TINY, mode))
    assert worker.main(["job.json"]) == worker.SETUP_FAILED


def test_run_mode_writes_the_waves_from_the_probe_files(tmp_path, monkeypatch):  # Review Focus 2
    log = fake_openems(monkeypatch)
    job = write_job(tmp_path, TINY, "run")
    for name in ("port_ut_1", "port_it_1"):
        (job / name).write_text(PROBE, encoding="utf-8")
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    w = np.load(job / "waves.npz")
    assert set(w.files) == {"t_u", "u", "t_i", "i"} and w["u"].shape == (1, 3)
    assert ("Run", (".",), worker.run_kwargs("run", 1, False)) in log


def test_xml_mode_clears_a_stale_abort_and_writes_a_relative_file(tmp_path, monkeypatch):  # C-20
    log = fake_openems(monkeypatch)
    job = write_job(tmp_path, TINY, "xml")
    (job / "ABORT").write_text("")
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    assert not (job / "ABORT").exists() and ("Write2XML", ("model.xml",), {}) in log


def test_openems_that_will_not_import_is_exit_2(tmp_path, monkeypatch):  # C-31: the orchestrator names the variable
    monkeypatch.setitem(sys.modules, "CSXCAD", None)
    monkeypatch.setitem(sys.modules, "openEMS", None)
    monkeypatch.chdir(write_job(tmp_path, TINY, "xml"))
    assert worker.main(["job.json"]) == 2


def test_the_worker_imports_no_geometry_stack():  # spec 3.1, R21, C-5
    out = subprocess.run([sys.executable, "-I", "-c", "import sys, kicad_rf_studio.worker; print(sorted(m for m in "
                          "('shapely', 'scipy', 'matplotlib', 'skrf', 'pandas', 'openEMS', 'CSXCAD', "
                          "'kicad_rf_studio.core.post') if m in sys.modules))"],
                         capture_output=True, text=True).stdout
    assert out.strip() == "[]"


NF = {"f_hz": [1e9, 0.9e9], "center": [2.0, 2.0, 2.0]}  # TINY's band: 0.5–1.1 GHz


def finished_job(tmp_path, dumps=worker.DUMPS):
    """A run job of TINY with a far field, as openEMS leaves it: model.json above it, its job.json and `dumps`."""
    job = write_job(tmp_path, {**TINY, "nf2ff": NF}, "run")
    for name in dumps:
        (job / name).write_bytes(b"")
    return job


def transform_job(job):
    """The transform's own folder beside `job`, as far_field makes it, with the token ab12."""
    folder = job.parent / "job-0-nf2ff-ab12"
    folder.mkdir()
    (folder / "job.json").write_text(json.dumps({"spec": "../model.json", "port": 1, "mode": "nf2ff", "threads": 1,
                                                 "t_max": 1e-9, "dumps": f"../{job.name}", "out": "nf2ff-ab12"}),
                                     encoding="utf-8")
    return folder


def test_nf2ff_mode_transforms_each_grid_afresh_into_a_file_of_its_own(tmp_path, monkeypatch):  # design 5.5; RF 2
    log = fake_openems(monkeypatch)
    monkeypatch.chdir(transform_job(finished_job(tmp_path)))
    assert worker.main(["job.json"]) == 0
    calls = [(args, kw) for name, args, kw in log if name == "CalcNF2FF"]
    assert list(worker.GRIDS) == ["sphere", "elevation", "azimuth"]
    assert [kw["outfile"] for _, kw in calls] == [f"nf2ff-ab12-{grid}.h5" for grid in worker.GRIDS]
    assert all(kw["read_cached"] is False and args[0] == "../job-1-P1" for args, kw in calls)
    assert all(kw["center"] == pytest.approx([2e-3] * 3) for _, kw in calls)  # metres: the spec's 2 mm
    assert [args[1] for args, _ in calls] == [NF["f_hz"], NF["f_hz"][:1], NF["f_hz"][:1]]  # recorded ones only
    assert [(len(args[2]), len(args[3])) for args, _ in calls] == [(37, 72), (360, 2), (1, 360)]
    assert (calls[1][0][2][0], list(calls[1][0][3]), list(calls[2][0][2])) == (-180, [0, 90], [90])
    assert "Run" not in [name for name, _, _ in log]  # no FDTD


def test_nf2ff_mode_refuses_a_job_whose_far_field_was_never_recorded(tmp_path, monkeypatch):  # RF 3
    log = fake_openems(monkeypatch)
    monkeypatch.chdir(transform_job(finished_job(tmp_path, worker.DUMPS[:-1])))
    with pytest.raises(FileNotFoundError, match="nf2ff_H_5.h5"):
        worker.main(["job.json"])
    assert "CalcNF2FF" not in [name for name, _, _ in log]


def test_far_field_transforms_in_a_folder_of_its_own_and_never_reuses_a_file(tmp_path, fake):  # 5.5; RF 2
    job = finished_job(tmp_path)
    first, second = pipeline.far_field(job), pipeline.far_field(job)
    assert list(first) == list(second) == list(worker.GRIDS)
    assert all(p.parent == job and p.is_file() for p in (*first.values(), *second.values()))
    assert not set(first.values()) & set(second.values())
    folders = sorted(job.parent.glob("job-0-nf2ff-*"))
    assert len(folders) == 2 and {json.loads((f / "job.json").read_text(encoding="utf-8"))["dumps"]
                                  for f in folders} == {"../job-1-P1"}
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # Stage 1 3.1: a worker transformed it


def test_a_transform_that_fails_names_the_far_field_job(tmp_path, fake, monkeypatch):  # pt-BR design 5.1
    job = finished_job(tmp_path)
    monkeypatch.setenv("KRS_FAKE_EXIT", "1")
    with pytest.raises(KrsError) as e:
        pipeline.far_field(job)
    assert (e.value.code, e.value.params["job"], e.value.params["exit_code"]) == (
        "E_WORKER_FAILED", "T_JOB_FAR_FIELD", 1)


@pytest.mark.openems
@pytest.mark.parametrize("parent", ["run", "usuário ação"])  # Review Focus 2: a non-ASCII parent never reaches openEMS
@pytest.mark.parametrize("mode", ["xml", "setup", "run"])
def test_the_worker_on_a_tiny_model(tmp_path, mode, parent):
    job = write_job(tmp_path, TINY, mode, parent)
    with open(job / worker.LOG, "wb") as out, open(job / worker.ERR, "wb") as err:
        code = subprocess.run([sys.executable, "-I", "-u", "-m", "kicad_rf_studio.worker", "job.json"], cwd=job,
                              stdout=out, stderr=err, env={**os.environ, "OPENBLAS_NUM_THREADS": "1"}).returncode
    assert code == 0
    if mode == "xml":
        assert xml.etree.ElementTree.parse(job / "model.xml").getroot().tag == "openEMS"
    if mode == "setup":
        s = json.loads((job / "setup.json").read_text(encoding="utf-8"))
        assert s["cells"] == [5, 5, 5] and s["dt"] > 0 and s["unused"] == [] and len(s["pec"]) == 1
    if mode == "run":
        w = np.load(job / "waves.npz")
        assert w["u"].shape[0] == 1 and w["u"].shape[1] >= 2 and np.isfinite(w["u"]).all()
