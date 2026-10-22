# SPDX-License-Identifier: GPL-3.0-or-later
"""What `cost`, `run`, `retune`, `verify` and `preview` share (spec 6.1): a project read with its board and geometry,
its model built through the mesh gates, the calibration that sizes its jobs, the setup gate on openEMS's setup-only run
(timestep floor, port connectivity, unused primitives), the cost model (spec 6.4), the job phase and the outputs of a
run's results (spec 7.3); and `cost` (spec 3.2), `run` (spec 6.1), `retune` (spec 3.2, 7.2, 7.8), `verify` (spec 7.6)
and `preview` (C-34) themselves."""
from __future__ import annotations

import copy
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
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
from kicad_rf_studio.core.kicad.values import part_kind, port_value
from kicad_rf_studio.core.mesh.gates import check_fit2d, dt_floor_reference, fit2d, mesh_with_lint
from kicad_rf_studio.core.messages import KrsError, reason, render
from kicad_rf_studio.core.model.parts import CURVE_PORT, GRID, PORT
from kicad_rf_studio.core.model.ports import ends, nominal_boxes, place
from kicad_rf_studio.core.model.readers import read_log, read_probe, read_run_stats, read_stats
from kicad_rf_studio.core.model.spec import grid_entry, model_spec, spec_hash, verify_spec
from kicad_rf_studio.core.post.chain import ideal_schematic, loads, part_impedances, terminate, z_part
from kicad_rf_studio.core.post.checks import compare, indicator_lines, loss_budget, loss_expected
from kicad_rf_studio.core.post.outputs import (LIMITS, OUTPUTS, VERIFY_OUTPUT, grid_lines, marker_lines, port_map,
                                               summary_csv, summary_png, touchstone, write)
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import (GATES, board_file, board_hash, load_project, mesh_n, parts, read_project,
                                          relative_path, save_project)
from kicad_rf_studio.stoprule import KEPT, PRESETS, Records, Verdict, residual_db, stop_rule
from kicad_rf_studio.worker import LOG

if TYPE_CHECKING:
    from collections.abc import Callable

    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.kicad.board import Board
    from kicad_rf_studio.core.mesh import Mesh
    from kicad_rf_studio.core.post.waves import Layout

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
    by_ref = parts(project)
    ports, grid = [], []
    for end in e:
        placed = place(end, mesh, geom.zs)
        if end.role == GRID:
            grid.append(grid_entry(placed, by_ref[end.name]))
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
    run to T_max, in ceil(runs / pool) rounds; the time predicted from the longest stop time of the last run's jobs
    that kept S, when that run was of this model; the RAM; the main cost (driver)."""
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
    results = project.get("results", {})  # a job with no samples has no stop time, and a stopped one a wrong one
    t_stops = [j["t_stop"] for j in results.get("jobs", ()) if j["verdict"] in KEPT and j["t_stop"] is not None]
    if t_stops and results.get("model_hash") == spec_hash(model.spec):  # another model stops elsewhere
        notes.append(("I_COST_PREDICTED", {"time": time(max(t_stops))}))
    gb = pool * (runs.MB_PER_MCELL * cells / 1e6 + runs.MB_PER_WORKER) / 1024
    return [*notes, ("I_COST_RAM", {"gb": f"{gb:.1f}", "pool": pool}),
            driver(mesh, n_runs, sum(q["part"] for q in ports))]


def prepare(model: Model, emit: Callable[[str, dict], None]) -> tuple[int, int, float]:
    """What the jobs of a built `model` (one with a mesh) run with: (threads, pool, per-job MC/s), from this machine's
    calibration, measured first on a machine that has none (spec 6.4), the pool no larger than the number of runs, so
    that the cost lines count only jobs that run at once. Calls `emit(code, params)` with check_openems()'s warnings,
    before any worker (C-31), and with W_RAM when one job needs more RAM than is free. Raises check_openems()'s
    refusals and what calibrate raises."""
    for code, params in runs.check_openems():
        emit(code, params)
    entry = runs.ensure_calibrated(runs.load_settings())
    cells = len(model.mesh.x) * len(model.mesh.y) * len(model.mesh.z)
    threads, pool = runs.sizing(entry, cells)
    need = runs.MB_PER_MCELL * cells / 1e6 + runs.MB_PER_WORKER  # one job's RAM in MB, as pool_size counts it
    free = runs.free_ram_mb()
    if need > free:
        emit("W_RAM", {"need_gb": f"{need / 1024:.1f}", "free_gb": f"{free / 1024:.1f}"})
    return threads, min(pool, len(model.spec["ports"])), entry["aggregate_mcs"] / entry["pool"]


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


def expected_loss(geom: Geometry, f0: float) -> float:
    """loss_expected at `f0` (C-25) of the measured sections of `geom`: each with its εeff with mask (the exact one),
    as the 2D readout prints it, the εr and tanδ (None for 0) of the dielectric next to its copper in geom.zs, the one
    below, else the one above, and its length. A section that other copper touches at its cut (ShortError) adds
    nothing."""
    # ponytail: straight, axis-aligned sections only, a lower bound; bends, pads and vias add nothing
    terms = []
    for s in geom.sections:
        try:
            eeff = solve(cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), "exact")).eps_eff
        except ShortError:
            continue
        i = next(k for k, slab in enumerate(geom.zs) if slab.copper == s.layer)
        d = geom.zs[i - 1] if i and geom.zs[i - 1].kind == "dielectric" else geom.zs[i + 1]
        terms.append((d.eps_r, eeff, d.tan_d or 0.0, s.length))
    return loss_expected(terms, f0)


def gate_lines(gates: dict) -> list[tuple[str, dict]]:
    """W_GATE_LIMITS when the gate limits `gates` are not GATES (C-10), else none."""
    if gates == GATES:
        return []
    return [("W_GATE_LIMITS", {"fit2d_limit": f"{gates['fit2d_limit']:g}", "dt_floor": f"{gates['dt_floor']:g}"})]


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
    for code, params in gate_lines(project["gates"]):
        runs.emit(run_dir, "message", code, params)
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


def command_line(*args: str) -> str:
    """The command `args` as a user types it again in this OS's shell, a path with spaces still one argument."""
    return subprocess.list2cmdline(args) if runs.WINDOWS else shlex.join(args)


