# SPDX-License-Identifier: GPL-3.0-or-later
"""What `cost`, `run` and `preview` share (spec 6.1): a project read with its board and geometry, its model built
through the mesh gates, the calibration that sizes its jobs, the setup gate on openEMS's setup-only run (timestep
floor, port connectivity, unused primitives) and the cost model (spec 6.4); and `cost` (spec 3.2) and `run` (spec 6.1)
themselves."""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from kicad_rf_studio import runs
from kicad_rf_studio.core.cs2d import ShortError, solve
from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.geometry.sections import cross_section
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.mesh.gates import check_fit2d, dt_floor_reference, fit2d, mesh_with_lint
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model.parts import GRID
from kicad_rf_studio.core.model.ports import ends, nominal_boxes, place
from kicad_rf_studio.core.model.readers import read_log, read_probe, read_run_stats, read_stats
from kicad_rf_studio.core.model.spec import grid_entry, model_spec, spec_hash
from kicad_rf_studio.core.project import (GATES, board_file, board_hash, load_project, mesh_n, read_project,
                                          save_project)
from kicad_rf_studio.stoprule import KEPT, Records, Verdict, residual_db, stop_rule
from kicad_rf_studio.worker import LOG

if TYPE_CHECKING:
    from collections.abc import Callable

    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.kicad.board import Board
    from kicad_rf_studio.core.mesh import Mesh

GEOMETRY_GATES = ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI")  # the geometry's notes that block a run
VERDICTS = {"converged": "I_JOB_CONVERGED", "flat": "W_JOB_FLAT", "t_max": "W_JOB_T_MAX", "diverged": "E_JOB_DIVERGED",
            "growth": "E_JOB_GROWTH", "unclassified": "W_JOB_UNCLASSIFIED", "stopped": "W_JOB_STOPPED"}  # spec 6.3


def project_path(arg: str) -> Path:
    """The project file a command's argument names: a folder stands for its project.json (O-5)."""
    path = Path(arg)
    return path / "project.json" if path.is_dir() else path


def stops(notes: list[tuple[str, dict]]) -> int:
    """The exit code that load()'s `notes` stop a command with: 2 for E_LID_HEIGHT, a refusal; 3 for a geometry gate
    (GEOMETRY_GATES); else 0, go on."""
    codes = {code for code, _ in notes}
    return 2 if "E_LID_HEIGHT" in codes else 3 if codes.intersection(GEOMETRY_GATES) else 0


def load(path: Path) -> tuple[dict, Board, Geometry, list[tuple[str, dict]]]:
    """The project at `path` (read_project), its board and its geometry, and the notes to report, in this order:
    W_BOARD_CHANGED when the board's sha256 is not the one `new` stored (C-30), the board's warnings, the geometry's
    notes (its E_ gate entries too, which stops() reads), then W_OFF_TOP_LAYER for each measured section off the top
    copper (C-9)."""
    project = read_project(path)
    file = board_file(path, project)
    board = load_board(file)
    geom = build_geometry(board, project)
    notes = [("W_BOARD_CHANGED", {"path": str(file)})] if board_hash(file) != project["board"]["sha256"] else []
    top = board.copper_layers[0]  # top to bottom
    notes += [*board.warnings, *geom.notes,
              *(("W_OFF_TOP_LAYER", {"net": s.net, "layer": s.layer}) for s in geom.sections if s.layer != top)]
    return project, board, geom, notes


@dataclass
class Model:
    """A project's model as build_model leaves it: the mesh and the model spec, both None when the edge lint failed;
    the mesh gates that block a run; the timestep floor's reference of the mesh (None without one). The port names, in
    job order, are [q["name"] for q in spec["ports"]]."""
    mesh: Mesh | None
    spec: dict | None
    blocked: list[tuple[str, dict]]
    dt_ref: float | None


