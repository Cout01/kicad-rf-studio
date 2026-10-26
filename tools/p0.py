# SPDX-License-Identifier: GPL-3.0-or-later
"""The pieces the P0 harnesses share (plan 5, D-4..D-7): the P0 folder with its lock and STOP file, resumable steps
keyed by model and code, the load check, plain JSON records, the versions, the machine time and Markdown tables; then
the runs, traces and chains (D-9, D-16, D-38, D-40): harness models through the product's job phase, CLI runs and
their summaries, job traces, the one record-to-S reduction, closed chains and criterion 1.

Dev-time only: the harnesses under tools/ import it, and the package never does. They drive the product through its
own CLI (cli()) as child processes whose per-user data folder is <P0>/data (enter()), so the owner's real one is never
touched."""
import atexit
import contextlib
import io
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path, PurePath

import numpy as np

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.kicad.values import part_kind, port_value
from kicad_rf_studio.core.mesh import Mesh
from kicad_rf_studio.core.mesh.gates import dt_floor_reference
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.chain import loads, part_impedances, terminate, z_part
from kicad_rf_studio.core.post.waves import layout, s_matrix
from kicad_rf_studio.core.project import GATES, load_project, parts, save_project
from kicad_rf_studio.stoprule import KEPT, Z0, Records, growth_rise, stop_rule

ROOT = Path(__file__).resolve().parents[1]  # the repo
FIX = ROOT / "tests" / "fixtures"
START = date(2026, 10, 22)  # the timebox counts from plan 5's start (D-4)
MARKERS = ("kicad_rf_studio.worker", "emerge_fem", "pytest")  # in the command lines of workers, EMerge and tests
_LOCKS = {}  # each P0 folder this process entered, resolved, with the harness.lock it holds
LIMITS1 = {"ds21_db_f0": 0.1, "ds11_f0": 0.02, "ds_max": 0.03, "shift": 0.02}  # criterion 1 (spec 9.3, 9.4)
TRACE_BYTES = 100_000  # a trace file's largest size: D-40's about 50 KB, doubled so a six-port record fits whole (Task 19 ruling)


def default_out() -> Path:
    """The default P0 folder, kicad-rf-studio-p0 beside the per-user data folder: read it before enter()."""
    return runs.data_dir().parent / "kicad-rf-studio-p0"


def inside_git(path: Path) -> bool:
    """Whether `path`, resolved, or one of its parents holds a .git file or folder. No git process, so a missing git, a
    refused repo or a GIT_DIR cannot read as outside; a worktree, a submodule, a file inside a repo and the .git folder
    itself are all inside."""
    path = path.resolve()
    return any((p / ".git").exists() for p in (path, *path.parents))


def enter(out: Path) -> Path:
    """Makes `out` this process's P0 folder (D-7) and returns it resolved: makes out/data, points LOCALAPPDATA and
    XDG_DATA_HOME at it, so runs.* here and every child use it, and holds out/harness.lock for the life of the process.
    The lock is taken once per folder, so entering a folder again only points the two variables at it again.
    SystemExit, with nothing made, for a folder inside a git work tree; raises E_LOCKED while another live harness
    holds the folder."""
    out = out.resolve()
    if inside_git(out):
        raise SystemExit(f"p0: {out} is inside a git work tree; choose a P0 folder outside every repository")
    if out not in _LOCKS:
        (out / "data").mkdir(parents=True, exist_ok=True)
        lock = runs.project_lock(out / "harness", out)
        lock.__enter__()  # E_LOCKED while another live harness holds it
        _LOCKS[out] = lock
        atexit.register(lock.__exit__, None, None, None)  # a normal exit removes it; the next enter reclaims a crash's
    os.environ["LOCALAPPDATA"] = os.environ["XDG_DATA_HOME"] = str(out / "data")
    return out