def _split(lay: Layout) -> tuple[list[int], list[str]]:
    """The external ports of `lay`, by index, and its part ports, by name."""
    return [k for k, q in enumerate(lay.ports) if not q["part"]], [q["name"] for q in lay.ports if q["part"]]


def _save(path: Path, data: dict, command: str) -> None:
    """save_project(path, data) as run, retune and verify store their results: an OSError (project.json held or
    read-only) raises E_RESULTS_WRITE for `path`, with `command` to run again."""
    try:
        save_project(path, data)
    except OSError as err:
        raise KrsError("E_RESULTS_WRITE", path=str(path), reason=reason(err, "cannot be written"),
                       command=command) from None


def write_outputs(path: Path, project: dict, command: str, *,
                  errors_as_lines: bool = False) -> list[tuple[str, dict]]:
    """The outputs of the run in `project`'s results (spec 3.2, 7.3, C-26..C-32), the step `run` and `retune` share:
    layout.s{N}p; chain.s{P}p when part ports are closed; with P = 2 summary.csv and summary.png, else W_NOT_TWO_PORT
    (C-31); all written to results/ beside `path` (write, with `command` as E_RESULTS_WRITE's advice). Returns the
    lines to report: I_BASIS with each flagged job, gate_lines, the part notes, the marker and indicator lines, then
    I_OUTPUTS and LIMITS. A part's refusal (E_PART_NO_VALUE, E_S2P_*, E_CBOX) and write's E_RESULTS_WRITE are raised,
    or, with `errors_as_lines`, each becomes a line: a part's refusal in the place of the chain's lines and files, so
    that the layout N-port is still written (C-26); E_RESULTS_WRITE in the place of I_OUTPUTS, so that the lines
    already computed and LIMITS are still reported (spec 7.5). Raises layout's refusals and E_S_SINGULAR."""
    results = project["results"]
    lay = layout(project, results)
    ext, refs = _split(lay)
    folder, n, p = path.parent / "results", len(lay.ports), len(ext)
    files = {f"layout.s{n}p": touchstone(lay.s, lay.f, [q["name"] for q in lay.ports],
                                         port_map(project, results, lay, range(n)))}
    count = Counter(job["verdict"] for job in results["jobs"])
    end = {"flat": "t_cut", "t_max": "t_stop"}  # where a flagged job's S ends: its cut, or its last sample
    lines = [("I_BASIS", {"run_dir": results["run_dir"], "preset": results["preset"], "converged": count["converged"],
                          "flat": count["flat"], "t_max": count["t_max"]})]
    lines += [(VERDICTS[job["verdict"]], {"port": job["port"], "t_ns": f"{job[end[job['verdict']]] * 1e9:.2f}",
                                          "residual_db": f"{job['residual_db']:.1f}"})
              for job in results["jobs"] if job["verdict"] in end]
    lines += gate_lines(results["gates"])
    try:
        zparts, notes = part_impedances(project, path.parent, refs, lay.f)
        lines += notes
        zk = loads(zparts, refs, results["c_box"], lay.f)
    except KrsError as err:
        if not errors_as_lines:
            raise
        lines.append((err.code, err.params))
    else:
        chain = terminate(lay.s, ext, zk, lay.f)
        if refs:
            files[f"chain.s{p}p"] = touchstone(chain, lay.f, [lay.ports[k]["name"] for k in ext],
                                               port_map(project, results, lay, ext))
        if p == 2:
            ideal = ideal_schematic(project, zparts, lay.f) if refs else None
            p_layout = loss_budget(lay.s, ext, zk)
            lines += [*marker_lines(lay, chain, ideal),
                      *indicator_lines(lay.f, lay.a_db, lay.s, p_layout, results["loss_expected"])]
            files["summary.csv"] = summary_csv(lay, chain, ideal, p_layout, results["loss_expected"])
            files["summary.png"] = summary_png(lay, chain, ideal, path.absolute().parent.name)  # `run .` too
        else:
            lines += [*indicator_lines(lay.f, lay.a_db, lay.s, None, results["loss_expected"]),
                      ("W_NOT_TWO_PORT", {"ports": p})]
    try:
        write(folder, files, OUTPUTS, command)
    except KrsError as err:  # E_RESULTS_WRITE: a file held open, say
        if not errors_as_lines:
            raise
        lines.append((err.code, err.params))
    else:
        lines.append(("I_OUTPUTS", {"files": ", ".join(sorted(files)), "folder": str(folder)}))
    return [*lines, *((code, {}) for code in LIMITS)]


