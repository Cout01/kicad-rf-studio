# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI's Qt-free logic (Stage 2 design 5.1): the detached start, the events tail, re-attach through the lock and
the end events, and the project read off the GUI thread. Never imports Qt or matplotlib."""
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.messages import KrsError, detail, render
from kicad_rf_studio.core.model import spec

END = {0: "G_END_DONE", 2: "G_END_REFUSED", 3: "G_END_BLOCKED", 4: "G_END_NOT_KEPT", 130: "G_END_STOPPED"}
# the CLI's lines that the GUI words its own way, with the same params (design 5.3)
GUI = {"E_LOCKED": "G_LOCKED", "I_RUN_START": "G_RUN_START", "I_WHAT_IF": "G_WHAT_IF", "E_NO_RESULTS": "G_NO_RESULTS",
       "E_RESULTS_STALE": "G_RESULTS_STALE"}


def orchestrator() -> list[str]:
    """The command that runs the CLI as a detached orchestrator (design 5.1): `python -X utf8 -I -m kicad_rf_studio`,
    python being the console python.exe beside a pythonw.exe (the gui-scripts entry on Windows), else this Python."""
    exe = Path(sys.executable)
    python = str(exe.with_name("python.exe")) if exe.name.lower() == "pythonw.exe" else sys.executable
    return [python, "-X", "utf8", "-I", "-m", "kicad_rf_studio"]


def start(prefix: list[str], command: str, project: Path, run_dir: Path) -> subprocess.Popen:
    """Starts `prefix command PROJECT --run-dir RUN_DIR` detached (design 5.1), in `run_dir`, which it makes and which
    is its working folder: stdin the null device, stdout and stderr to run_dir/cli.log, and KiCad's API variables left
    out of its environment. On Windows in a process group of its own with no window, out of this process's job when
    the job allows it; elsewhere in a session of its own."""
    run_dir.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("KICAD_API_SOCKET", "KICAD_API_TOKEN")}
    with open(run_dir / "cli.log", "wb") as log:
        spawn = partial(subprocess.Popen, [*prefix, command, str(project), "--run-dir", str(run_dir)], cwd=run_dir,
                        env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        if sys.platform != "win32":
            return spawn(start_new_session=True)
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:
            return spawn(creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        except PermissionError:  # a job that forbids breakaway
            # ponytail: without breakaway, a job that kills its processes on close still takes the run with it; plan 3
            # checks KiCad's job
            return spawn(creationflags=flags)


def _event(line: bytes) -> dict | None:
    """The event on `line`, None when it does not parse."""
    try:
        return json.loads(line)
    except ValueError:  # json.JSONDecodeError or UnicodeDecodeError
        return None


@dataclass
class Tail:
    """The events appended to the file `path` (events.jsonl), read from `offset` on: the GUI's tail (design 5.1)."""
    path: Path
    offset: int = 0

    def read(self, limit: int = 1 << 20) -> list[dict]:
        """The events of the complete lines from `offset`, which moves past them: at most `limit` bytes read, a partial
        last line held back until its newline arrives and a line that does not parse skipped; [] while there is no
        file."""
        # ponytail: a line longer than limit is never read; events are under 1 KB
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                data = f.read(limit)
        except FileNotFoundError:
            return []
        data = data[:data.rfind(b"\n") + 1]
        self.offset += len(data)
        return [e for e in map(_event, data.splitlines()) if e is not None]


def latest(events: list[dict]) -> list[dict]:
    """`events` in order without each progress event that a later one of the same job replaces (r2 §1: a replay of an
    8 h run is about 40k lines)."""
    last = {e.get("job"): i for i, e in enumerate(events) if e.get("kind") == "progress"}
    return [e for i, e in enumerate(events) if e.get("kind") != "progress" or last[e.get("job")] == i]


def last_event(run_dir: Path) -> dict | None:
    """The event on the last complete line of run_dir/events.jsonl, read from its last 64 KiB: None without the file,
    when that line does not parse, or on an OSError."""
    # ponytail: the last 64 KiB only; a longer last line reads as none
    try:
        with open(run_dir / "events.jsonl", "rb") as f:
            f.seek(max(0, f.seek(0, os.SEEK_END) - (1 << 16)))
            data = f.read()
    except OSError:
        return None
    lines = data[:data.rfind(b"\n") + 1].splitlines()
    return _event(lines[-1]) if lines else None