def build_model(project: dict, board: Board, geom: Geometry) -> Model:
    """The model of `project` (spec 6.1 step 2, C-42): its port ends; the mesh, finest across their nominal boxes, with
    the edge lint (on E_EDGE_LINT no mesh and no spec, and that gate blocked); fit2d against gates.fit2d_limit (E_FIT2D,
    E_FIT2D_FINE or E_FIT2D_SHORT blocked, the model still built); the timestep floor's reference, from the mesh before
    any port is placed on it; each end placed on the mesh, a grid part's through grid_entry with its entry in
    project.json; then the model spec. Raises the refusals of ends, place and grid_entry; the caller handles stops()
    of load()'s notes first."""
    e = ends(board, project, geom.pieces)
    n = mesh_n(project)
    try:
        mesh = mesh_with_lint(geom, replace(geom.protected, boxes=nominal_boxes(e)), n)
    except KrsError as err:  # E_EDGE_LINT
        return Model(None, None, [(err.code, err.params)], None)
    blocked = []
    try:
        check_fit2d(fit2d(geom, mesh), project["gates"]["fit2d_limit"], n)
    except KrsError as err:  # E_FIT2D_SHORT from fit2d, E_FIT2D or E_FIT2D_FINE from check_fit2d
        blocked.append((err.code, err.params))
    dt_ref = dt_floor_reference(mesh)
    parts = {q["ref"]: q for q in (*project["chain"]["series"], *project["chain"]["shunt"], *project["others"])}
    ports, grid = [], []
    for end in e:
        placed = place(end, mesh, geom.zs)
        if end.role == GRID:
            grid.append(grid_entry(placed, parts[end.name]))
        else:
            ports.append(placed)
    return Model(mesh, model_spec(project, board, geom, mesh, ports, grid), blocked, dt_ref)


def port_gates(ports: list[dict], roots: list[list[int]]) -> list[tuple[str, dict]]:
    """The port connectivity gate (C-15) on the PEC roots of each port's nodes (setup.json's "pec"; -1 for a node no
    PEC edge touches, so two such nodes are no short). A lumped port's four, its reference and signal caps then its
    reference and signal witnesses: E_PORT_OPEN for an end whose cap is not on its witness's piece of copper,
    E_PORT_SHORT when the two witnesses are on one. A CurvePort's two, its reference end then its signal end, have no
    caps: E_PORT_OPEN for an end on no copper, E_PORT_SHORT when both are on one piece."""
    notes = []
    for port, r in zip(ports, roots):
        rc, sc, rw, sw = r if len(r) == 4 else [*r, *r]  # a CurvePort's ends stand for their own caps
        notes += [("E_PORT_OPEN", {"name": port["name"], "end": end})
                  for end, cap, witness in (("reference", rc, rw), ("signal", sc, sw)) if not (cap == witness >= 0)]
        if rw == sw >= 0:
            notes.append(("E_PORT_SHORT", {"name": port["name"]}))
    return notes


def duration(seconds: float) -> str:
    """`seconds` as the cost lines show a time, floored: "N s" under a minute, "N min" under an hour, else
    "H h M min"."""
    s = int(seconds)
    return f"{s} s" if s < 60 else f"{s // 60} min" if s < 3600 else f"{s // 3600} h {s % 3600 // 60} min"


def smallest_cell(mesh: Mesh) -> tuple[float, str, float]:
    """The smallest cell of `mesh`: its size in mm, its axis and its middle along that axis in KiCad's frame (y down).
    The first of the smallest wins, in x, y and z order; the sizes go to 1e-9 mm, so that a tie on the 1e-6 mm grid
    compares equal (float noise put either cell ahead)."""
    steps = {axis: np.round(np.diff(getattr(mesh, axis)), 9) for axis in "xyz"}
    axis = min(steps, key=lambda a: steps[a].min())
    lines, i = getattr(mesh, axis), int(steps[axis].argmin())
    mid = float(lines[i] + lines[i + 1]) / 2
    return float(steps[axis][i]), axis, 0.0 - mid if axis == "y" else mid


