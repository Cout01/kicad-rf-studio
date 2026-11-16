# SPDX-License-Identifier: GPL-3.0-or-later
"""The shared pins of Stage 5 plan 3 (plan 3 ruling 2, Stage 5 design 8 risk 11): sha256 digests of what plan 3's
shared edits reach that golden_v1, golden_antenna and golden_si do not hash, recorded once at a87bcc1, before plan 3's
first shared edit, in tests/fixtures/golden_s5.json with golden_v1.env(). For each case of the three golden tools,
load()'s notes, the cost lines at pool 1 and at pool 4 with a kept run, every call build_csx makes (verify's model
too for lpf915 and ifa2g4_pi), and an antenna's or SI project's fingerprint; the stop rule's verdicts on the committed
traces and P3-A's hand-written specs; and a whole cost, run and (lpf915's) verify through the fake worker: exit codes,
the results and verify blocks, every event line, every job.json and the results/ files. tests/test_golden_v1.py,
test_golden_antenna.py and test_golden_si.py compare the cases everywhere and the runs where env() matches.

Dev-time only: run it once with `python tools/golden_s5.py`, which records in English through golden_v1.record. It
refuses to overwrite the JSON; a new recording is a controller ruling, which deletes the file first."""
import os

if __name__ == "__main__":
    os.environ["LANGUAGE"] = "en"  # the suite's language, set before core.messages binds one: golden_v1.env() holds it

import contextlib
import json
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import golden_antenna
import golden_si
import golden_v1
import p0
import p3a
from golden_antenna import _board
from golden_v1 import sha
from kicad_rf_studio import cli, pipeline, runs
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.csx import build_csx
from kicad_rf_studio.core.model.spec import far_field_box, spec_hash, verify_spec
from kicad_rf_studio.core.project import antenna, load_project, parts, save_project, si
from kicad_rf_studio.stoprule import PRESETS, stop_rule

sys.path.append(str(p0.ROOT / "tests"))  # fake_cli, test_cli_si, test_model_csx: the fake, si_args, the recorder
from fake_cli import patches  # noqa: E402
from test_cli_si import si_args  # noqa: E402
from test_model_csx import Rec  # noqa: E402

GOLDEN = p0.FIX / "golden_s5.json"
SETUP = {"dt": 1e-13, "node": [0, 1, 1, 1]}  # the setup.json cost_notes reads: openEMS's dt and the edge that sets it
VOLATILE = ("folder", "run_dir", "path", "log", "wall")  # event params that hold a path or a measured time


def digest(data) -> str:
    return sha(json.dumps(data, sort_keys=True, default=str).encode())


def csx_calls(spec: dict) -> str:
    """The sha256 of every call build_csx(spec, 1, its T_max) makes, CSXCAD and openEMS standing in as Recs, an object
    passed to one by its type's name. Each module is a namespace holding its Rec, as test_model_csx's fake_openems has
    it: once PySide6 is imported, its import hook reads every imported module's source, and a Rec as the module answers
    every __wrapped__ (inspect.unwrap's ValueError)."""
    log = []
    stand_ins = {"CSXCAD": SimpleNamespace(ContinuousStructure=Rec(log, "ContinuousStructure")),
                 "CSXCAD.CSProperties": SimpleNamespace(CSPropDebyeMaterial=Rec(log, "CSPropDebyeMaterial")),
                 "openEMS": SimpleNamespace(openEMS=Rec(log, "openEMS"))}
    with mock.patch.dict(sys.modules, stand_ins):
        build_csx(spec, 1, spec["excitation"]["t_max"])
    return sha(json.dumps(log, default=lambda o: type(o).__name__).encode())


def case(pj: Path, verify: bool = False) -> dict:
    """The pins of the project `pj` as `new` wrote it: load()'s notes, the cost lines at pool 1 and at pool 4 with a
    kept run of this model, the CSX calls, an antenna's or SI project's fingerprint without the two versions, and with
    `verify` the CSX calls of verify's model, as golden_v1 builds lpf915's and golden_antenna ifa2g4_pi's."""
    project, board, geom, notes = pipeline.load(pj)
    model = pipeline.build_model(project, board, geom)
    spec = model.spec
    kept = {**project, "results": {"model_hash": spec_hash(spec), "jobs": [{"verdict": "converged", "t_stop": 5e-9}]}}
    out = {"load": digest(notes),
           "cost": digest([pipeline.cost_notes(model, project, SETUP, 4, 1, 100.0),
                           pipeline.cost_notes(model, kept, SETUP, 2, 4, 3.0)]),
           "csx": csx_calls(spec)}
    if antenna(project) or si(project):
        with mock.patch.object(runs, "openems_versions", lambda: ("0.37.0", "0.7.0")):
            fp = pipeline.fingerprint(project)
        out["fingerprint"] = digest({k: v for k, v in fp.items() if k not in ("app", "openems")})
    if verify:
        dump = pj.parent / "operator_dump.vtr"
        dump.write_bytes(b"")
        with mock.patch.object(spec_module, "c_box", lambda *_: 2e-14):
            vspec = verify_spec(spec, parts(project), dump, 1e-13,
                                far_field=far_field_box(project, board, geom) if antenna(project) else None)
        out["csx_verify"] = csx_calls(vspec)
    return out