def run(path: Path) -> int:
    """`run` on the project at `path` (spec 6.1, C-42), returning its exit code (C-22). Raises E_NO_PORTS for a project
    without ports, and E_LOCKED while another run holds the project lock. Then, under the lock, in a fresh run folder
    whose events.jsonl gets every line, with any KrsError a message event and exit 2: W_FILLS_AS_SAVED and load()'s
    notes, stopping with stops(); the model, 3 when a mesh gate blocks; the expected loss (expected_loss); prepare and
    the setup gate, 3 when it blocks, else I_GATES_PASSED and the cost lines; then one job per port under the stop rule,
    each job's verdict (classify_job) and the calibration's speed refreshed. When every job kept S, the results in
    project.json, with the preset and the expected loss (E_RESULTS_WRITE advising `run` when project.json cannot be
    replaced), I_RESULTS, then write_outputs' lines as result events, an E_ line (a part's refusal, the layout N-port
    still written; E_RESULTS_WRITE for a file held open, the lines and LIMITS still printed) as a message event, and
    0, or 2 after an E_ line (C-26); else W_RUN_NOT_KEPT and 4, the previous results and results/ left as they were
    (C-24, C-29). W_GATE_LIMITS follows the gate lines and each verdict when the gate limits are not GATES (C-10). STOP
    or Ctrl+C before the jobs start propagates as KeyboardInterrupt (exit 130, results untouched); once they run, it
    stops them, and their verdicts say so."""
    if not read_project(path)["ports"]:
        raise KrsError("E_NO_PORTS")
    return _locked(path, _run)