def driver(mesh: Mesh, runs: int, parts: int) -> tuple[str, dict]:
    """The main cost (C-36): a cell under d/3, which sets dt (1e-6 mm of slack, so that d/3 on the mesh's 1e-6 mm grid
    is not under it); else more than two runs; else the cell count."""
    size, axis, at = smallest_cell(mesh)
    if size < mesh.d / 3 - 1e-6:
        return "I_COST_DRIVER_CELL", {"size_um": f"{size * 1e3:.1f}", "axis": axis, "at_mm": f"{at:.3f}"}
    if runs > 2:
        return "I_COST_DRIVER_RUNS", {"runs": runs, "parts": parts}
    return "I_COST_DRIVER_CELLS", {"d_mm": f"{mesh.d:.4f}"}


def dt_params(model: Model, floor: float, setup: dict) -> dict:
    """The params of I_COST_DT and E_DT_FLOOR: openEMS's dt in `setup` (setup.json) against `floor` × the model's
    reference, and the edge that sets it, setup's node [n, i, j, k]: its axis n and its point at mesh lines (i, j, k),
    in KiCad's frame."""
    mesh, (n, *ijk) = model.mesh, setup["node"]
    x, y, z = (float(lines[k]) for lines, k in zip((mesh.x, mesh.y, mesh.z), ijk))
    return {"dt": f"{setup['dt']:.4e}", "floor": f"{floor:g}", "ref": f"{model.dt_ref:.4e}", "axis": "xyz"[n],
            "x": f"{x:.3f}", "y": f"{0.0 - y:.3f}", "z": f"{z:.3f}"}


def cost_notes(model: Model, project: dict, setup: dict, threads: int, pool: int,
               per_job_mcs: float) -> list[tuple[str, dict]]:
    """The cost lines (spec 6.4) of a built `model`, from openEMS's setup (setup.json: its dt and the node [n, i, j, k]
    of the smallest timestep) and `pool` jobs at once with `threads` threads each at `per_job_mcs` MC/s a job: the
    cells; the smallest cell; dt against its floor, with the edge that sets it in KiCad's frame; the worst case, every
    run to T_max, in ceil(runs / pool) rounds; the time predicted from the longest stop time of the last run, when it
    has one; the RAM; the main cost (driver)."""
    mesh, ports, dt = model.mesh, model.spec["ports"], setup["dt"]
    nx, ny, nz = len(mesh.x), len(mesh.y), len(mesh.z)
    cells, n_runs = nx * ny * nz, len(ports)

    def time(t_stop: float) -> str:
        return duration(math.ceil(n_runs / pool) * cells * (t_stop / dt) / (per_job_mcs * 1e6))

    size, axis, at = smallest_cell(mesh)
    t_max = project["t_max_s"]
    notes = [
        ("I_COST_CELLS", {"nx": nx, "ny": ny, "nz": nz, "mcells": f"{cells / 1e6:.2f}", "n": mesh_n(project),
                          "d_mm": f"{mesh.d:.4f}"}),
        ("I_COST_SMALLEST", {"size_um": f"{size * 1e3:.1f}", "axis": axis, "at_mm": f"{at:.3f}"}),
        ("I_COST_DT", dt_params(model, project["gates"]["dt_floor"], setup)),
        ("I_COST_TIME", {"time": time(t_max), "runs": n_runs, "t_max_ns": f"{t_max * 1e9:g}", "pool": pool,
                         "threads": threads})]
    t_stops = [j["t_stop"] for j in project.get("results", {}).get("jobs", ()) if j["t_stop"] is not None]
    if t_stops:  # a job with no samples has no stop time
        notes.append(("I_COST_PREDICTED", {"time": time(max(t_stops))}))
    gb = pool * (runs.MB_PER_MCELL * cells / 1e6 + runs.MB_PER_WORKER) / 1024
    return [*notes, ("I_COST_RAM", {"gb": f"{gb:.1f}", "pool": pool}),
            driver(mesh, n_runs, sum(q["part"] for q in ports))]