def cli(*args: str) -> tuple[int, str]:
    """Runs the product's CLI with `args` as a child process, with this process's environment and UTF-8 text. Returns
    its exit code and its stdout followed by its stderr."""
    child = [sys.executable, "-c", "import sys; from kicad_rf_studio.cli import main; sys.exit(main(sys.argv[1:]))"]
    done = subprocess.run([*child, *args], capture_output=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return done.returncode, done.stdout + done.stderr


def command_lines() -> list[str]:
    """The command line of every process: Win32_Process's through PowerShell on Windows, /proc/*/cmdline elsewhere.
    Raises when the check cannot run."""
    if sys.platform == "win32":  # PowerShell writes in the console code page, so a stray byte is replaced (PF-10)
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-CimInstance Win32_Process).CommandLine"]
        return subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=True,
                              timeout=60).stdout.splitlines()
    lines = []
    for pid in filter(str.isdigit, os.listdir("/proc")):  # no /proc raises
        with contextlib.suppress(OSError):  # the process ended meanwhile
            lines.append((Path("/proc") / pid / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace"))
    return lines


def busy() -> dict:
    """The PC's load now (D-6): "workers", "emerge" and "pytest", the numbers of command lines holding each of MARKERS
    (each None when command_lines raised), and "calibration", this machine's entry in settings.json or None."""
    # ponytail: matched by substring, read at a step's start and end only; a process that starts and ends between them
    # is not seen
    try:
        lines = command_lines()
    except (OSError, subprocess.SubprocessError):
        lines = None
    counts = {name: None if lines is None else sum(marker in line for line in lines)
              for name, marker in zip(("workers", "emerge", "pytest"), MARKERS)}
    return {**counts, "calibration": runs.load_settings().get("machines", {}).get(runs.machine_key())}


def plain(o):
    """json.dumps's default, so a long run's record is never lost to a TypeError: a complex number (Python or numpy) as
    [re, im], a numpy scalar as its Python value, an array as a list, a path as its name, anything else as its repr."""
    if isinstance(o, complex):
        return [o.real, o.imag]
    if isinstance(o, (np.generic, np.ndarray)):  # numpy's complex64 comes back here as a Python complex
        return o.tolist()
    if isinstance(o, PurePath):
        return o.name
    return repr(o)


def save(path: Path, data) -> dict:
    """Writes `data` as plain JSON, plain() for what json cannot write and null for NaN and ±inf, with save_project (a
    temporary file, then os.replace), making its folder first. Returns what it wrote."""
    data = json.loads(json.dumps(data, default=plain), parse_constant=lambda _: None)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_project(path, data)
    return data


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, errors="replace",
                          check=True).stdout.strip()


def code_id() -> str:
    """The id of the committed product tree, `git rev-parse HEAD:src`, plus "+dirty" when a tracked file under src
    differs from it."""
    dirty = _git("status", "--porcelain", "--untracked-files=no", "--", "src")
    return _git("rev-parse", "HEAD:src") + ("+dirty" if dirty else "")


def step(out: Path, step_id: str, key: str, work: Callable[[], dict]) -> dict:
    """One resumable step of a harness (D-6), recorded in out/steps/<step_id>.json. SystemExit when out/STOP exists or
    when runs.data_dir() is not inside `out` (D-7, fail closed). Returns the stored record when it holds key@code_id(),
    so changed product code runs the step again; else runs `work` between two busy() readings and stores {"step",
    "key", "code", "load", "load_end", "loaded", "started", "wall_s", "result"} with save() once `work` returned, so a
    crash leaves no record. "loaded": a reading counted another process, or the check failed (PF-9). Returns the
    record as stored."""
    if (out / "STOP").exists():
        raise SystemExit(f"p0: {out / 'STOP'} exists; delete it to go on")
    if not runs.data_dir().resolve().is_relative_to(out.resolve()):
        raise SystemExit(f"p0: the data folder {runs.data_dir()} is not inside {out}; call p0.enter first")
    path, code = out / "steps" / f"{step_id}.json", code_id()
    key = f"{key}@{code}"  # the model's key and the product code's id
    if path.is_file():
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("key") == key:
            return record
    load, started, t0 = busy(), time.strftime("%Y-%m-%dT%H:%M:%S"), time.monotonic()
    result = work()
    wall_s, load_end = time.monotonic() - t0, busy()
    loaded = any(n is None or n > 0 for reading in (load, load_end)
                 for n in (reading["workers"], reading["emerge"], reading["pytest"]))
    return save(path, {"step": step_id, "key": key, "code": code, "load": load, "load_end": load_end, "loaded": loaded,
                       "started": started, "wall_s": wall_s, "result": result})


def records(out: Path, ids: list[str]) -> list[dict]:
    """The records of the steps `ids`, from out/steps. SystemExit naming the missing ids, or the ids whose "code"
    differs from the first one's: a gate is never assembled from two codes."""
    paths = [out / "steps" / f"{i}.json" for i in ids]
    if missing := [i for i, p in zip(ids, paths) if not p.is_file()]:
        raise SystemExit(f"p0: no record of {', '.join(missing)} in {out / 'steps'}; run the harness first")
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    if other := [i for i, r in zip(ids, recs) if r["code"] != recs[0]["code"]]:
        raise SystemExit(f"p0: {', '.join(other)} ran on other product code than {ids[0]}; run the harness again")
    return recs


def versions() -> dict:
    """What a gate ran on, with no path and no host name: the short HEAD commit, code_id(), the Python, openEMS and
    CSXCAD versions (None when openEMS is missing), the OS and the number of CPUs."""
    try:
        openems, csxcad = runs.openems_versions()
    except KrsError:  # E_OPENEMS_MISSING
        openems = csxcad = None
    return {"commit": _git("rev-parse", "--short", "HEAD"), "code": code_id(), "python": platform.python_version(),
            "openems": openems, "csxcad": csxcad, "os": platform.platform(), "cpus": os.cpu_count()}


def machine(records: list[dict]) -> dict:
    """The machine time of `records` (D-4): the number of steps, their machine hours, the loaded steps' ids and the
    days elapsed since START."""
    return {"steps": len(records), "machine_hours": sum(r["wall_s"] for r in records) / 3600,
            "loaded": [r["step"] for r in records if r["loaded"]], "elapsed_days": (date.today() - START).days}


def table(rows: list[dict], cols: list[str]) -> str:
    """`rows` as a Markdown table of the columns `cols`: a float as :.4g, None or a missing column as "–"."""
    def cell(v) -> str:
        return "–" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v)

    lines = [cols, ["---"] * len(cols), *([cell(row.get(c)) for c in cols] for row in rows)]
    return "\n".join("| " + " | ".join(line) + " |" for line in lines)