def _locked(path: Path, body: Callable[[Path, Path], int]) -> int:
    """The exit code of `body(path, run_dir)` under the project lock, in a fresh run folder `run_dir` whose
    events.jsonl gets any KrsError as a message event, then exit 2: the lock contract that run and verify share."""
    run_dir = runs.run_dir_for(path.absolute().parent.name)  # absolute: as in cost
    with runs.project_lock(path, run_dir):
        run_dir.mkdir(parents=True)
        try:
            return body(path, run_dir)
        except KrsError as err:
            runs.emit(run_dir, "message", err.code, err.params)
            return 2


def _run(path: Path, run_dir: Path) -> int:
    """run() under the lock, with `run_dir` made."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    if isinstance(built := _model_phase(path, emit), int):
        return built
    project, geom, model = built
    gates, preset = project["gates"], project["preset"]
    loss = expected_loss(geom, project["f0_hz"])  # before prepare: an error here costs no job
    if (out := simulate(model, project, run_dir)) is None:
        return 3
    done, setup, wall_s = out
    kept = sum(j["verdict"] in KEPT for j in done)
    if kept < len(done):  # C-24: the previous results stay
        emit("result", "W_RUN_NOT_KEPT", {"kept": kept, "runs": len(done), "wall": duration(wall_s),
                                          "folder": str(run_dir)})
        return 4
    data = load_project(path)  # as it is now: only results is replaced
    data["results"] = {"model_hash": spec_hash(model.spec), "run_dir": str(run_dir), "gates": gates, "preset": preset,
                       "loss_expected": loss, "dt": setup["dt"], "c_box": setup["c_box"], "wall_s": wall_s,
                       "jobs": done}
    _save(path, data, command_line("kicad-rf-studio", "run", str(path)))
    emit("result", "I_RESULTS", {"kept": kept, "runs": len(done), "wall": duration(wall_s), "path": str(path)})
    lines = write_outputs(path, data, command_line("kicad-rf-studio", "retune", str(path)), errors_as_lines=True)
    for code, params in lines:
        emit("message" if code.startswith("E_") else "result", code, params)
    return 2 if any(code.startswith("E_") for code, _ in lines) else 0


def _model_phase(path: Path, emit: Callable[..., None]) -> tuple[dict, Geometry, Model] | int:
    """The model phase that run and verify share under the lock (spec 6.1, C-42): the project at `path`, its geometry
    and its model, with W_FILLS_AS_SAVED and load()'s notes as message events through `emit` (runs.emit bound to the
    run folder). Instead the exit code where it stops: stops()'s, or 3 when a mesh gate blocks, its gates as verdict
    events followed by gate_lines (C-10)."""
    project, board, geom, notes = load(path)
    for code, params in [("W_FILLS_AS_SAVED", {}), *notes]:
        emit("message", code, params)
    if stop := stops(notes):
        return stop
    model = build_model(project, board, geom)
    if model.blocked:
        for code, params in model.blocked:
            emit("verdict", code, params)
        for code, params in gate_lines(project["gates"]):  # C-10
            emit("message", code, params)
        return 3
    return project, geom, model


def simulate(model: Model, project: dict, run_dir: Path) -> tuple[list[dict], dict, float] | None:
    """The job phase of a built `model` (one with a spec) in `run_dir`, which run and verify share (spec 6.1): prepare
    and the setup gate, its blocking gates as verdict events and its warnings as message events, then gate_lines and
    None when it blocks; else I_GATES_PASSED, gate_lines and the cost lines, then one job per port of the model under
    the stop rule at the project's preset, each job's verdict (classify_job) followed by gate_lines, and the
    calibration's speed refreshed. Returns (the jobs as project.json's results records them, setup.json, the job
    phase's wall time in s). STOP or Ctrl+C before the jobs start propagates as KeyboardInterrupt; once they run, it
    stops them, and their verdicts say so."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    gates, preset = project["gates"], project["preset"]
    threads, pool, per_job_mcs = prepare(model, partial(emit, "message"))
    settings = runs.load_settings()
    setup, blocked, warnings = setup_gate(model, project, run_dir, settings, threads)
    for code, params in blocked:
        emit("verdict", code, params, 0)
    for code, params in warnings:
        emit("message", code, params, 0)
    if blocked:
        for code, params in gate_lines(gates):  # C-10
            emit("message", code, params)
        return None
    emit("message", "I_GATES_PASSED", {"dt": f"{setup['dt']:.4e}"})
    for code, params in gate_lines(gates):
        emit("message", code, params)
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

    emit("message", "I_RUN_START", {"runs": len(jobs), "pool": pool, "folder": str(run_dir)})
    start = time.monotonic()
    out = runs.run_jobs(jobs, pool, run_dir, settings, watch)
    wall_s = time.monotonic() - start

    done, speeds = [], []  # each job's results, and openEMS's speed (cells/s) of each job that wrote its stats
    for k, job in enumerate(jobs, 1):
        rec = records(job, len(names), dt)
        kind, verdict = classify_job(job, out[job], live.get(job), rec, k, preset, exc)
        t_stop, r_last = last_sample(rec)
        t, r = (verdict.t, verdict.residual_db) if verdict else (t_stop, r_last)
        r = r if r is not None and math.isfinite(r) else None  # a diverged job's NaN is no residual, nor in JSON
        emit("verdict", VERDICTS[kind], {"port": names[k - 1], "t_ns": None if t is None else f"{t * 1e9:.2f}",
                                         "residual_db": None if r is None else f"{r:.1f}", "log": str(job / LOG)}, k)
        for code, params in gate_lines(gates):
            emit("message", code, params)
        waves = f"{job.name}/waves.npz"
        done.append({"port": names[k - 1], "verdict": kind, "t_cut": verdict.t if verdict else None, "t_stop": t_stop,
                     "residual_db": r, "waves": waves if (run_dir / waves).is_file() else None})
        if (stats := job / "openEMS_stats.txt").is_file():  # a killed or crashed job has none
            speeds.append(read_stats(stats.read_text(encoding="utf-8"))["speed"])

    if speeds:  # spec 6.4: refreshed from the run's Speed lines; a run whose every job died measured nothing
        settings = runs.load_settings()
        entry = settings["machines"][runs.machine_key()]
        entry["aggregate_mcs"] = sum(speeds) / len(speeds) * entry["pool"] / 1e6  # prepare's / pool: the per-job speed
        runs.save_settings(settings)
    return done, setup, wall_s