def prepare(model: Model, emit: Callable[[str, dict], None]) -> tuple[int, int, float]:
    """What the jobs of a built `model` (one with a mesh) run with: (threads, pool, per-job MC/s), from this machine's
    calibration, measured first on a machine that has none (spec 6.4). Calls `emit(code, params)` with
    check_openems()'s warnings, before any worker (C-31), and with W_RAM when one job needs more RAM than is free.
    Raises check_openems()'s refusals and what calibrate raises."""
    for code, params in runs.check_openems():
        emit(code, params)
    entry = runs.ensure_calibrated(runs.load_settings())
    cells = len(model.mesh.x) * len(model.mesh.y) * len(model.mesh.z)
    threads, pool = runs.sizing(entry, cells)
    need = runs.MB_PER_MCELL * cells / 1e6 + runs.MB_PER_WORKER  # one job's RAM in MB, as pool_size counts it
    free = runs.free_ram_mb()
    if need > free:
        emit("W_RAM", {"need_gb": f"{need / 1024:.1f}", "free_gb": f"{free / 1024:.1f}"})
    return threads, pool, entry["aggregate_mcs"] / entry["pool"]


def setup_gate(model: Model, project: dict, run_dir: Path, settings: dict, threads: int) -> tuple[dict, list, list]:
    """openEMS's setup of a built `model` and the gates on it (spec 6.1 step 2): model.json in `run_dir`, one
    setup-only worker in job-0-setup, then (its setup.json, the gates that block a run, the warnings). Blocking:
    E_DT_FLOOR when dt is under gates.dt_floor × the model's reference (C-17), port_gates (C-15), and
    E_UNUSED_PRIMITIVE for each "unused" entry of a port_* or lumped_* property (a port, its probes, a grid part);
    W_UNUSED_PRIMITIVE for any other property, copper (C-16). Raises what check_job raises, KeyboardInterrupt when STOP
    or Ctrl+C stopped the job."""
    runs.write_spec(run_dir, model.spec)
    # T_max 2·t0, the pulse's end: nothing in setup depends on T_max, and openEMS's excitation arrays et and ht hold
    # NrTS lines
    job = runs.write_job(runs.job_dir(run_dir, 0, "setup"), 1, "setup", threads, 2 * model.spec["excitation"]["t0"])
    runs.check_job(job, runs.run_jobs([job], 1, run_dir, settings)[job], "setup", settings)
    setup = json.loads((job / "setup.json").read_text(encoding="utf-8"))
    floor, blocked, warnings = project["gates"]["dt_floor"], [], []
    # ponytail: dt from the setup log (6 digits); openEMS_stats.txt exists only after a run
    if setup["dt"] < floor * model.dt_ref:
        blocked.append(("E_DT_FLOOR", dt_params(model, floor, setup)))
    blocked += port_gates(model.spec["ports"], setup["pec"])
    for kind, prop in setup["unused"]:  # [type, property], ["none", property] or ["outside", property]
        note = {"property": prop, "type": kind}
        if prop.startswith(("port_", "lumped_")):
            blocked.append(("E_UNUSED_PRIMITIVE", note))
        else:
            warnings.append(("W_UNUSED_PRIMITIVE", note))
    return setup, blocked, warnings


def readout_2d(geom: Geometry) -> None:
    """Prints the 2D readout (spec 3.2): each measured section solved on cs2d's own grid without and with the exact
    mask of its own side (none on inner copper), in chain-net order and then by place, or W_2D_SHORT in its place
    where other copper touches the line at its cut."""
    print(render("I_2D_HEADER" if geom.sections else "W_NO_SECTIONS"))
    for s in geom.sections:
        named = {"net": s.net, "layer": s.layer, "width_mm": f"{s.width:.3f}", "length_mm": f"{s.length:.3f}"}
        try:
            bare, coated = [solve(cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), m))
                            for m in ("none", "exact")]
        except ShortError:  # another net's copper (E_SHORT_IN_ROI) or copper with none, which no check reports
            print(render("W_2D_SHORT", **named))
            continue
        print(render("I_2D_SECTION", **named, gap_mm="none" if s.gap is None else f"{s.gap:.3f}", z0=f"{bare.z0:.2f}",
                     eeff=f"{bare.eps_eff:.3f}", z0_mask=f"{coated.z0:.2f}", eeff_mask=f"{coated.eps_eff:.3f}"))