def criterion1(cmp: dict) -> dict:
    """Criterion 1 (spec 9.3, 9.4) on a checks.compare result `cmp` under LIMITS1: whether each of ds21_db_f0, ds11_f0
    and ds_max is within its limit; "nulls", "n/a" without a null, else whether every null's |shift| is within its
    limit (an unmatched null, shift None, fails); "pass" when all of them hold."""
    out = {key: bool(cmp[key] <= LIMITS1[key]) for key in ("ds21_db_f0", "ds11_f0", "ds_max")}
    nulls = "n/a" if not cmp["nulls"] else all(
        null["shift"] is not None and abs(null["shift"]) <= LIMITS1["shift"] for null in cmp["nulls"])
    return {**out, "nulls": nulls, "pass": all(out.values()) and nulls is not False}


def model_of(spec: dict) -> pipeline.Model:
    """A harness model (D-9) of the model spec `spec`, for the product's job phase: its mesh lines as a Mesh, d, dz0,
    pinned and edges left empty, no blocking gate, and the timestep floor's reference of those lines."""
    mesh = Mesh(*(np.array(spec["mesh"][axis]) for axis in "xyz"), 0.0, 0.0, {}, {})
    return pipeline.Model(mesh, spec, [], dt_floor_reference(mesh))


def model_key(pj: Path) -> str:
    """The key of a step that runs the project `pj` (project.json): the spec_hash of the model the product builds from
    it (pipeline.load, build_model), or "blocked" when the edge lint left no spec."""
    project, board, geom, _ = pipeline.load(pj)
    spec = pipeline.build_model(project, board, geom).spec
    return "blocked" if spec is None else spec_hash(spec)