def results_of(project: dict, model: Model) -> dict:
    """The results in `project` when they are the last run's of `model` (spec 7.8, C-22, C-23): E_NO_RESULTS without
    any; E_RESULTS_STALE when the model has no spec (E_EDGE_LINT), its spec_hash is not the one the run recorded, or
    the run recorded no loss_expected (a run before this version)."""
    # ponytail: rebuilds the model (1.2–3.2 s on lpf915) to compare hashes; Stage 2 may cache it
    if "results" not in project:
        raise KrsError("E_NO_RESULTS")
    results = project["results"]
    if model.spec is None or spec_hash(model.spec) != results.get("model_hash") or "loss_expected" not in results:
        raise KrsError("E_RESULTS_STALE")
    return results


def assign(project: dict, assignments: list[str], folder: Path) -> dict:
    """A deep copy of `project` with each assignment "REF=RIGHT" stored, split at the first "=" (C-17, C-18): a RIGHT
    FILE:series or FILE:shunt sets the part's s2p to FILE, as relative_path stores it against `folder` (a relative
    FILE is read from the working directory, as `new` reads BOARD), its value and model kept; any other RIGHT is
    stored verbatim as its value, its s2p None, when port_value reads it (so a C of 0 is refused). Refusals, the first
    in argument order: E_RETUNE_ARG (no "="), E_RETUNE_TWICE, E_RETUNE_UNKNOWN (no such part; it names the retunable
    ones, in project order), E_RETUNE_ROLE (copper, open or grid), E_RETUNE_VALUE."""
    # ponytail: a file on another drive is stored absolute without a warning; a moved project then meets E_S2P_MISSING
    new = copy.deepcopy(project)
    by_ref, seen = parts(new), set()
    for arg in assignments:
        ref, eq, right = arg.partition("=")
        if not eq:
            raise KrsError("E_RETUNE_ARG", arg=arg)
        if ref in seen:
            raise KrsError("E_RETUNE_TWICE", ref=ref)
        seen.add(ref)
        if ref not in by_ref:
            raise KrsError("E_RETUNE_UNKNOWN", ref=ref,
                           refs=", ".join(r for r, q in by_ref.items() if q["role"] in (PORT, CURVE_PORT)))
        part = by_ref[ref]
        if part["role"] not in (PORT, CURVE_PORT):
            raise KrsError("E_RETUNE_ROLE", ref=ref, role=part["role"])
        file, _, connection = right.rpartition(":")  # the last ":", so a drive's colon stays in the file
        if file and connection in ("series", "shunt"):
            part["s2p"] = {"file": relative_path(file, folder)[0], "connection": connection}
        elif port_value(ref, right) is None:
            raise KrsError("E_RETUNE_VALUE", ref=ref, value=right)
        else:
            part["value"], part["s2p"] = right, None
    return new