def cost(path: Path) -> int:
    """`cost` on the project at `path` (spec 3.2), returning its exit code (C-22): W_FILLS_AS_SAVED, the 2D readout and
    load()'s notes, then 2 on a refusal among them; a project without ports stops there with W_NO_PORTS. Then the
    model and its mesh gates; with a spec, prepare, the setup gate in a run folder of its own, its lines as events,
    W_GATE_LIMITS when the gate limits are not GATES (C-10), and the cost lines. 3 if any gate blocked (geometry, mesh
    or setup), else 0."""
    project, board, geom, notes = load(path)
    print(render("W_FILLS_AS_SAVED"))
    readout_2d(geom)
    for code, params in notes:
        print(render(code, **params))
    if stops(notes) == 2:
        return 2
    if not project["ports"]:
        print(render("W_NO_PORTS"))
        return stops(notes)
    model = build_model(project, board, geom)
    for code, params in model.blocked:
        print(render(code, **params))
    if model.spec is None:  # E_EDGE_LINT left no mesh to set up
        return 3
    threads, pool, per_job_mcs = prepare(model, lambda code, params: print(render(code, **params)))
    # absolute: `cost .` names the run folder after the project's folder too
    run_dir, settings = runs.run_dir_for(path.absolute().parent.name), runs.load_settings()
    setup, blocked, warnings = setup_gate(model, project, run_dir, settings, threads)
    for code, params in blocked:
        runs.emit(run_dir, "verdict", code, params, job=0)
    for code, params in warnings:
        runs.emit(run_dir, "message", code, params, job=0)
    if (gates := project["gates"]) != GATES:  # C-10
        runs.emit(run_dir, "message", "W_GATE_LIMITS",
                  {"fit2d_limit": f"{gates['fit2d_limit']:g}", "dt_floor": f"{gates['dt_floor']:g}"})
    for code, params in cost_notes(model, project, setup, threads, pool, per_job_mcs):
        runs.emit(run_dir, "cost", code, params)
    return 3 if stops(notes) or model.blocked or blocked else 0


def records(job: Path, ports: int, dt: float) -> Records:
    """The records of the job in folder `job` as they stand: the probe files of its `ports` ports cut to the shortest,
    and the energy of openEMS_run_stats.txt at te = timestep × `dt`. A missing file reads as empty: setup is still
    running, or the worker died."""
    def text(name: str) -> str:
        try:
            return (job / name).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    probes = [[read_probe(text(f"port_{q}t_{k}")) for k in range(1, ports + 1)] for q in "ui"]
    n = min(len(t) for files in probes for t, _ in files)
    (t_u, u), (t_i, i) = ((files[0][0][:n], np.array([v[:n] for _, v in files])) for files in probes)
    steps, _, e = read_run_stats(text("openEMS_run_stats.txt"))
    return Records(t_u, u, t_i, i, steps * dt, e)


def last_sample(rec: Records) -> tuple[float | None, float | None]:
    """The time and the port residual (dB) of the last sample of `rec`; None and None without samples."""
    return (float(rec.t_u[-1]), float(residual_db(rec)[-1])) if len(rec.t_u) else (None, None)