def edit(project: dict, edits: dict) -> dict:
    """Sets each dotted key of `edits` ("mesh.n") to its value in `project`, in place, making its groups as needed;
    returns `project`."""
    for dotted, value in edits.items():
        *groups, name = dotted.split(".")
        node = project
        for group in groups:
            node = node.setdefault(group, {})
        node[name] = value
    return project


def run_path(name: str) -> Path:
    """The run folder `name` in the data folder, the P0 folder's once enter() ran."""
    return runs.data_dir() / "runs" / name


def run_model(model: pipeline.Model, preset: str, stem: str, ports: list[int], t_max: float | None = None) -> dict:
    """The product's job phase on a harness model (D-9): prepare, its lines printed; a fresh runs.run_dir_for(stem);
    the setup gate at GATES, its blocking gates recorded, never applied; then, when `ports` (1-based) is not empty,
    run_ports on those ports only, at `preset`, to `t_max` (default the spec's), at most as many at once as there are.
    KeyboardInterrupt when a job was stopped, so a stopped run is never recorded. Returns {"run_dir": the folder's
    name, "setup": setup.json, "blocked" and "warnings": [[code, params]], "jobs": the jobs as results record them,
    each plus "job", its folder's name, "pool", "wall_s" (None without jobs), "speeds_mcs": each job's MC/s}."""
    threads, pool, _ = pipeline.prepare(model, lambda code, params: print(render(code, **params)))
    run_dir, pool = runs.run_dir_for(stem), min(pool, len(ports))
    setup, blocked, warnings = pipeline.setup_gate(model, {"gates": GATES}, run_dir, runs.load_settings(), threads)
    done, speeds, wall_s = (pipeline.run_ports(model, run_dir, setup, threads, pool, preset, GATES, ports, t_max)
                            if ports else ([], [], None))
    if any(job["verdict"] == "stopped" for job in done):
        raise KeyboardInterrupt
    names = [q["name"] for q in model.spec["ports"]]
    return {"run_dir": run_dir.name, "setup": setup, "blocked": [[c, p] for c, p in blocked],
            "warnings": [[c, p] for c, p in warnings],
            "jobs": [{**job, "job": runs.job_dir(run_dir, k, names[k - 1]).name} for job, k in zip(done, ports)],
            "pool": pool, "wall_s": wall_s, "speeds_mcs": [speed / 1e6 for speed in speeds]}


def cli_run(pj: Path, command: str) -> dict:
    """`run` or `verify` (`command`) on the project `pj` (project.json) through cli(), for a step to store: {"exit",
    "run_dir": the name of the newest run folder the command made whose whole name is runs.run_dir_for's for the
    project's folder (PF-16), else None, "jobs": the jobs project.json's results (verify's, for `verify`) record for
    that folder, else None, "wall_s": likewise}. RuntimeError, so that the step records nothing and runs again, on exit
    1 or 130, or on exit 2 naming the project's lock (E_LOCKED: an orphaned child holds the project). An exit 4 is
    stored: its stopped verdicts could only come from a STOP file inside a run folder, which the stop procedure
    forbids."""
    home = runs.data_dir() / "runs"
    before = set(home.glob("*"))
    code, text = cli(command, str(pj))
    if code in (1, 130) or code == 2 and f"{pj}.lock" in text:
        raise RuntimeError(f"p0: {command} {pj} exited {code}:\n{text}")
    name = re.compile(re.escape(runs.ascii_name(pj.absolute().parent.name)) + r"-\d{8}-\d{6}-[0-9a-f]{4}")
    made = [p for p in set(home.glob("*")) - before if name.fullmatch(p.name)]
    run_dir = max(made, key=lambda p: p.stat().st_mtime_ns).name if made else None
    stored = load_project(pj).get("results" if command == "run" else "verify", {})
    ours = run_dir is not None and Path(stored.get("run_dir", "")).name == run_dir
    return {"exit": code, "run_dir": run_dir, "jobs": stored["jobs"] if ours else None,
            "wall_s": stored.get("wall_s") if ours else None}