def retune(path: Path, assignments: list[str], emit: Callable[[str, dict], None] | None = None) -> int:
    """`retune` on the project at `path` (spec 3.2, 7.2, C-17..C-23), returning its exit code. A project that cannot
    be read refuses first, as in run. Then, under the project lock: the project read; E_RETUNE_NO_PARTS for
    assignments to a project without part ports (a single trace, C-21); the `assignments` stored in a copy (assign);
    its model built and results_of; write_outputs, whose E_RESULTS_WRITE advises this command with its assignments;
    then project.json saved, only when there were assignments (none: the outputs alone, C-19), with the same
    E_RESULTS_WRITE when it cannot be replaced. Then `emit(code, params)` for each line, which prints it by default
    (Stage 2's GUI passes its own, C-4), and 0. It starts no worker and needs no openEMS; any refusal but that last
    one raises before anything is stored (C-20)."""
    read_project(path)  # before the lock, as in run: its file needs the project's folder, which a typo lacks
    # ponytail: results/ stands in for the lock's run folder, so E_LOCKED names results/ while a retune holds the lock
    with runs.project_lock(path, path.parent / "results"):
        project = read_project(path)  # again under the lock: a run may have saved new results since
        if assignments and not any(q["role"] in (PORT, CURVE_PORT) for q in parts(project).values()):
            raise KrsError("E_RETUNE_NO_PARTS")
        new = assign(project, assignments, path.parent)
        # ponytail: load()'s notes (W_BOARD_CHANGED too) go unreported: results_of's hash check is retune's one gate
        _, board, geom, _ = load(path)
        results_of(new, build_model(new, board, geom))
        command = command_line("kicad-rf-studio", "retune", str(path), *assignments)
        lines = write_outputs(path, new, command)
        if assignments:
            _save(path, new, command)
    emit = emit or (lambda code, params: print(render(code, **params)))
    for code, params in lines:
        emit(code, params)
    return 0


def verify(path: Path) -> int:
    """`verify` on the project at `path` (spec 3.2, 7.6, C-36..C-38), returning its exit code as run does (C-22).
    Before the lock: E_VERIFY_NO_PARTS when no part is a port or a curve_port (a single trace), E_VERIFY_CURVE for the
    first curve_port, E_NO_RESULTS, E_VERIFY_PORTS for fewer than 2 external ports. Then as in run, under the lock in
    a fresh run folder whose events.jsonl gets every line, with any KrsError a message event and exit 2:
    W_FILLS_AS_SAVED and load()'s notes, stopping with stops(); the model, 3 when a mesh gate blocks; results_of and
    the run's layout N-port; verify's model (verify_spec) and the part ports' loads at their ideal values, the part
    models and S2P files ignored (C-38), every refusal before any job. Then simulate on verify's model, its external
    ports the only jobs: 3 when its setup gate blocks, and unless every job kept S, W_VERIFY_NOT_KEPT and 4 with
    nothing stored. Else verify's own N-port is compared with the run's closed by those loads, the noisier of the
    run's and the project's presets setting the null floor; the comparison goes to project.json's verify (its results
    kept), then verify.s{P}p to results/ with its port map and grid lines, a refusal of either an E_ line, so that a
    held file costs only that file. The lines follow: I_VERIFY_RESULTS when the comparison was stored,
    I_VERIFY_COMPARE, I_VERIFY_NULL or W_VERIFY_NULL_UNMATCHED for each null (I_VERIFY_NO_NULLS for none), the
    indicator lines with a 2-port's loss budget in its verify form (the parts in the grid, no part loss removed), the
    E_ lines as message events, I_OUTPUTS when verify.s{P}p was written, I_VERIFY_SCOPE and LIMITS; then 0, or 2
    after an E_ line."""
    project = read_project(path)  # before the lock, as in run
    by_ref = parts(project)
    if not any(q["role"] in (PORT, CURVE_PORT) for q in by_ref.values()):
        raise KrsError("E_VERIFY_NO_PARTS")
    if curve := next((ref for ref, q in by_ref.items() if q["role"] == CURVE_PORT), None):
        raise KrsError("E_VERIFY_CURVE", ref=curve)
    if "results" not in project:
        raise KrsError("E_NO_RESULTS")
    if len(project["ports"]) < 2:  # the external ports, as _split counts them; compare() reads S21 and S11
        raise KrsError("E_VERIFY_PORTS", ports=len(project["ports"]))
    return _locked(path, _verify)