def classify_job(job: Path, result: dict, live: Verdict | None, rec: Records, k: int, preset: str,
                 exc: dict) -> tuple[str, Verdict | None]:
    """The verdict on the job in `job`, port `k`, once it exited (spec 6.3), the first match winning: a non-finite
    sample in its final records `rec`, diverged; a non-zero exit or no waves.npz, stopped when the run was stopped, else
    unclassified; the `live` verdict; the stop rule on `rec`; stopped; t_max when the log's iterations are its NrTS;
    else unclassified, never silently done. `result` is the job's entry in what run_jobs returns. Returns the verdict
    and the Verdict that gives its time and residual, None for t_max, stopped and unclassified."""
    bad = ((rec.t_u, ~np.isfinite(rec.u).all(0)), (rec.t_i, ~np.isfinite(rec.i).all(0)), (rec.te, ~np.isfinite(rec.e)))
    t_bad = min(np.min(t, initial=np.inf, where=b) for t, b in bad)  # as stop_rule finds it
    if t_bad < np.inf:
        return "diverged", Verdict("diverged", float(t_bad), math.nan)
    if result["code"] != 0 or not (job / "waves.npz").is_file():
        return ("stopped" if result["stopped"] else "unclassified"), None
    if verdict := live or stop_rule(rec, k - 1, preset, exc):
        return verdict.kind, verdict
    if result["stopped"]:
        return "stopped", None
    log = read_log((job / LOG).read_text(encoding="utf-8"))
    return ("t_max" if log["nrts"] is not None and log["iterations"] == log["nrts"] else "unclassified"), None


def run(path: Path) -> int:
    """`run` on the project at `path` (spec 6.1, C-42), returning its exit code (C-22). Raises E_NO_PORTS for a project
    without ports, and E_LOCKED while another run holds the project lock. Then, under the lock, in a fresh run folder
    whose events.jsonl gets every line, with any KrsError a message event and exit 2: W_FILLS_AS_SAVED and load()'s
    notes, stopping with stops(); the model, 3 when a mesh gate blocks; prepare and the setup gate, 3 when it blocks,
    else I_GATES_PASSED and the cost lines; then one job per port under the stop rule, each job's verdict
    (classify_job), the results in project.json, the calibration's speed refreshed and I_RESULTS: 0 when every job kept
    S, else 4 (C-29). W_GATE_LIMITS follows the gate lines and each verdict when the gate limits are not GATES (C-10).
    STOP or Ctrl+C before the jobs start propagates as KeyboardInterrupt (exit 130, results untouched); once they run,
    it stops them, and their results say so."""
    if not read_project(path)["ports"]:
        raise KrsError("E_NO_PORTS")
    run_dir = runs.run_dir_for(path.absolute().parent.name)  # absolute: as in cost
    with runs.project_lock(path, run_dir):
        run_dir.mkdir(parents=True)
        try:
            return _run(path, run_dir)
        except KrsError as err:
            runs.emit(run_dir, "message", err.code, err.params)
            return 2