def save_trace(job: Path, ports: int, dt: float, k: int, exc: dict, t_cut: float | None, out: Path) -> Path:
    """Writes the records of the job folder `job` (pipeline.records, `ports` ports, timestep `dt`) to `out`, making its
    folder first, as np.savez_compressed members t_u, u, t_i, i, te, e, exc ([f1, f2, t0] of the excitation `exc`), k
    (the excited port `k`, 1-based, stored as k − 1) and t_cut (NaN for None); returns `out`. At most TRACE_BYTES
    (D-40): the energy rows are thinned by 2 while the file is larger, never the probe samples, which the exact replay
    needs (PF-15); ValueError naming the job, with nothing written, when the probe samples alone exceed it."""
    rec = pipeline.records(job, ports, dt)
    fixed = {"t_u": rec.t_u, "u": rec.u, "t_i": rec.t_i, "i": rec.i,
             "exc": np.array([exc["f1"], exc["f2"], exc["t0"]]), "k": np.array(k - 1),
             "t_cut": np.array(np.nan if t_cut is None else t_cut)}
    te, e = rec.te, rec.e
    while True:
        buf = io.BytesIO()
        np.savez_compressed(buf, te=te, e=e, **fixed)
        if len(data := buf.getvalue()) <= TRACE_BYTES:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            return out
        if not len(te):
            raise ValueError(f"p0: the probe samples of {job} alone exceed {TRACE_BYTES} bytes")
        te, e = (te[::2], e[::2]) if len(te) > 1 else (te[:0], e[:0])


def load_trace(path: Path) -> tuple[Records, int, dict, float | None]:
    """The trace save_trace wrote at `path`: (its Records, the excited port's 0-based row, {"f1", "f2", "t0"}, its
    t_cut, None for NaN). Nothing is unpickled."""
    with np.load(path) as z:
        f1, f2, t0 = z["exc"].tolist()
        t_cut = float(z["t_cut"])
        return (Records(*(z[m] for m in ("t_u", "u", "t_i", "i", "te", "e"))), int(z["k"]),
                {"f1": f1, "f2": f2, "t0": t0}, None if math.isnan(t_cut) else t_cut)


