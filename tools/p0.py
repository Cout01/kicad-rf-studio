# SPDX-License-Identifier: GPL-3.0-or-later
"""The pieces the P0 harnesses share (plan 5, D-4..D-7): the P0 folder with its lock and STOP file, resumable steps
keyed by model and code, the load check, plain JSON records, the versions, the machine time and Markdown tables.

Dev-time only: the harnesses under tools/ import it, and the package never does. They drive the product through its
own CLI (cli()) as child processes whose per-user data folder is <P0>/data (enter()), so the owner's real one is never
touched."""
import atexit
import contextlib
import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path, PurePath

import numpy as np

from kicad_rf_studio import runs
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import save_project

ROOT = Path(__file__).resolve().parents[1]  # the repo
FIX = ROOT / "tests" / "fixtures"
START = date(2026, 10, 22)  # the timebox counts from plan 5's start (D-4)
MARKERS = ("kicad_rf_studio.worker", "emerge_fem", "pytest")  # in the command lines of workers, EMerge and tests
_LOCKS = {}  # each P0 folder this process entered, resolved, with the harness.lock it holds


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
