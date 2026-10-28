# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI's Qt-free logic (Stage 2 design 5.1, 5.3): the detached start, Apply's retune run to its end, the events
tail, re-attach through the lock and the end events, the project read off the GUI thread, the retune session (an update
of a project read's chain from the parts' rows), Verify's stale indicator and comparison, New's pad list, and
Advanced's fields of project.json and their edit. Never imports Qt or matplotlib."""
import contextlib
import copy
import json
import math
import operator
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, replace
from functools import partial, reduce
from pathlib import Path

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.values import part_kind, port_value, snap, value_text
from kicad_rf_studio.core.messages import KrsError, detail, render
from kicad_rf_studio.core.model import spec
from kicad_rf_studio.core.project import (BAND_FACTOR, DEFAULT_PRESET, EXPAND_H, GATES, HARMONICS, MARGIN_SCALE, MESH_N,
                                          REACH_H, T_MAX_S, board_file, load_project, parts)

END = {0: "G_END_DONE", 2: "G_END_REFUSED", 3: "G_END_BLOCKED", 4: "G_END_NOT_KEPT", 130: "G_END_STOPPED"}
# the CLI's lines that the GUI words its own way, with the same params (design 5.3)
GUI = {"E_LOCKED": "G_LOCKED", "I_RUN_START": "G_RUN_START", "I_WHAT_IF": "G_WHAT_IF", "E_NO_RESULTS": "G_NO_RESULTS",
       "E_RESULTS_STALE": "G_RESULTS_STALE", "E_PROJECT_EXISTS": "G_PROJECT_EXISTS", "E_OUTPUT_PATH": "G_OUTPUT_PATH",
       "E_NO_STACKUP": "G_NO_STACKUP", "E_STACKUP_LAYERS": "G_STACKUP_LAYERS",
       "W_LID_HEIGHT_MISSING": "G_LID_HEIGHT_MISSING", "I_PART_NO_MODEL": "G_PART_NO_MODEL",
       "W_NO_REFERENCE": "G_NO_REFERENCE", "E_RETUNE_VALUE": "G_RETUNE_VALUE", "E_PART_NO_VALUE": "G_PART_NO_VALUE",
       "E_S2P_MISSING": "G_S2P_MISSING", "E_S2P_UNREADABLE": "G_S2P_UNREADABLE", "E_S2P_BAND": "G_S2P_BAND",
       "W_S2P_FIXTURE": "G_S2P_FIXTURE", "E_VERIFY_VALUE": "G_VERIFY_VALUE", "E_PROJECT_FIELD": "G_PROJECT_FIELD"}


def orchestrator() -> list[str]:
    """The command that runs the CLI as a detached orchestrator (design 5.1): `python -X utf8 -I -m kicad_rf_studio`,
    python being the console python.exe beside a pythonw.exe (the gui-scripts entry on Windows), else this Python."""
    exe = Path(sys.executable)
    python = str(exe.with_name("python.exe")) if exe.name.lower() == "pythonw.exe" else sys.executable
    return [python, "-X", "utf8", "-I", "-m", "kicad_rf_studio"]


def _env() -> dict:
    """This process's environment for the CLI it starts: os.environ without KiCad's API variables."""
    return {k: v for k, v in os.environ.items() if k not in ("KICAD_API_SOCKET", "KICAD_API_TOKEN")}