def _verify(path: Path, run_dir: Path) -> int:
    """verify() under the lock, with `run_dir` made."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    if isinstance(built := _model_phase(path, emit), int):
        return built
    project, _, model = built
    results = results_of(project, model)
    lay = layout(project, results)
    by_ref, (ext, refs) = parts(project), _split(lay)
    values = {ref: by_ref[ref]["value"] for ref in refs}
    dump = runs.job_dir(Path(results["run_dir"]), 0, "setup") / "operator_dump.vtr"
    vspec = verify_spec(model.spec, by_ref, results["c_box"], dump, results["dt"])
    zk = loads({ref: z_part(part_kind(ref), port_value(ref, values[ref]), None, lay.f) for ref in refs}, refs,
               results["c_box"], lay.f)  # the ideal values, the part models and S2P files ignored (C-38)
    if (out := simulate(replace(model, spec=vspec), project, run_dir)) is None:
        return 3
    done, _, wall_s = out
    kept = sum(j["verdict"] in KEPT for j in done)
    if kept < len(done):  # nothing compared or stored
        emit("result", "W_VERIFY_NOT_KEPT", {"kept": kept, "runs": len(done), "wall": duration(wall_s),
                                             "folder": str(run_dir)})
        return 4
    own = layout(project, {"run_dir": str(run_dir), "jobs": done})
    k0, p = lay.markers[0], len(own.ports)
    # 10 × the S tolerance of the noisier preset, the run's or verify's own
    floor = 10 * max(PRESETS[results["preset"]][1], PRESETS[project["preset"]][1])
    cmp = compare(own.s, terminate(lay.s, ext, zk, lay.f), lay.f, k0, floor)
    command = command_line("kicad-rf-studio", "verify", str(path))
    # the comparison is stored first, then verify.s{P}p written; a refusal of either is a line, so the comparison is
    # still printed and a held file costs only that file
    lines, errors, outputs = [], [], []
    try:
        data = load_project(path)  # as it is now: only verify is replaced
        data["verify"] = {"model_hash": spec_hash(vspec), "base_hash": results["model_hash"], "values": values,
                          "run_dir": str(run_dir), "jobs": done, "compare": cmp}
        _save(path, data, command)
    except KrsError as err:  # E_RESULTS_WRITE for project.json, or E_PROJECT_UNREADABLE after a hand edit meanwhile
        errors.append((err.code, err.params))
    else:
        lines.append(("I_VERIFY_RESULTS", {"runs": len(done), "wall": duration(wall_s), "path": str(path)}))
    folder, name = path.parent / "results", f"verify.s{p}p"
    basis = {**results, "run_dir": str(run_dir), "jobs": done, "preset": project["preset"]}
    comments = port_map(project, basis, own, list(range(p))) + grid_lines(vspec["grid"], values)
    try:
        write(folder, {name: touchstone(own.s, own.f, [q["name"] for q in own.ports], comments)}, VERIFY_OUTPUT,
              command)
    except KrsError as err:  # E_RESULTS_WRITE for verify.s{P}p
        errors.append((err.code, err.params))
    else:
        outputs.append(("I_OUTPUTS", {"files": name, "folder": str(folder)}))
    lines.append(("I_VERIFY_COMPARE", {"f0_mhz": f"{own.f[k0] / 1e6:g}", "a_db": f"{own.a_db[k0]:.1f}",
                                       "ds21_db": f"{cmp['ds21_db_f0']:.3f}", "ds11": f"{cmp['ds11_f0']:.4f}",
                                       "ds_max": f"{cmp['ds_max']:.4f}"}))
    for null in cmp["nulls"]:
        k = np.abs(own.f - null["f_hz"]).argmin()  # the grid point nearest the null
        at = {"f_mhz": f"{null['f_hz'] / 1e6:.1f}", "a_db": f"{own.a_db[k]:.1f}"}
        if null["shift"] is None:
            lines.append(("W_VERIFY_NULL_UNMATCHED", at))
        else:
            lines.append(("I_VERIFY_NULL", {**at, "shift_pct": f"{100 * null['shift']:+.2f}"}))
    if not cmp["nulls"]:
        lines.append(("I_VERIFY_NO_NULLS", {}))
    p_layout = loss_budget(own.s, list(range(p)), np.zeros((len(own.f), 0))) if p == 2 else None  # P_parts = 0
    lines += [*indicator_lines(own.f, own.a_db, own.s, p_layout, results["loss_expected"], in_grid=True), *errors,
              *outputs, ("I_VERIFY_SCOPE", {}), *((code, {}) for code in LIMITS)]
    for code, params in lines:
        emit("message" if code.startswith("E_") else "result", code, params)
    return 2 if errors else 0


def appcsxcad(settings: dict) -> str | None:
    """AppCSXCAD's path: in settings.json's openems_dir, then in CSXCAD_INSTALL_PATH, then on PATH; None when none of
    them has it."""
    folders = (settings.get("openems_dir"), os.environ.get("CSXCAD_INSTALL_PATH"), os.environ.get("PATH"))
    return shutil.which("AppCSXCAD", path=os.pathsep.join(filter(None, folders)))


def open_viewer(exe: str, job: Path) -> None:
    """Opens model.xml in AppCSXCAD `exe`, detached and not waited for, with the job folder `job` as its working
    directory and a relative file name: AppCSXCAD fails on non-ASCII paths (spec 8)."""
    detach = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
              if sys.platform == "win32" else {"start_new_session": True})
    subprocess.Popen([exe, "model.xml"], cwd=job, **detach)


def preview(path: Path) -> int:
    """`preview` on the project at `path` (C-34), returning its exit code: W_FILLS_AS_SAVED and load()'s notes, then 2
    on a refusal among them; the model and its mesh gates, then 3 when the edge lint left no spec. A blocking gate,
    geometry or mesh, does not stop it: preview is how one looks at a failing model. Then check_openems(), model.json
    in a run folder of its own and one xml worker in job-0-xml (port 1, one thread; preview does not calibrate);
    E_APPCSXCAD_MISSING, naming its model.xml and this OS's install command, when no AppCSXCAD is found, else AppCSXCAD
    opens it, I_PREVIEW and 0."""
    project, board, geom, notes = load(path)
    for code, params in [("W_FILLS_AS_SAVED", {}), *notes]:
        print(render(code, **params))
    if stops(notes) == 2:
        return 2
    model = build_model(project, board, geom)
    for code, params in model.blocked:
        print(render(code, **params))
    if model.spec is None:  # E_EDGE_LINT left no mesh to write
        return 3
    for code, params in runs.check_openems():
        print(render(code, **params))
    run_dir, settings = runs.run_dir_for(path.absolute().parent.name), runs.load_settings()  # absolute: as in cost
    runs.write_spec(run_dir, model.spec)
    job = runs.write_job(runs.job_dir(run_dir, 0, "xml"), 1, "xml", 1, model.spec["excitation"]["t_max"])
    runs.check_job(job, runs.run_jobs([job], 1, run_dir, settings)[job], "xml", settings)
    xml = str(job / "model.xml")
    if (exe := appcsxcad(settings)) is None:
        raise KrsError("E_APPCSXCAD_MISSING", path=xml, command=runs.install_command())
    open_viewer(exe, job)
    print(render("I_PREVIEW", path=xml))
    return 0