def s_of(traces: list[tuple[Records, int, dict, float | None]], f: np.ndarray, preset: str | None = None,
         rows: list[int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """S on `f` (Hz) from job records, the one record-to-S reduction of the tools (the empty box, P0-C's per-preset
    replay, P0-D): each trace (Records, the excited port's 0-based row k, the excitation {"f1", "f2", "t0"}, t_cut)
    replayed at `preset` (stop_rule, causal) and cut at its verdict, or cut at its own t_cut when `preset` is None,
    and taken whole without one; u and i restricted to `rows` (default every port). One trace gives its column
    (F, N, 1), s_jk = (U_j − Z0·I_j)/(U_k + Z0·I_k); N traces give s_matrix's S (F, N, N). Returns (S, the cut times,
    NaN for a whole record)."""
    rows = slice(None) if rows is None else rows
    cut, times = [], []
    for rec, k, exc, t_cut in traces:
        if preset is not None:
            verdict = stop_rule(rec, k, preset, exc)
            t_cut = verdict.t if verdict else None
        n = len(rec.t_u) if t_cut is None else np.searchsorted(rec.t_u, t_cut, "right")
        cut.append((rec.t_u[:n], rec.u[:, :n], rec.t_i[:n], rec.i[:, :n]))
        times.append(np.nan if t_cut is None else t_cut)
    if len(cut) > 1:
        return s_matrix([(t_u, u[rows], t_i, i[rows]) for t_u, u, t_i, i in cut], f)[0], np.array(times)
    # ponytail: one excitation gives a column that carries the feeds' port parasitics, the same on both sides of a
    # comparison
    (t_u, u, t_i, i), k = cut[0], traces[0][1]
    U, I = (x @ np.exp(-2j * np.pi * np.outer(t, f)) for x, t in ((u, t_u), (i, t_i)))
    s = (U[rows] - Z0 * I[rows]) / (U[k] + Z0 * I[k])  # mirrors the s(at) in stoprule._converged
    return s.T[:, :, None], np.array(times)


def closed_chain(pj: Path, *, f: np.ndarray | None = None, ideal: bool = False, cbox: dict | None = None,
                 key: str = "results", cuts: list[float | None] | None = None) -> tuple[np.ndarray, np.ndarray, int]:
    """The chain of the run that the project `pj` (project.json) holds under `key` ("verify": verify's own N-port,
    which has no part port), as `run` writes chain.s{P}p: the layout at `f` (one holding f0; default the grid), each
    job cut at cuts[k] in place of its t_cut when given, each part port closed by Z_part ∥ C_box, Z_part from the
    part models and S2P files, or from the ideal values when `ideal` (as verify closes them), C_box the run's or, when
    given, `cbox`'s (by ref). Returns (f, S (F, P, P), the index of f0 in f)."""
    project = load_project(pj)
    run = project[key]
    if cuts is not None:
        run = {**run, "jobs": [{**job, "t_cut": t} for job, t in zip(run["jobs"], cuts, strict=True)]}
    lay = layout(project, run, f=f)
    ext, refs = [k for k, q in enumerate(lay.ports) if not q["part"]], [q["name"] for q in lay.ports if q["part"]]
    if ideal:
        by_ref = parts(project)
        zparts = {ref: z_part(part_kind(ref), port_value(ref, by_ref[ref]["value"]), None, lay.f) for ref in refs}
    else:
        zparts = part_impedances(project, pj.parent, refs, lay.f)[0]
    zk = loads(zparts, refs, run.get("c_box", {}) if cbox is None else cbox, lay.f)
    return lay.f, terminate(lay.s, ext, zk, lay.f), lay.markers[0]


def predicted_s(runs: int, pool: int, cells: int, dt: float, t: float, mcs: float) -> float:
    """The machine time in s of `runs` jobs of `cells` cells at the timestep `dt` (s) to the simulated time `t` (s),
    `pool` at once at `mcs` MC/s a job (D-16)."""
    return math.ceil(runs / pool) * cells * (t / dt) / (mcs * 1e6)  # mirrors the time() in pipeline.cost_notes


def summary(record: dict) -> dict:
    """The numbers of a CLI run from its step `record` (cli_run's) and its run folder (events.jsonl, model.json,
    setup.json), each None when it is missing: {"exit"; "cells" (I_COST_CELLS); "dt" (setup.json); "dt_ratio"
    (I_COST_DT's dt / ref); "pool" (I_RUN_START); "jobs": [{"port", "verdict", "t_cut", "t_stop", "residual_db",
    "growth_db"}], the record's jobs, else the jobs' verdict events, with growth_db, stoprule.growth_rise, and a
    missing t_stop read from each job's records; "wall_s", the run's job phase, else the step's; "predicted_s", to the
    longest t_stop of the jobs that kept S, and "worst_s", to T_max, by predicted_s at runs.per_job_mcs of the
    calibration the step's load saw at its start; "indicators": {"sigma", "recip", "loss_pct", "expected_pct"} of the
    result events; "warnings", the W_ codes among them; "lid_mm", the lid plate's z in model.json minus the top
    copper face; "run_dir", its name}. Event params are read into numbers and port names, never copied whole."""
    res, entry = record["result"], record["load"]["calibration"]
    folder = run_path(res["run_dir"]) if res["run_dir"] else None

    def read(*names: str):
        """The JSON in a file of the run folder, events.jsonl as a list of events; None when it is missing."""
        path = folder.joinpath(*names) if folder else None
        if path is None or not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()] if path.suffix == ".jsonl" else json.loads(text)

    def number(value, scale: float = 1.0) -> float | None:
        return None if value is None else float(value) * scale

    events, spec, setup = read("events.jsonl") or [], read("model.json"), read("job-0-setup", "setup.json")
    first = {}  # each code's first params
    for event in events:
        first.setdefault(event["code"], event["params"])
    results = [event for event in events if event["kind"] == "result"]
    if res["jobs"] is not None:
        base = [(k, {key: job[key] for key in ("port", "verdict", "t_cut", "t_stop", "residual_db")})
                for k, job in enumerate(res["jobs"], 1)]
    else:  # no results for this folder: the jobs' verdict events, whose t_ns is the cut where the rule gave a verdict
        kinds, base = {code: kind for kind, code in pipeline.VERDICTS.items()}, []
        for event in events:
            if event["kind"] == "verdict" and event["job"]:
                p, kind = event["params"], kinds[event["code"]]
                cut = kind in ("converged", "flat", "diverged", "growth")  # else t_ns is the last sample's
                base.append((event["job"], {"port": p["port"], "verdict": kind, "residual_db": number(p["residual_db"]),
                                            "t_cut": number(p["t_ns"], 1e-9) if cut else None}))
    jobs = []
    for k, job in base:
        rec = pipeline.records(runs.job_dir(folder, k, job["port"]), len(spec["ports"]), setup["dt"])
        jobs.append({"t_stop": pipeline.last_sample(rec)[0], **job,  # the record's t_stop, else the last sample's
                     "growth_db": growth_rise(rec, spec["excitation"]["t0"])})
    size, cost_dt, start = first.get("I_COST_CELLS"), first.get("I_COST_DT"), first.get("I_RUN_START")
    cells = size and size["nx"] * size["ny"] * size["nz"]
    dt, pool = setup and setup["dt"], start and start["pool"]

    def time_to(t: float | None) -> float | None:
        if None in (t, cells, dt, pool, entry):
            return None
        return predicted_s(len(jobs), pool, cells, dt, t, runs.per_job_mcs(entry, pool))

    def indicator(suffix: str, field: str) -> float | None:
        params = next((event["params"] for event in results if event["code"].endswith(suffix)), None)
        return number(params and params[field])

    plate = spec and spec["metal"]["lid"]["plate"]
    kept = [job["t_stop"] for job in jobs if job["verdict"] in KEPT and job["t_stop"] is not None]
    return {"exit": res["exit"], "cells": cells, "dt": dt,
            "dt_ratio": cost_dt and float(cost_dt["dt"]) / float(cost_dt["ref"]), "pool": pool, "jobs": jobs,
            "wall_s": record["wall_s"] if res["wall_s"] is None else res["wall_s"],
            "predicted_s": time_to(max(kept, default=None)), "worst_s": time_to(spec and spec["excitation"]["t_max"]),
            "indicators": {"sigma": indicator("_PASSIVITY", "sigma"), "recip": indicator("_RECIPROCITY", "err"),
                           "loss_pct": indicator("LOSS_BUDGET", "layout_pct"),
                           "expected_pct": indicator("LOSS_BUDGET", "expected_pct")},
            "warnings": [event["code"] for event in results if event["code"].startswith("W_")],
            "lid_mm": plate and plate["z"] - max(solid["z"][1] for solid in spec["metal"]["copper"]),
            "run_dir": res["run_dir"]}