def ended(project: Path) -> list[tuple[Path, dict]]:
    """The run folders of the project file `project` that ended, each with its end event (A-13), newest first by the
    event's time: the folders runs/<its folder's ascii_name>-* in the data folder whose last event is an end naming
    `project`, a folder that cannot be read skipped."""
    # ponytail: scans every run folder of the project on each read (C-23 keeps them all); an index of run folders if it
    # grows slow
    found = [(d, e) for d in (runs.data_dir() / "runs").glob(f"{runs.ascii_name(project.parent.name)}-*")
             if (e := last_event(d)) and e.get("kind") == "end" and e["params"]["project"] == str(project)]
    return sorted(found, key=lambda pair: pair[1]["t"], reverse=True)


def _model_hash(run_dir: Path) -> str | None:
    """The spec_hash of run_dir/model.json, None when it cannot be read."""
    try:
        return spec.spec_hash(json.loads((run_dir / "model.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def last_cost(project: Path, spec_hash: str | None) -> Path | None:
    """The folder of the newest cost of `project` that ended with exit code 0 on the model of `spec_hash`, as its
    model.json says (one that cannot be read matches nothing); None without one, or without a `spec_hash`."""
    if spec_hash is None:
        return None
    return next((d for d, e in ended(project) if (e["params"]["command"], e["params"]["exit_code"]) == ("cost", 0)
                 and _model_hash(d) == spec_hash), None)


@dataclass
class Opened:
    """A project as open_project reads it: project.json, its model's spec_hash and the chain results while they apply,
    each None when not read; the first refusal met, as (code, params); the last cost of this model (last_cost) and the
    newest run or verify that ended; each None without one."""
    project: dict | None
    spec_hash: str | None
    results: pipeline.ChainResults | None
    problem: tuple[str, dict] | None
    cost: Path | None
    last: Path | None


def open_project(path: Path) -> Opened:
    """The project file `path`, which the caller resolves, read off the GUI thread (design 5.1): pipeline.load, its
    model, the model's spec_hash (None without a spec), results_of and chain_results with errors as lines, the first
    KrsError stopping there as `problem`, any other exception E_INTERNAL; then last_cost and the newest of ended() that
    is a run or a verify. Never raises; starts nothing."""
    project = model_hash = results = problem = None
    try:
        project, board, geom, _ = pipeline.load(path)
        model = pipeline.build_model(project, board, geom)
        model_hash = None if model.spec is None else spec.spec_hash(model.spec)
        pipeline.results_of(project, model)
        results = pipeline.chain_results(path, project, errors_as_lines=True)
    except KrsError as e:
        problem = (e.code, e.params)
    except Exception as e:  # E_INTERNAL, as cli.main reports it
        problem = ("E_INTERNAL", {"detail": detail(e)})
    last = next((d for d, end in ended(path) if end["params"]["command"] in ("run", "verify")), None)
    return Opened(project, model_hash, results, problem, last_cost(path, model_hash), last)


def run_state(run_dir: Path, end: dict | None, holder: dict | None, own: bool,
              returncode: int | None) -> tuple[str, dict]:
    """The state of the run in `run_dir` (design 5.1, 5.3), from its end event `end`, the project lock's `holder`
    (runs.lock_holder), whether this window started its process (`own`) and that process's exit code (None while it
    runs): with an end event, its exit code's end state (END, else G_END_FAILED); else, for this window's process,
    G_RUNNING, then G_END_EXITED; for another's, G_RUNNING while a live lock names `run_dir`, G_END_LOST while a dead
    one does, else G_ENDED. The params are its folder, the exit code (the end's, else `returncode`) and its cli.log."""
    params = {"folder": str(run_dir), "exit_code": end["params"]["exit_code"] if end else returncode,
              "log": str(run_dir / "cli.log")}
    if end:
        state = END.get(params["exit_code"], "G_END_FAILED")
    elif own:
        state = "G_RUNNING" if returncode is None else "G_END_EXITED"
    elif holder and holder["run_dir"] and Path(holder["run_dir"]) == run_dir:
        state = "G_RUNNING" if holder["alive"] else "G_END_LOST"
    else:
        state = "G_ENDED"
    return state, params


def text(code: str, params: dict) -> str:
    """The line the GUI shows for the CLI's `code` with `params`: the GUI's own words (GUI) for the five lines whose
    advice is a terminal's, else the CLI's line."""
    return render(GUI.get(code, code), **params)