def _run(path: Path, run_dir: Path) -> int:
    """run() under the lock, with `run_dir` made."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    project, board, geom, notes = load(path)
    gates, preset = project["gates"], project["preset"]

    def limits() -> None:  # C-10
        if gates != GATES:
            emit("message", "W_GATE_LIMITS",
                 {"fit2d_limit": f"{gates['fit2d_limit']:g}", "dt_floor": f"{gates['dt_floor']:g}"})

    for code, params in [("W_FILLS_AS_SAVED", {}), *notes]:
        emit("message", code, params)
    if stop := stops(notes):
        return stop
    model = build_model(project, board, geom)
    if model.blocked:
        for code, params in model.blocked:
            emit("verdict", code, params)
        limits()
        return 3
    threads, pool, per_job_mcs = prepare(model, partial(emit, "message"))
    settings = runs.load_settings()
    setup, blocked, warnings = setup_gate(model, project, run_dir, settings, threads)
    for code, params in blocked:
        emit("verdict", code, params, 0)
    for code, params in warnings:
        emit("message", code, params, 0)
    if blocked:
        limits()
        return 3
    emit("message", "I_GATES_PASSED", {"dt": f"{setup['dt']:.4e}"})
    limits()
    for code, params in cost_notes(model, project, setup, threads, pool, per_job_mcs):
        emit("cost", code, params)

    names, exc, dt = [q["name"] for q in model.spec["ports"]], model.spec["excitation"], setup["dt"]
    jobs = [runs.write_job(runs.job_dir(run_dir, k, name), k, "run", threads, exc["t_max"])
            for k, name in enumerate(names, 1)]
    live, rows = {}, {}  # each job's live verdict, and the energy rows its last I_PROGRESS saw

    def watch(job: Path) -> bool:
        """Whether the stop rule has a verdict on `job`; I_PROGRESS when its energy log has a new row."""
        k = jobs.index(job) + 1
        rec = records(job, len(names), dt)
        live[job] = stop_rule(rec, k - 1, preset, exc)
        if len(rec.e) > rows.get(job, 0) and len(rec.t_u):
            rows[job] = len(rec.e)
            t, r = last_sample(rec)
            speed = read_run_stats((job / "openEMS_run_stats.txt").read_text(encoding="utf-8"))[1][-1]
            emit("progress", "I_PROGRESS", {"port": names[k - 1], "t_ns": f"{t * 1e9:.2f}", "residual_db": f"{r:.1f}",
                                            "speed_mcs": f"{speed / 1e6:.1f}"}, k)
        return live[job] is not None

    emit("message", "I_RUN_START", {"runs": len(jobs), "pool": min(pool, len(jobs)), "folder": str(run_dir)})
    start = time.monotonic()
    out = runs.run_jobs(jobs, pool, run_dir, settings, watch)
    wall_s = time.monotonic() - start

    done, work = [], 0  # each job's results, and Σ cells·iterations
    for k, job in enumerate(jobs, 1):
        rec = records(job, len(names), dt)
        kind, verdict = classify_job(job, out[job], live.get(job), rec, k, preset, exc)
        t_stop, r_last = last_sample(rec)
        t, r = (verdict.t, verdict.residual_db) if verdict else (t_stop, r_last)
        r = r if r is not None and math.isfinite(r) else None  # a diverged job's NaN is no residual, nor in JSON
        emit("verdict", VERDICTS[kind], {"port": names[k - 1], "t_ns": None if t is None else f"{t * 1e9:.2f}",
                                         "residual_db": None if r is None else f"{r:.1f}", "log": str(job / LOG)}, k)
        limits()
        waves = f"{job.name}/waves.npz"
        done.append({"port": names[k - 1], "verdict": kind, "t_cut": verdict.t if verdict else None, "t_stop": t_stop,
                     "residual_db": r, "waves": waves if (run_dir / waves).is_file() else None})
        if (stats := job / "openEMS_stats.txt").is_file():  # a killed or crashed job has none
            s = read_stats(stats.read_text(encoding="utf-8"))
            work += s["cells"] * s["iterations"]

    data = load_project(path)  # as it is now: only results is replaced
    data["results"] = {"model_hash": spec_hash(model.spec), "run_dir": str(run_dir), "gates": gates, "dt": dt,
                       "c_box": setup["c_box"], "wall_s": wall_s, "jobs": done}
    save_project(path, data)
    # ponytail: this run's own concurrency sets the speed, so fewer jobs at once than the calibration's pool (fewer
    # ports, or the RAM) under-reports it; scale by the jobs that ran at once if cost's predictions drift
    if work:  # a run whose every job died measured nothing
        settings = runs.load_settings()
        settings["machines"][runs.machine_key()]["aggregate_mcs"] = work / wall_s / 1e6
        runs.save_settings(settings)
    kept = sum(j["verdict"] in KEPT for j in done)
    emit("result", "I_RESULTS", {"kept": kept, "runs": len(jobs), "wall": duration(wall_s), "path": str(path)})
    return 0 if kept == len(jobs) else 4