def _step(code: int, run_dir: Path, block: dict | None = None) -> dict:
    """A command's pins: its exit `code`, the `block` it stored in project.json without its folder and wall time, its
    events in `run_dir` without VOLATILE's params, and each job.json there."""
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return {"exit": code,
            "record": block and digest({k: v for k, v in block.items() if k not in ("run_dir", "wall_s")}),
            "events": digest([[e["kind"], e["job"], e["code"], {k: v for k, v in e["params"].items()
                                                                 if k not in VOLATILE}] for e in events]),
            "jobs": {job.name: sha((job / "job.json").read_bytes()) for job in sorted(run_dir.glob("job-*"))}}


def fake_run(pj: Path, verify: bool = False) -> dict:
    """A whole cost, run and, with `verify`, verify of `pj` through the fake worker, each a _step, then each results/
    file's sha256. Unwatched (run_jobs with no watch), each fake job writes its whole trace, so verdicts, t_stop and
    waves are the same on every call; the data folder is data-<project folder> with conftest's `calibrated` in it."""
    data, real = Path(f"data-{pj.parent.name}"), runs.run_jobs

    def unwatched(jobs, pool, run_dir, settings, watch=None):
        return real(jobs, pool, run_dir, settings)

    # each command's run folder is named for it: run_dir_for's name holds the time, which every Touchstone port map
    # prints
    folder = data / "runs"
    with (mock.patch.multiple(runs, **patches(data), free_ram_mb=lambda: 1e6, run_jobs=unwatched),
          mock.patch.object(secrets, "token_hex", lambda n: "0" * (2 * n)),
          mock.patch.object(spec_module, "c_box", lambda *_: 2e-14) if verify else contextlib.nullcontext()):
        runs.save_settings({"machines": {runs.machine_key(): {
            "threads": 2, "pool": 2, "aggregate_mcs": 400.0, "single": {"2": 200.0}, "parallel": {"2": 400.0},
            "at": "2026-10-21T00:00:00"}}})
        (folder / "cost").mkdir(parents=True)  # made first: cost writes every line as an event
        out = {"cost": _step(pipeline.cost(pj, folder / "cost"), folder / "cost")}
        code = pipeline.run(pj, folder / "run")
        out["run"] = _step(code, folder / "run", load_project(pj).get("results"))
        if verify:
            code = pipeline.verify(pj, folder / "verify")
            out["verify"] = _step(code, folder / "verify", load_project(pj).get("verify"))
    return {**out, "files": {f.name: sha(f.read_bytes()) for f in sorted((pj.parent / "results").iterdir())}}


def shared_v1() -> dict:
    """golden_v1's cases built as it builds them, each a case() (lpf915's with verify's model), lpf915's fake_run with
    verify, the stop rule's verdicts on each committed trace at each preset, and P3-A's spec hashes."""
    pjs = {}
    for name, (start, end, lid) in golden_v1.CASES.items():
        pjs[name], _ = cli.new(_board(name), start, end, 915e6, lid_height=lid, output=Path(name))
        if name == "lpf915-45":
            save_project(pjs[name], {**load_project(pjs[name]), "allow_curve_port": True})
    cases = {name: case(pj, verify=name == "lpf915") for name, pj in pjs.items()}
    stop = {}
    for path in sorted((p0.FIX / "traces").glob("*.npz")):
        rec, k, exc, _ = p0.load_trace(path)
        verdicts = {preset: stop_rule(rec, k, preset, exc) for preset in PRESETS}
        stop[path.stem] = {preset: v and [v.kind, v.t, round(v.residual_db, 2)] for preset, v in verdicts.items()}
    return {"cases": cases, "run": {"lpf915": fake_run(pjs["lpf915"], verify=True)}, "stop": stop,
            "p3a": {sid: spec_hash(s) for sid, s in p3a.specs().items()}}


def shared_antenna() -> dict:
    """golden_antenna's BANDS built as it builds them, each a case() (ifa2g4_pi's with verify's model), and ifa2g4's
    fake_run, whose transform's job.json joins its run's."""
    pjs = {name: cli.new_antenna(_board(name), "U1.1", "AE1", band, output=Path(name))[0]
           for name, band in golden_antenna.BANDS.items()}
    cases = {name: case(pj, verify=name == "ifa2g4_pi") for name, pj in pjs.items()}
    return {"cases": cases, "run": {"ifa2g4": fake_run(pjs["ifa2g4"])}}


def shared_si() -> dict:
    """golden_si's CASES built as it builds them, each a case(), and usb2_hs's fake_run on the KRS_FAKE=network fake,
    as tests/test_si_run.py runs SI: SI's layout reads S from DC, which the default fake's pulse does not reach."""
    pjs = {}
    for name in golden_si.CASES:
        file = Path(_board(name))
        args, kw = si_args(file)
        pjs[name] = cli.new_si(file, *args, **kw, output=Path(name))[0]
    cases = {name: case(pj) for name, pj in pjs.items()}
    with mock.patch.dict(os.environ, {"KRS_FAKE": "network"}):
        return {"cases": cases, "run": {"usb2_hs": fake_run(pjs["usb2_hs"])}}


def digests() -> dict:
    """{"v1": shared_v1(), "antenna": shared_antenna(), "si": shared_si()}, each in a new subfolder of the working
    folder, so the three tools' case folders never meet (golden_antenna writes golden_v1's too)."""
    out = {}
    for kind, shared in (("v1", shared_v1), ("antenna", shared_antenna), ("si", shared_si)):
        os.mkdir(kind)
        os.chdir(kind)
        try:
            out[kind] = shared()
        finally:
            os.chdir("..")
    return out


def main() -> int:
    """Records digests() in GOLDEN through golden_v1.record; 1 when GOLDEN exists."""
    return golden_v1.record(GOLDEN, digests)


if __name__ == "__main__":
    sys.exit(main())