def start(prefix: list[str], command: str, project: Path, run_dir: Path) -> subprocess.Popen:
    """Starts `prefix command PROJECT --run-dir RUN_DIR` detached (design 5.1), in `run_dir`, which it makes and which
    is its working folder: stdin the null device, stdout and stderr to run_dir/cli.log, and KiCad's API variables left
    out of its environment (_env). On Windows in a process group of its own with no window, out of this process's job
    when the job allows it; elsewhere in a session of its own."""
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "cli.log", "wb") as log:
        spawn = partial(subprocess.Popen, [*prefix, command, str(project), "--run-dir", str(run_dir)], cwd=run_dir,
                        env=_env(), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        if sys.platform != "win32":
            return spawn(start_new_session=True)
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:
            return spawn(creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        except PermissionError:  # a job that forbids breakaway
            # ponytail: without breakaway, a job that kills its processes on close still takes the run with it; plan 3
            # checks KiCad's job
            return spawn(creationflags=flags)


def apply(prefix: list[str], project: Path, assignments: list[str]) -> tuple[int, list[str]]:
    """Apply (design 5.3): `prefix retune PROJECT ASSIGNMENTS...` run to its end, with stdin the null device, no
    window and KiCad's API variables left out of its environment (_env); its exit code and its lines, stdout's then
    stderr's, read as UTF-8 with errors replaced. Raises an OSError when the program cannot start."""
    # ponytail: the pool's one thread waits for retune (2–4 s), so a project read queued meanwhile waits too; a pool of
    # two if that matters
    done = subprocess.run([*prefix, "retune", str(project), *assignments], stdin=subprocess.DEVNULL,
                          capture_output=True, encoding="utf-8", errors="replace", env=_env(),
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    return done.returncode, (done.stdout + done.stderr).splitlines()


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


def verify_lines(project: dict | None) -> list[tuple[str, dict]]:
    """The comparison of the last verify of `project` (design 5.3): the result events of its run folder's events.jsonl
    (verify.run_dir), in order, as (code, params), read with Tail until it returns nothing; [] without a verify and on
    any exception (a folder that cannot be read, a hand-edited block), so that open_project never raises."""
    # ponytail: reads verify's whole events.jsonl on each project read (MBs after a long verify); its result lines are
    # its last, so the last 64 KiB would do, as last_event reads
    try:
        tail, events = Tail(Path(project["verify"]["run_dir"]) / "events.jsonl"), []
        while more := tail.read():
            events += more
        return [(e["code"], e["params"]) for e in events if e.get("kind") == "result"]
    except Exception:
        return []


@dataclass
class Opened:
    """A project as open_project reads it: project.json, its model's spec_hash and the chain results while they apply,
    each None when not read; the first refusal met, as (code, params); the last cost of this model (last_cost) and the
    newest run or verify that ended; each None without one; the board file that project.json names
    (core.project.board_file), None when project.json cannot be read or names no board; the last verify's
    comparison (verify_lines), [] without one; and project.json as load_project reads it (`stored`), unchecked, so that
    Advanced can fix a field the checks refuse, None when it cannot be read."""
    project: dict | None
    spec_hash: str | None
    results: pipeline.ChainResults | None
    problem: tuple[str, dict] | None
    cost: Path | None
    last: Path | None
    board: Path | None = None
    verified: list[tuple[str, dict]] = field(default_factory=list)
    stored: dict | None = None


def open_project(path: Path) -> Opened:
    """The project file `path`, which the caller resolves, read off the GUI thread (design 5.1): pipeline.load, its
    model, the model's spec_hash (None without a spec), results_of and chain_results with errors as lines, the first
    KrsError stopping there as `problem`, any other exception E_INTERNAL; then `stored`, the project read when
    pipeline.load succeeded, else load_project alone, unchecked (a project the checks refuse, or whose board fails to
    load, still reads), and the board file it names, each None when it raises, `stored` kept when only the board file
    does; then last_cost, the newest of ended() that is a run or a verify, and verify_lines. Never raises; starts
    nothing."""
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
    stored = file = None
    # ponytail: a failed read reads project.json a second time, for Advanced and its board's path
    with contextlib.suppress(Exception):  # project.json unreadable, or naming no board
        stored = project if project is not None else load_project(path)
        file = board_file(path, stored)
    last = next((d for d, end in ended(path) if end["params"]["command"] in ("run", "verify")), None)
    return Opened(project, model_hash, results, problem, last_cost(path, model_hash), last, file,
                  verify_lines(project), stored)


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
    """The line the GUI shows for the CLI's `code` with `params`: the GUI's own words (GUI) for the lines whose advice
    is a terminal's, else the CLI's line."""
    return render(GUI.get(code, code), **params)


@dataclass(frozen=True)
class Row:
    """A part port's row in the retune session (design 5.3): its ref, its value as typed, its S2P file ("" for none)
    and that file's connection, "series" or "shunt"."""
    ref: str
    value: str
    s2p: str
    connection: str


SERIES = ("off", "E12", "E24")  # a row's snapping choices (design 5.3)


def default_series(ref: str) -> str:
    """A part's snapping until the user sets it (design 7's owner default): E24 for a C or an L, else off."""
    return "E24" if part_kind(ref) in ("C", "L") else "off"


def snapped(ref: str, text: str, series: str) -> str:
    """The value text `text` of the part `ref` snapped to `series` (design 5.3): the nearest E12 or E24 value (snap)
    written as port_value reads it (value_text). `text` unchanged when series is off, or when port_value gives None, 0
    or a value that is not finite for it (a 400-digit value reads as inf, which snap cannot take)."""
    value = port_value(ref, text)
    if series == "off" or not value or not math.isfinite(value):
        return text
    return value_text(snap(value, series), part_kind(ref))


def _s2p(part: dict, folder: Path) -> tuple[str, str]:
    """The S2P file of the project.json `part`, resolved against `folder` (project.json's) as part_impedances resolves
    it, and its connection; ("", "series") without one."""
    s2p = part["s2p"]
    return (str((folder / s2p["file"]).resolve()), s2p["connection"]) if s2p else ("", "series")


def rows(project: dict, folder: Path, refs: list[str]) -> list[Row]:
    """The rows of the part ports `refs` as `project` stores them (design 5.3): each part's value, S2P file and
    connection (_s2p, against `folder`, project.json's)."""
    by_ref = parts(project)
    return [Row(ref, by_ref[ref]["value"], *_s2p(by_ref[ref], folder)) for ref in refs]


def changed(project: dict, folder: Path, rows: list[Row]) -> list[str]:
    """The REF=RIGHT assignments (pipeline.assign) of the `rows` that differ from `project`, in row order (design 5.3).
    A row with a file is FILE:CONNECTION, its file resolved against `folder` (project.json's), never the working
    directory; it changed when the part has no file, another one or another connection, whatever its value. A row
    without one is its value as typed; it changed when the part has a file or another value text."""
    # ponytail: a value typed as TEXT:series reads as an S2P file, as on the command line; refuse the suffix in the
    # Value cell if it confuses users
    by_ref, assignments = parts(project), []
    for row in rows:
        part = by_ref[row.ref]
        if row.s2p:
            file = str(Path(folder, row.s2p).resolve())
            if (file, row.connection) != _s2p(part, folder):
                assignments.append(f"{row.ref}={file}:{row.connection}")
        elif part["s2p"] or row.value != part["value"]:
            assignments.append(f"{row.ref}={row.value}")
    return assignments


def retuned(path: Path, project: dict, stored: pipeline.ChainResults, rows: list[Row]) -> pipeline.ChainResults:
    """The chain results of the project file `path` (`project`, as read) with its `rows` (design 5.3, 5.4): the rows
    that changed stored by pipeline.assign, then pipeline.chain_results with errors as lines on the layout `stored`
    holds, the CLI's own functions in retune's order, so its numbers and lines are retune's. Any exception on the way
    gives `stored` with no chain and no what-if, its lines that one line: a KrsError's (assign's refusal,
    E_S_SINGULAR), else E_INTERNAL. Writes nothing and never raises, so no stale curve stays on screen."""
    # ponytail: each S2P file is read again on every update, on the GUI thread (about 2, 5 and 19 ms per file of 401,
    # 1601 and 6401 points on lpf915; a file on a slow network share stalls it); cache by (file, mtime_ns), or read on
    # the pool, when several large files pass 50 ms
    try:
        new = pipeline.assign(project, changed(project, path.parent, rows), path.parent)
        return pipeline.chain_results(path, new, errors_as_lines=True, lay=stored.lay)
    except KrsError as e:
        line = (e.code, e.params)
    except Exception as e:  # E_INTERNAL, as cli.main reports it
        line = ("E_INTERNAL", {"detail": detail(e)})
    return replace(stored, chain=None, ideal=None, p_layout=None, what_if=False, lines=[line])


def carried(before: dict | None, after: dict | None, folder: Path, rows: list[Row],
            fresh: list[Row]) -> tuple[list[Row], bool]:
    """A new read's rows `fresh` with the user's `rows` carried over it (design 5.3): each row that differs from
    `before`, the last read's project (changed, against `folder`, project.json's), put back in its part's place when
    `after`, the new read's, holds that part exactly as `before` did (parts); and whether any such row was lost: its
    part changed or gone, or no `after`, unless `after` now stores the row as it is (Apply's re-read). Nothing is
    carried without `before`."""
    # ponytail: a row whose part project.json changed takes the stored row (G_DROPPED); a per-field merge if users lose
    # work that way
    if before is None:
        return fresh, False
    old, new = parts(before), {} if after is None else parts(after)
    kept, lost = {row.ref: row for row in fresh}, False
    for row in rows:
        if not changed(before, folder, [row]):
            continue
        if new.get(row.ref) == old[row.ref]:
            kept[row.ref] = row
        elif row.ref not in new or changed(after, folder, [row]):
            lost = True
    return [kept[row.ref] for row in fresh], lost


def verify_stale(project: dict, rows: list[Row]) -> str | None:
    """The stale indicator of `project` with the retune's `rows` (design 5.3): G_VERIFY_NONE without a verify block it
    can read (none, or a hand edit that is not an object with base_hash and an object of values); G_VERIFY_STALE when
    a run came since (base_hash is not the results' model_hash) or when a row's value reads (port_value) other than
    the one verify ran; else None. A row with an S2P file counts with its part's stored value: Apply keeps that value,
    and verify runs it, not the file (C-38)."""
    v, by_ref = project.get("verify"), parts(project)
    if not (isinstance(v, dict) and "base_hash" in v and isinstance(v.get("values"), dict)):
        return "G_VERIFY_NONE"
    if v["base_hash"] != project["results"]["model_hash"] or any(
            port_value(row.ref, by_ref[row.ref]["value"] if row.s2p else row.value)
            != port_value(row.ref, v["values"].get(row.ref, "")) for row in rows):
        return "G_VERIFY_STALE"
    return None


def pads(board: Path) -> list[str]:
    """New's pad picker (design 5.3): the names REF.PAD of the pads with copper of the board file `board` (load_board,
    Pad.layers), each once, in natural order (U1.9 before U1.10), file order between names that read alike. Raises
    load_board's refusals."""
    # ponytail: every pad with copper, GND's too; new refuses a GND or netless end with its own message
    names = dict.fromkeys(p.name for p in load_board(board).all_pads() if p.layers)
    return sorted(names, key=lambda name: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)])


def message(error: Exception) -> str:
    """The window's line for `error`: a KrsError's in the GUI's words (text), any other E_INTERNAL, as cli.main
    reports it."""
    if isinstance(error, KrsError):
        return text(error.code, error.params)
    return text("E_INTERNAL", {"detail": detail(error)})


@dataclass(frozen=True)
class Field:
    """A leaf of project.json as Advanced shows it (design 5.3): its dotted `name` (region.expand_h,
    chain.series[2].role), its `path` of keys and indices down to it, its `value`, its `default` as JSON text ("" for
    none) and its `unit`, a G_UNIT_ code (None for none)."""
    name: str
    path: tuple
    value: object
    default: str
    unit: str | None


# a field's unit by its last two keys, an index between them written as [], so every part's model has its units
UNITS = {"f0_hz": "G_UNIT_HZ", "t_max_s": "G_UNIT_S", "region.expand_h": "G_UNIT_SUBSTRATE",
         "mesh.reach_h": "G_UNIT_SUBSTRATE", "lid_height_mm": "G_UNIT_MM", "layers[].thickness_mm": "G_UNIT_MM",
         "reference.point": "G_UNIT_MM", "model.esl_h": "G_UNIT_HENRY", "model.esr_ohm": "G_UNIT_OHM",
         "model.cp_f": "G_UNIT_FARAD"}


def _leaves(value, path: tuple):
    """The (path, value) of each leaf under `value`, at `path`, in order: a dict is walked, and so is a non-empty list
    whose items are all dicts; any other value is a leaf."""
    if isinstance(value, dict) or (isinstance(value, list) and value and all(isinstance(x, dict) for x in value)):
        for key, sub in value.items() if isinstance(value, dict) else enumerate(value):
            yield from _leaves(sub, (*path, key))
    else:
        yield path, value


def fields(data: dict) -> list[Field]:
    """Advanced's fields of project.json `data` (design 5.3): every leaf (_leaves) in file order, but those under
    schema, results and verify (records, not settings), each with the default that `new` writes when it has one. The
    preset is read through str(), so a hand-edited one that is not text (a list) cannot raise: unchecked data is what
    Advanced is there to fix."""
    # ponytail: a list of objects can be edited but not grown, and a reference cannot switch between pad and point
    # here; a text editor does both
    defaults = {"harmonics": HARMONICS, "preset": DEFAULT_PRESET, "band_factor": BAND_FACTOR, "t_max_s": T_MAX_S,
                "region.expand_h": EXPAND_H, "region.margin_scale": MARGIN_SCALE,
                "mesh.n": MESH_N.get(str(data.get("preset")), MESH_N[DEFAULT_PRESET]), "mesh.reach_h": REACH_H,
                "lid_height_mm": None, "lid": None, "gates.fit2d_limit": GATES["fit2d_limit"],
                "gates.dt_floor": GATES["dt_floor"], "allow_curve_port": False}
    found = []
    for path, value in _leaves({k: v for k, v in data.items() if k not in ("schema", "results", "verify")}, ()):
        name = "".join(f"[{k}]" if isinstance(k, int) else f".{k}" for k in path)[1:]
        unit = UNITS.get(".".join(re.sub(r"\[\d+\]", "[]", name).split(".")[-2:]))
        found.append(Field(name, path, value, json.dumps(defaults[name]) if name in defaults else "", unit))
    return found


def edited(data: dict, edits: dict[tuple, str]) -> dict:
    """A deep copy of project.json `data` with the leaf at each path of `edits` (Field.path) set to its text read as
    JSON; a text that is not JSON stays the text itself, so draft needs no quotes."""
    new = copy.deepcopy(data)
    for path, typed in edits.items():
        try:
            value = json.loads(typed)
        except ValueError:  # json.JSONDecodeError
            value = typed
        reduce(operator.getitem, path[:-1], new)[path[-1]] = value
    return new
