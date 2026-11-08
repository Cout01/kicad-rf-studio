# SPDX-License-Identifier: GPL-3.0-or-later
"""What `cost`, `run`, `retune`, `verify` and `preview` share (spec 6.1): a project read with its board and geometry,
its model built through the mesh gates, the calibration that sizes its jobs, the setup gate on openEMS's setup-only run
(timestep floor, port connectivity, unused primitives), the cost model (spec 6.4), the job phase and the outputs of a
run's results (spec 7.3); and `cost` (spec 3.2), `run` (spec 6.1), `retune` (spec 3.2, 7.2, 7.8), `verify` (spec 7.6)
and `preview` (C-34) themselves. `compare BASE VARIANT` compares two antenna projects' or two signal-integrity
projects' full simulations (pipeline.compare_projects, Stage 3 and Stage 4)."""
from __future__ import annotations

import contextlib
import copy
import json
import math
import os
import secrets
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

from kicad_rf_studio import __version__, runs
from kicad_rf_studio.core.cs2d import ShortError, pair, solve
from kicad_rf_studio.core.geometry import build_geometry, chain_of
from kicad_rf_studio.core.geometry.region import air_cell, band
from kicad_rf_studio.core.geometry.sections import cross_section, route_length
from kicad_rf_studio.core.geometry.zstack import substrate_h
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.stackup import Stackup
from kicad_rf_studio.core.kicad.tracer import adopt, check_antenna
from kicad_rf_studio.core.kicad.values import bypass, port_value
from kicad_rf_studio.core.mesh.gates import check_fit2d, dt_floor_reference, fit2d, mesh_with_lint
from kicad_rf_studio.core.messages import KrsError, english, reason, render
from kicad_rf_studio.core.model.parts import CURVE_PORT, GRID, PORT
from kicad_rf_studio.core.model.ports import ends, nominal_boxes, place
from kicad_rf_studio.core.model.readers import read_log, read_probe, read_run_stats, read_stats
from kicad_rf_studio.core.model.spec import (DEBYE_POLES, air_box, cell_split, debye_cells, far_field_box, grid_entry,
                                             metal_in_pml, model_spec, round_trip, spec_hash, verify_spec)
from kicad_rf_studio.core.post.antenna import (ANTENNA_LIMITS, ANTENNA_OUTPUTS, ANTENNA_VERIFY_OUTPUTS, COMPARE_OUTPUTS,
                                               antenna_csv, antenna_png, compare_png, compare_s11, delta_lines, deltas,
                                               deltas_csv, eta_what_if_lines, far_field_lines, far_field_of,
                                               farfield_csv, s11_lines)
from kicad_rf_studio.core.post.chain import above_dc, ideal_schematic, loads, part_impedances, terminate, z_value
from kicad_rf_studio.core.post.checks import compare, indicator_lines, loss_budget, loss_expected
from kicad_rf_studio.core.post.outputs import (LIMITS, OUTPUTS, VERIFY_OUTPUT, grid_lines, marker_lines, port_map,
                                               summary_csv, summary_png, touchstone, write)
from kicad_rf_studio.core.post.si import (SI_OUTPUTS, Reading, compare_verify, hammerstad, read, si_csv,
                                          si_delta_lines, si_deltas, si_limits, si_lines, si_png, tdr_csv)
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import (GATES, GATES_SI, antenna, board_file, board_hash, copper_model, default_gates,
                                          load_project, mesh_n, parts, read_project, relative_path, save_project, si)
from kicad_rf_studio.stoprule import (KEPT, PRESETS, RING_CEILING, WINDOW_S, Records, Verdict, ceiling, residual_db,
                                      stop_rule)
from kicad_rf_studio.worker import GRIDS, LOG

if TYPE_CHECKING:
    from collections.abc import Callable

    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.kicad.board import Board
    from kicad_rf_studio.core.mesh import Mesh
    from kicad_rf_studio.core.post.waves import Layout

GEOMETRY_GATES = ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI")  # the geometry's notes that block a run
VERDICTS = {"converged": "I_JOB_CONVERGED", "flat": "W_JOB_FLAT", "t_max": "W_JOB_T_MAX", "diverged": "E_JOB_DIVERGED",
            "growth": "E_JOB_GROWTH", "unclassified": "W_JOB_UNCLASSIFIED", "stopped": "W_JOB_STOPPED"}  # spec 6.3
# spec 7.6 (amendment A-4): the instant retune is labelled relative / what-if until P0-C passes; the owner sets True
# after P0-C (controller recommendation, owner unavailable)
RETUNE_VALIDATED = False
LONG_RUN_S = 7200  # design 5.9: a warning past two hours


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
    copper (C-9), but in an SI project, whose geometry takes its lines' layers (Stage 4 design 5.3). An SI project whose
    "dielectric" is "debye" then names in W_SI_DEBYE_NO_LOSS the stackup's dielectric layers whose loss tangent reads 0,
    which model_spec leaves lossless (Stage 4 plan 4 ruling D-4): a loss tangent the board leaves out reads KiCad's
    0.02 (Layer.__post_init__), so only 0 runs lossless. An antenna project's antenna is checked again as `new` checks
    it (tracer.check_antenna: an edited ref or a re-annotated board raises E_ANTENNA_UNKNOWN, E_ANTENNA_MODULE,
    E_ANTENNA_CHIP or E_NOT_AN_ANTENNA); then its netless copper takes the feed net, the chain's last (tracer.adopt,
    Stage 3 design 5.3), before the geometry is built."""
    project = read_project(path)
    file = board_file(path, project)
    board = load_board(file)
    if antenna(project):
        check_antenna(board, project["antenna"]["ref"])
        adopt(board, project["antenna"]["ref"], project["chain"]["nets"][-1])
    geom = build_geometry(board, project)
    notes = [("W_BOARD_CHANGED", {"path": str(file)})] if board_hash(file) != project["board"]["sha256"] else []
    top = board.copper_layers[0]  # top to bottom
    notes += [*board.warnings, *geom.notes,
              *(("W_OFF_TOP_LAYER", {"net": s.net, "layer": s.layer}) for s in geom.sections
                if s.layer != top and not si(project))]
    if si(project) and project["dielectric"] == "debye":
        layers = Stackup.from_json(project["stackup"]).layers
        if names := [x.name for x in layers if x.kind == "dielectric" and x.loss_tangent == 0]:
            notes.append(("W_SI_DEBYE_NO_LOSS", {"layers": ", ".join(names)}))
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
    """The model of `project` (spec 6.1 step 2, C-42): its port ends; the mesh, finest across their nominal boxes, an
    SI project's at its mesh.max_cell_mm (Stage 4 design 5.3), with the edge lint (on E_EDGE_LINT no mesh and no spec,
    and that gate blocked); fit2d against gates.fit2d_limit (E_FIT2D, E_FIT2D_FINE or E_FIT2D_SHORT blocked, the model
    still built); the timestep floor's reference, from the mesh before any port is placed on it; an antenna's mesh in
    its air box (Stage 3 design 5.2); each end placed on the mesh, a grid part's through grid_entry with its entry in
    project.json; then the model spec. Raises the refusals of ends, place and grid_entry; the caller handles stops() of
    load()'s notes first."""
    e = ends(board, project, geom.pieces)
    n = mesh_n(project)
    try:
        mesh = mesh_with_lint(geom, replace(geom.protected, boxes=nominal_boxes(e)), n,
                              max_cell=project["mesh"]["max_cell_mm"] if si(project) else None)
    except KrsError as err:  # E_EDGE_LINT
        return Model(None, None, [(err.code, err.params)], None)
    blocked = []
    try:
        check_fit2d(fit2d(geom, mesh), project["gates"]["fit2d_limit"], n)
    except KrsError as err:  # E_FIT2D_SHORT from fit2d, E_FIT2D or E_FIT2D_FINE from check_fit2d
        blocked.append((err.code, err.params))
    dt_ref = dt_floor_reference(mesh)
    if antenna(project):
        mesh = air_box(mesh, project["air_gap_mm"], air_cell(band(project)[1]), project["boundary"] == "pml_8")
    by_ref = parts(project)
    ports, grid = [], []
    for end in e:
        placed = place(end, mesh, geom.zs, geom.pieces)
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
                  for end, cap, witness in (("T_END_REFERENCE", rc, rw), ("T_END_SIGNAL", sc, sw))
                  if not (cap == witness >= 0)]
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
    cells; an antenna's split of them into board, air and PML (cell_split, Stage 3 design 5.9); the smallest cell; dt
    against its floor, with the edge that sets it in KiCad's frame; the worst case, every run to T_max, in
    ceil(runs / pool) rounds; the time predicted from the longest stop time of the last run's jobs that kept S, when
    that run was of this model; the RAM; the main cost (driver). An antenna's two times take the cost refit's
    corrections: each PML cell counts as runs.PML_WEIGHT cells, at runs.small_speed(`pool`) × `per_job_mcs`; its RAM
    counts the cells. An SI project's two times count each cell in its Debye dielectric (debye_cells) as
    runs.DEBYE_WEIGHT cells (Stage 4 design 5.9, plan 4 ruling D-4). Its worst case is followed by its runs broken down
    into the measured lines' ends, the victims' ends and the part ports (I_SI_COST_JOBS), then, with a Debye dielectric,
    its cells there, their weight and DEBYE_POLES' count (I_SI_COST_DEBYE), then the ring rule's ceiling, RING_CEILING
    × T_max, and its runs' time to it (I_SI_COST_RING), then W_SI_LONG_RUN when the worst case exceeds LONG_RUN_S: it
    stays on T_max, since only a job whose planes ring runs past it (Stage 4 plan 4 ruling T-2)."""
    mesh, ports, dt = model.mesh, model.spec["ports"], setup["dt"]
    nx, ny, nz = len(mesh.x), len(mesh.y), len(mesh.z)
    cells, n_runs, n_parts = nx * ny * nz, len(ports), sum(q["part"] for q in ports)
    weighted, mcs, split = cells, per_job_mcs, []  # the cells a timestep costs, at mcs MC/s a job
    n_debye = debye_cells(model.spec) if si(project) else 0
    if antenna(project):
        board, air, pml = cell_split(model.spec)
        ratio = runs.small_speed(pool)
        weighted, mcs = cells + (runs.PML_WEIGHT - 1) * pml, per_job_mcs * ratio
        split = [("I_COST_SPLIT", {"board": f"{board / 1e6:.2f}", "air": f"{air / 1e6:.2f}", "pml": f"{pml / 1e6:.2f}",
                                   "weight": f"{runs.PML_WEIGHT:g}", "ratio": f"{ratio:g}"})]
    elif n_debye:
        weighted = cells + (runs.DEBYE_WEIGHT - 1) * n_debye

    def seconds(t_stop: float) -> float:
        return math.ceil(n_runs / pool) * weighted * (t_stop / dt) / (mcs * 1e6)

    size, axis, at = smallest_cell(mesh)
    t_max = project["t_max_s"]
    notes = [
        ("I_COST_CELLS", {"nx": nx, "ny": ny, "nz": nz, "mcells": f"{cells / 1e6:.2f}", "n": mesh_n(project),
                          "d_mm": f"{mesh.d:.4f}"}),
        *split,
        ("I_COST_SMALLEST", {"size_um": f"{size * 1e3:.1f}", "axis": axis, "at_mm": f"{at:.3f}"}),
        ("I_COST_DT", dt_params(model, project["gates"]["dt_floor"], setup)),
        ("I_COST_TIME", {"time": duration(seconds(t_max)), "runs": n_runs, "t_max_ns": f"{t_max * 1e9:g}",
                         "pool": pool, "threads": threads})]
    if si(project):
        roles = [line["role"] for line in project["lines"]]
        notes.append(("I_SI_COST_JOBS", {"lines": 2 * roles.count("measured"), "victims": 2 * roles.count("victim"),
                                         "parts": n_parts}))
        if n_debye:
            # ponytail: the registered pole count; the fit drops a pole that fits 0, so a material may hold fewer
            notes.append(("I_SI_COST_DEBYE", {"mcells": f"{n_debye / 1e6:.2f}", "weight": f"{runs.DEBYE_WEIGHT:g}",
                                              "poles": len(DEBYE_POLES)}))
        notes.append(("I_SI_COST_RING", {"ceiling_ns": f"{RING_CEILING * t_max * 1e9:g}",
                                         "time": duration(seconds(RING_CEILING * t_max))}))
        if seconds(t_max) > LONG_RUN_S:
            notes.append(("W_SI_LONG_RUN", {"time": duration(seconds(t_max))}))
    results = project.get("results", {})  # a job with no samples has no stop time, and a stopped one a wrong one
    t_stops = [j["t_stop"] for j in results.get("jobs", ()) if j["verdict"] in KEPT and j["t_stop"] is not None]
    if t_stops and results.get("model_hash") == spec_hash(model.spec):  # another model stops elsewhere
        notes.append(("I_COST_PREDICTED", {"time": duration(seconds(max(t_stops)))}))
    # ponytail: RAM counts the cells, not the far-field dumps (12 MB at 2.4 GHz, r1); add them if W_RAM misleads
    gb = pool * (runs.MB_PER_MCELL * cells / 1e6 + runs.MB_PER_WORKER) / 1024
    return [*notes, ("I_COST_RAM", {"gb": f"{gb:.1f}", "pool": pool}), driver(mesh, n_runs, n_parts)]


def prepare(model: Model, emit: Callable[[str, dict], None], run_dir: Path | None = None, *,
            small: bool = False, si: bool = False) -> tuple[int, int, float]:
    """What the jobs of a built `model` (one with a mesh) run with: (threads, pool, per-job MC/s), from this machine's
    calibration, measured first on a machine that has none (spec 6.4), inside the command's `run_dir` when it has one
    (runs.calibrate), the pool no larger than the number of runs, so that the cost lines count only jobs that run at
    once, and the per-job MC/s at that level (runs.per_job_mcs, D-16). With `small` (an antenna's model, Stage 3
    design 5.9) and a pool of 1, the per-job MC/s is the calibration's own one-job speed at its threads ("single"),
    when it holds one, else per_job_mcs at 1: the cost refit measured runs.SMALL_SPEED[1] against that speed, which no
    run refreshes, while a v1 run at pool 1 refreshes levels["1"]. With `si` (an SI project's model, Stage 4 plan 4
    ruling K-1), a per-job MC/s that is still the calibration's own at that level (runs.calibrated_mcs) is taken at
    runs.SI_SPEED of it, with I_SI_COST_SPEED, until a run at that level measures it. Calls `emit(code, params)` with
    check_openems()'s warnings, before any worker (C-31), and with W_RAM when one job needs more RAM than is free.
    Raises check_openems()'s refusals and what calibrate raises."""
    for code, params in runs.check_openems():
        emit(code, params)
    entry = runs.ensure_calibrated(runs.load_settings(), run_dir)
    cells = len(model.mesh.x) * len(model.mesh.y) * len(model.mesh.z)
    threads, pool = runs.sizing(entry, cells)
    need = runs.MB_PER_MCELL * cells / 1e6 + runs.MB_PER_WORKER  # one job's RAM in MB, as pool_size counts it
    free = runs.free_ram_mb()
    if need > free:
        emit("W_RAM", {"need_gb": f"{need / 1024:.1f}", "free_gb": f"{free / 1024:.1f}"})
    pool = min(pool, len(model.spec["ports"]))
    mcs = runs.per_job_mcs(entry, pool)
    if small and pool == 1:
        mcs = entry.get("single", {}).get(str(threads), mcs)
    if si and mcs == runs.calibrated_mcs(entry, pool):
        mcs *= runs.SI_SPEED
        emit("I_SI_COST_SPEED", {"ratio": f"{runs.SI_SPEED:g}"})
    return threads, pool, mcs


def setup_gate(model: Model, project: dict, run_dir: Path, settings: dict, threads: int) -> tuple[dict, list, list]:
    """openEMS's setup of a built `model` and the gates on it (spec 6.1 step 2): model.json in `run_dir`, one
    setup-only worker in job-0-setup, then (its setup.json, the gates that block a run, the warnings). Blocking:
    E_DT_FLOOR when dt is under gates.dt_floor × the model's reference (C-17), E_METAL_IN_PML (metal_in_pml) for a
    structure within an antenna's PML or the 2 cells inside it (Stage 3 design 5.2), port_gates (C-15), and
    E_UNUSED_PRIMITIVE for each "unused" entry of a port_* or lumped_* property (a port, its probes, a grid part);
    W_UNUSED_PRIMITIVE for any other property, copper (C-16). Raises what check_job raises, KeyboardInterrupt when STOP
    or Ctrl+C stopped the job."""
    runs.write_spec(run_dir, model.spec)
    # T_max 2·t0, the pulse's end: nothing in setup depends on T_max, and openEMS's excitation arrays et and ht hold
    # NrTS lines
    job = runs.write_job(runs.job_dir(run_dir, 0, "setup"), 1, "setup", threads, 2 * model.spec["excitation"]["t0"])
    runs.check_job(job, runs.run_jobs([job], 1, run_dir, settings)[job], "T_JOB_SETUP", settings)
    setup = json.loads((job / "setup.json").read_text(encoding="utf-8"))
    floor, blocked, warnings = project["gates"]["dt_floor"], [], []
    # ponytail: dt from the setup log (6 digits); openEMS_stats.txt exists only after a run
    if setup["dt"] < floor * model.dt_ref:
        blocked.append(("E_DT_FLOOR", dt_params(model, floor, setup)))
    blocked += metal_in_pml(model.spec)
    blocked += port_gates(model.spec["ports"], setup["pec"])
    for kind, prop in setup["unused"]:  # [type, property], ["none", property] or ["outside", property]
        note = {"property": prop, "type": kind}
        if prop.startswith(("port_", "lumped_")):
            blocked.append(("E_UNUSED_PRIMITIVE", note))
        else:
            warnings.append(("W_UNUSED_PRIMITIVE", note))
    return setup, blocked, warnings


def readout_2d(geom: Geometry) -> list[tuple[str, dict]]:
    """The lines of the 2D readout (spec 3.2): I_2D_HEADER (W_NO_SECTIONS without a measured section), then each
    measured section solved on cs2d's own grid without and with the exact mask of its own side (none on inner copper),
    in chain-net order and then by place, I_2D_SECTION, or W_2D_SHORT in its place where other copper touches the line
    at its cut. It prints nothing."""
    lines = [("I_2D_HEADER" if geom.sections else "W_NO_SECTIONS", {})]
    for s in geom.sections:
        named = {"net": s.net, "layer": s.layer, "width_mm": f"{s.width:.3f}", "length_mm": f"{s.length:.3f}"}
        try:
            bare, coated = [solve(cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), m))
                            for m in ("none", "exact")]
        except ShortError:  # another net's copper (E_SHORT_IN_ROI) or copper with none, which no check reports
            lines.append(("W_2D_SHORT", named))
            continue
        lines.append(("I_2D_SECTION", {**named, "gap_mm": "T_NONE" if s.gap is None else f"{s.gap:.3f}",
                                       "z0": f"{bare.z0:.2f}", "eeff": f"{bare.eps_eff:.3f}",
                                       "z0_mask": f"{coated.z0:.2f}", "eeff_mask": f"{coated.eps_eff:.3f}"}))
    return lines


def si_readout(board: Board, geom: Geometry, project: dict) -> list[tuple[str, dict]]:
    """The 2D table of an SI project (Stage 4 design 5.9), no file written: I_SI_2D_HEADER (W_NO_SECTIONS without a
    section), then each section of `geom` in order, its cut solved on cs2d's own grid with the exact mask of its side,
    in a box of its own layer's substrate (cross_section's `h`): a pair's line whose partner runs alongside at the cut
    as I_SI_2D_PAIR (cs2d.pair: Zdiff, Zodd, Zeven, the odd and even εeff, the delay at the odd mode's); a pair's line
    alone there as I_SI_2D_LEG (Z0, Zdiff 2·Z0 uncoupled); a single net's as I_SI_2D_LINE; each against the target
    band, |Z − target| ≤ tolerance·target, a victim's as T_VICTIM; W_2D_SHORT where other copper touches the line at
    its cut. Then I_SI_SHORT_ROUTE for the longest measured route (route_length) when its delay, at the largest εeff
    its rows read, is under rise_s/6."""
    target, tolerance, rise = project["target_ohm"], project["tolerance"], project["rise_s"]
    victims = {net for line in project["lines"] if line["role"] == "victim" for net in line["chain"]["nets"]}
    rows = [("I_SI_2D_HEADER", {"target": f"{target:g}", "tolerance_pct": f"{100 * tolerance:g}"})
            if geom.sections else ("W_NO_SECTIONS", {})]
    read = []  # each row's net and the largest εeff it reads, for the short route

    def verdict(net: str, z: float) -> str:
        if net in victims:
            return "T_VICTIM"
        return "T_IN_BAND" if abs(z - target) <= tolerance * target else "T_OUT_OF_BAND"

    def delay_s(length_mm: float, eps_eff: float) -> float:
        return round_trip(length_mm, eps_eff) / 2

    # ponytail: no skip rule for a cut that is no line's until plan 4's P4-C sets one; the fixtures have none
    for s in geom.sections:
        named = {"net": s.net, "layer": s.layer, "width_mm": f"{s.width:.3f}", "length_mm": f"{s.length:.3f}"}
        cut = partial(cross_section, s, geom.pieces, geom.zs, geom.masks.get(s.layer), "exact",
                      h=substrate_h(geom.zs, (s.layer,)))
        coupled = None
        if partners := geom.partners(s.net):
            with contextlib.suppress(ValueError):  # no partner at the cut, widths over 2·SIMPLIFY apart, or a short
                cs = cut(partners=partners)
                coupled = pair(cs)
        if coupled is not None:
            # ponytail: mean-c11 modes as a screening; on usb2_hs's long cut the legs alone read 51.01 and 51.10 Ω
            p, n = (r for r in cs.conductors if r.role == "signal")
            rows.append(("I_SI_2D_PAIR", {**named, "gap_mm": f"{max(n.x0 - p.x1, p.x0 - n.x1):.3f}",
                                          "z_diff": f"{coupled.z_diff:.2f}", "z_odd": f"{coupled.z_odd:.2f}",
                                          "z_even": f"{coupled.z_even:.2f}", "eeff_odd": f"{coupled.eps_odd:.3f}",
                                          "eeff_even": f"{coupled.eps_even:.3f}",
                                          "delay_ps": f"{delay_s(s.length, coupled.eps_odd) * 1e12:.1f}",
                                          "verdict": verdict(s.net, coupled.z_diff)}))
            read.append((s.net, max(coupled.eps_odd, coupled.eps_even)))
            continue
        try:
            line = solve(cut())
        except ShortError:  # another net's copper (E_SHORT_IN_ROI) or copper with none, which no check reports
            rows.append(("W_2D_SHORT", named))
            continue
        read.append((s.net, line.eps_eff))
        named |= {"z0": f"{line.z0:.2f}", "eeff": f"{line.eps_eff:.3f}",
                  "delay_ps": f"{delay_s(s.length, line.eps_eff) * 1e12:.1f}"}
        if partners:
            # ponytail: such a pair reads 2·Z0 with its partner grounded, which overstates Zdiff by the coupling;
            # cs2d's asymmetric modes if real boards need it
            rows.append(("I_SI_2D_LEG", {**named, "z_diff": f"{2 * line.z0:.2f}",
                                         "verdict": verdict(s.net, 2 * line.z0)}))
        else:
            rows.append(("I_SI_2D_LINE", {**named, "gap_mm": "T_NONE" if s.gap is None else f"{s.gap:.3f}",
                                          "verdict": verdict(s.net, line.z0)}))
    route = max((line["chain"]["nets"] for line in project["lines"] if line["role"] == "measured"),
                key=lambda nets: route_length(board, nets))
    eps = max((e for net, e in read if net in route), default=None)
    if eps is not None and (delay := delay_s(route_length(board, route), eps)) < rise / 6:
        rows.append(("I_SI_SHORT_ROUTE", {"net": route[0], "delay_ps": f"{delay * 1e12:.1f}",
                                          "rise_ps": f"{rise * 1e12:g}"}))
    return rows


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


def si_route(board: Board, geom: Geometry, project: dict) -> dict:
    """An SI run's route (Stage 4 design 5.6), from its geometry, as expected_loss is v1's, recorded with its results:
    the measured line whose route_length is the longest (a pair's P leg on a tie); each section of that line cut as
    si_readout cuts a line alone, `cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), "exact",
    h=substrate_h(geom.zs, (s.layer,)))` (a cut that other copper touches adds nothing), on the slab expected_loss
    takes (the one below the copper, else above); "eeff", their εeff weighted by length, the distance axis's 2D εeff;
    "length_mm", that route_length; "loss_db", at marker_hz and at f_max_hz, the copper's
    20·log10(e)·Σ hammerstad(f, s.width, z0)·ℓ and the dielectric's −10·log10(1 − loss_expected(terms, f)), each over
    the sections' Σℓ and times length_mm, in dB. With no section solved (a route of 45° tracks or arcs alone, or every
    cut touched), "eeff" is the stack's largest εr, as new's, and "loss_db" None."""
    # ponytail: one line's loss for a pair, the P leg's (the odd mode's runs a little higher); the straight sections'
    # mean per mm stands for the bends and pads
    # ponytail: si_readout's cut and expected_loss's slab written once more, not hoisted, as expected_loss is v1's; a
    # shared helper if a third copy comes
    nets = max((line["chain"]["nets"] for line in project["lines"] if line["role"] == "measured"),
               key=lambda nets: route_length(board, nets))
    length = route_length(board, nets)
    solved = []  # each section of the route solved: (the section, its 2D line, its slab)
    for s in geom.sections:
        if s.net not in nets:
            continue
        try:
            line = solve(cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), "exact",
                                       h=substrate_h(geom.zs, (s.layer,))))
        except ShortError:
            continue
        i = next(k for k, slab in enumerate(geom.zs) if slab.copper == s.layer)
        solved.append((s, line, geom.zs[i - 1] if i and geom.zs[i - 1].kind == "dielectric" else geom.zs[i + 1]))
    if not solved:
        return {"eeff": max(s.eps_r for s in geom.zs if s.kind == "dielectric"), "length_mm": length, "loss_db": None}
    total = sum(s.length for s, _, _ in solved)
    terms = [(d.eps_r, line.eps_eff, d.tan_d or 0.0, s.length) for s, line, d in solved]
    freqs = (project["marker_hz"], project["f_max_hz"])
    conductor = [20 * math.log10(math.e) * sum(hammerstad(f, s.width, line.z0) * s.length * 1e-3
                                               for s, line, _ in solved) / total * length for f in freqs]
    dielectric = [-10 * math.log10(1 - loss_expected(terms, f)) / total * length for f in freqs]
    return {"eeff": sum(line.eps_eff * s.length for s, line, _ in solved) / total, "length_mm": length,
            "loss_db": {"conductor": conductor, "dielectric": dielectric}}


def gate_lines(gates: dict, defaults: dict = GATES) -> list[tuple[str, dict]]:
    """W_GATE_LIMITS when the gate limits `gates` are not `defaults` (C-10), W_GATE_LIMITS_SI when those are GATES_SI
    (an SI project's, default_gates), else none."""
    if gates == defaults:
        return []
    return [("W_GATE_LIMITS_SI" if defaults == GATES_SI else "W_GATE_LIMITS",
             {"fit2d_limit": f"{gates['fit2d_limit']:g}", "dt_floor": f"{gates['dt_floor']:g}"})]


def cost(path: Path, run_dir: Path | None = None) -> int:
    """`cost` on the project at `path` (spec 3.2), returning its exit code (C-22): W_FILLS_AS_SAVED, the 2D readout (an
    SI project's 2D table, si_readout) and load()'s notes, then 2 on a refusal among them; a project without ports
    stops there with W_NO_PORTS. Then the model and its mesh gates; with a spec, prepare (a first-use calibration
    inside the run folder), the setup gate in `run_dir`, else a run folder of its own, its lines as events,
    gate_lines when the gate limits are not default_gates' (C-10), and the cost lines. 3 if any gate blocked
    (geometry, mesh or setup), else 0. A `run_dir` that exists at the start (--run-dir, A-14) gets every line as an
    event from the first: the readout as cost events, the mesh gates as verdict events with job None, the others
    message events; otherwise those first lines are printed only."""
    # absolute: `cost .` names the run folder after the project's folder too
    run_dir = run_dir or runs.run_dir_for(path.absolute().parent.name)
    # ponytail: a folder made first (--run-dir) gets every line; a terminal cost prints its first lines only, so the
    # GUI's replay of it starts at its calibration or setup gate
    say = partial(runs.emit, run_dir if run_dir.is_dir() else None)  # (kind, code, params, job=None)
    project, board, geom, notes = load(path)
    say("message", "W_FILLS_AS_SAVED", {})
    for code, params in si_readout(board, geom, project) if si(project) else readout_2d(geom):
        say("cost", code, params)
    for code, params in notes:
        say("message", code, params)
    if stops(notes) == 2:
        return 2
    if not project["ports"]:
        say("message", "W_NO_PORTS", {})
        return stops(notes)
    model = build_model(project, board, geom)
    for code, params in model.blocked:
        say("verdict", code, params)
    if model.spec is None:  # E_EDGE_LINT left no mesh to set up
        return 3
    threads, pool, per_job_mcs = prepare(model, partial(say, "message"), run_dir, small=antenna(project),
                                         si=si(project))
    settings = runs.load_settings()
    setup, blocked, warnings = setup_gate(model, project, run_dir, settings, threads)
    for code, params in blocked:
        runs.emit(run_dir, "verdict", code, params, job=0)
    for code, params in warnings:
        runs.emit(run_dir, "message", code, params, job=0)
    for code, params in gate_lines(project["gates"], default_gates(project)):
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


def last_sample(rec: Records, window: float = WINDOW_S) -> tuple[float | None, float | None]:
    """The time and the port residual (dB) of the last sample of `rec`, the residual over the last `window` s (the
    stop rule's: an SI pulse's window_s, else WINDOW_S); None and None without samples."""
    return (float(rec.t_u[-1]), float(residual_db(rec, window)[-1])) if len(rec.t_u) else (None, None)


def classify_job(job: Path, result: dict, live: Verdict | None, rec: Records, k: int, preset: str,
                 exc: dict) -> tuple[str, Verdict | None]:
    """The verdict on the job in `job`, port `k`, once it exited (spec 6.3), the first match winning: a non-finite
    sample in its final records `rec`, diverged; a non-zero exit or no waves.npz, stopped when the run was stopped, else
    unclassified; the `live` verdict; the stop rule on `rec`; stopped; t_max when the log's iterations are its NrTS;
    else unclassified, never silently done. `result` is the job's entry in what run_jobs returns. Returns the verdict
    and the Verdict that gives its time and residual, None for t_max at its NrTS, stopped and unclassified."""
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
        raise KrsError("E_RESULTS_WRITE", path=str(path), reason=reason(err, "T_CANNOT_WRITE"),
                       command=command) from None


def basis_lines(results: dict, defaults: dict = GATES) -> list[tuple[str, dict]]:
    """The first lines of a run's outputs, from the run `results` holds: I_BASIS, each flagged job (flat or t_max) where
    its S ends, at its cut when it has one (the stop rule's verdict; an SI job's at or past T_max, ruling T-2), else at
    its last sample, then gate_lines against `defaults` (C-10)."""
    count = Counter(job["verdict"] for job in results["jobs"])
    lines = [("I_BASIS", {"run_dir": results["run_dir"], "preset": results["preset"], "converged": count["converged"],
                          "flat": count["flat"], "t_max": count["t_max"]})]
    lines += [(VERDICTS[job["verdict"]], {"port": job["port"], "t_ns": f"{(job['t_cut'] or job['t_stop']) * 1e9:.2f}",
                                          "residual_db": f"{job['residual_db']:.1f}"})
              for job in results["jobs"] if job["verdict"] in ("flat", "t_max")]
    return lines + gate_lines(results["gates"], defaults)


@dataclass
class ChainResults:
    """A run's results as chain_results reads them: the layout N-port, its external ports by index and its part ports
    by name; the chain S (F, P, P), None after a part's refusal; with a chain and P = 2, the ideal schematic (None
    without part ports) and the loss budget, else both None, except an antenna chain's loss budget: its P_layout, for
    the what-if η_tot, which no line reports (Stage 3 design 5.6, 5.7); an SI chain has neither at any P (Stage 4
    design 5.6); whether the chain is a what-if (closed part ports while RETUNE_VALIDATED is False, D-15); the lines
    to report, I_BASIS up to W_NOT_TWO_PORT; and an SI chain's reading when si_view gave one (the GUI's read and retune
    keep it, plan 5), else None."""
    lay: Layout
    ext: list[int]
    refs: list[str]
    chain: np.ndarray | None
    ideal: np.ndarray | None
    p_layout: np.ndarray | None
    what_if: bool
    lines: list[tuple[str, dict]]
    reading: Reading | None = None


def chain_results(path: Path, project: dict, *, errors_as_lines: bool = False,
                  lay: Layout | None = None) -> ChainResults:
    """The numbers and lines that write_outputs writes and reports for the run in `project`'s results, with no file
    written (Stage 2 design 5.2 item 7): the layout N-port (layout), basis_lines (I_BASIS with each flagged job,
    gate_lines against default_gates), the part notes (part_impedances, S2P files beside `path`), the chain with every
    part port closed, each load evaluated on above_dc(lay.f) (lay.f itself on v1's and an antenna's grids); with P = 2
    the ideal schematic, the loss budget, the marker and indicator lines, else the indicator lines and W_NOT_TWO_PORT
    (C-31). A part's refusal (E_PART_NO_VALUE, E_S2P_*, E_CBOX) is raised, or, with `errors_as_lines`, becomes the last
    line, with no chain. A given `lay` stands in for the layout N-port, which depends only on the run, never on the
    part values (the GUI's retune session holds it, Stage 2 design 5.3). Raises layout's refusals and E_S_SINGULAR. An
    antenna, one port by design, gets no W_NOT_TWO_PORT but its loss budget, which no line reports (Stage 3 design 5.6,
    5.7). An SI project (Stage 4 design 5.6) gets its verdicts against GATES_SI, each part port's load held at DC at
    its value at the first point above it, and the indicator lines alone: no ideal schematic, loss budget or
    W_NOT_TWO_PORT."""
    results = project["results"]
    lay = layout(project, results) if lay is None else lay
    ext, refs = _split(lay)
    lines = basis_lines(results, default_gates(project))
    chain = ideal = p_layout = None
    fz = above_dc(lay.f)  # the loads' grid: lay.f itself off DC
    try:
        zparts, notes = part_impedances(project, path.parent, refs, fz)
        lines += notes
        zk = loads(zparts, refs, results["c_box"], fz)
    except KrsError as err:
        if not errors_as_lines:
            raise
        lines.append((err.code, err.params))
    else:
        chain = terminate(lay.s, ext, zk, lay.f)
        if si(project):  # design 5.6: v1's loss budget does not apply to SI
            lines += indicator_lines(lay.f, lay.a_db, lay.s, None, None)
        elif len(ext) == 2:
            ideal = ideal_schematic(project, zparts, lay.f) if refs else None
            p_layout = loss_budget(lay.s, ext, zk)
            lines += [*marker_lines(lay, chain, ideal),
                      *indicator_lines(lay.f, lay.a_db, lay.s, p_layout, results["loss_expected"])]
        else:
            lines += indicator_lines(lay.f, lay.a_db, lay.s, None, results["loss_expected"])
            if antenna(project):  # the power the board takes, for the what-if η_tot; no line reports it (design 5.6)
                p_layout = loss_budget(lay.s, ext, zk)
            else:
                lines.append(("W_NOT_TWO_PORT", {"ports": len(ext)}))
    return ChainResults(lay, ext, refs, chain, ideal, p_layout,
                        chain is not None and bool(refs) and not RETUNE_VALIDATED, lines)


def si_view(project: dict, res: ChainResults) -> tuple[Reading | None, list[tuple[str, dict]]]:
    """An SI result's reading and lines (Stage 4 design 5.6, 5.10), no file written: with a chain, read of it at the
    run's route's εeff, and chain_results' `res` lines followed by si_lines; without one (a part's refusal), None and
    `res`'s lines. What write_outputs reports before its label, I_OUTPUTS and limits, and what the GUI shows on a read
    and on each retune, so the two never differ."""
    if res.chain is None:
        return None, [*res.lines]
    route = project["results"]["route"]
    reading = read(res.chain, res.lay.f, project, route["eeff"])
    return reading, [*res.lines, *si_lines(project, reading, route)]


def write_outputs(path: Path, project: dict, command: str, *,
                  errors_as_lines: bool = False) -> list[tuple[str, dict]]:
    """The outputs of the run in `project`'s results (spec 3.2, 7.3, C-26..C-32), the step `run` and `retune` share:
    layout.s{N}p; chain.s{P}p when part ports are closed; with P = 2 summary.csv and summary.png, else W_NOT_TWO_PORT
    (C-31); all written to results/ beside `path` (write, with `command` as E_RESULTS_WRITE's advice). Until
    RETUNE_VALIDATED, closed part ports put the what-if label I_WHAT_IF, which offers `verify` (D-15), as the last
    comment line of chain.s{P}p, in English (english: the file is ASCII, pt-BR design 5.3), and the second line of
    summary.png's title, in the language of the process that draws it. Returns the lines to report: I_BASIS with
    each flagged job, gate_lines, the part notes, the marker and indicator lines (W_NOT_TWO_PORT after them), the
    label's line, then I_OUTPUTS and LIMITS. A part's refusal (E_PART_NO_VALUE, E_S2P_*, E_CBOX) and write's
    E_RESULTS_WRITE are raised, or, with `errors_as_lines`, each becomes a line: a part's refusal in the place of the
    chain's lines and files, so that the layout N-port is still written (C-26); E_RESULTS_WRITE in the place of
    I_OUTPUTS, so that the lines already computed and LIMITS are still reported (spec 7.5). Raises layout's refusals
    and E_S_SINGULAR. An antenna's outputs are antenna_outputs' instead (Stage 3 design 5.6). An SI project's (Stage 4
    design 5.6) are v1's with si_view's lines (chain_results', then si_lines of the chain's reading) in place of
    chain_results' and, with a reading, si_summary.csv, si_tdr.csv and si_summary.png of it (si_csv, tdr_csv, si_png,
    the label as summary.png's) in place of summary.csv and summary.png at any P, with SI_OUTPUTS as the files it owns
    and si_limits in LIMITS' place."""
    if antenna(project):
        return antenna_outputs(path, project, command, errors_as_lines=errors_as_lines)
    res = chain_results(path, project, errors_as_lines=errors_as_lines)
    results, lay, ext = project["results"], res.lay, res.ext
    folder, n, p = path.parent / "results", len(lay.ports), len(ext)
    files = {f"layout.s{n}p": touchstone(lay.s, lay.f, [q["name"] for q in lay.ports],
                                         port_map(project, results, lay, range(n)))}
    what_if = {"command": command_line("kicad-rf-studio", "verify", str(path))}
    label = render("I_WHAT_IF", **what_if) if res.what_if else None
    if res.chain is not None and res.refs:
        files[f"chain.s{p}p"] = touchstone(res.chain, lay.f, [lay.ports[k]["name"] for k in ext],
                                           port_map(project, results, lay, ext)
                                           + ([english("I_WHAT_IF", **what_if)] if label else []))
    reading, lines = si_view(project, res) if si(project) else (None, [*res.lines])
    name = path.absolute().parent.name  # `run .` too
    if reading is not None:
        files["si_summary.csv"], files["si_tdr.csv"] = si_csv(project, reading), tdr_csv(reading)
        files["si_summary.png"] = si_png([(name, reading)], project, render("I_PLOT_SI_TITLE", name=name), label)
    if not si(project) and res.chain is not None and p == 2:
        files["summary.csv"] = summary_csv(lay, res.chain, res.ideal, res.p_layout, results["loss_expected"])
        files["summary.png"] = summary_png(lay, res.chain, res.ideal, name, label)
    lines += [("I_WHAT_IF", what_if)] if label else []
    try:
        write(folder, files, SI_OUTPUTS if si(project) else OUTPUTS, command)
    except KrsError as err:  # E_RESULTS_WRITE: a file held open, say
        if not errors_as_lines:
            raise
        lines.append((err.code, err.params))
    else:
        lines.append(("I_OUTPUTS", {"files": ", ".join(sorted(files)), "folder": str(folder)}))
    return [*lines, *((code, {}) for code in (si_limits(project) if si(project) else LIMITS))]


def s11_at(path: Path, project: dict, f: np.ndarray, lay: Layout | None = None) -> tuple[np.ndarray, np.ndarray]:
    """S11 and the loss budget's P_layout (each (F,), in f's order) of the chain at the frequencies `f` (Hz): the run's
    layout there, every part port closed as chain_results closes it (scikit-rf takes f ascending). A given `lay` (the
    run's layout at f ascending, which the GUI's retune session holds, plan 5) stands in for it."""
    up = np.argsort(f)
    res = chain_results(path, project, lay=layout(project, project["results"], f[up]) if lay is None else lay)
    back = np.argsort(up)  # f's order again
    return res.chain[back, 0, 0], res.p_layout[back]


def current_verify(project: dict) -> dict | None:
    """project.json's verify block while it is of the model its results hold and its run folder still holds it (Stage 3
    design 5.7, 5.8): its base_hash the results' model_hash, and its model.json, its jobs' waves and, when it records a
    far field, its far-field files present; else None (none, another run's, or its folder moved or deleted); None
    without results either. The what-if η_tot and compare read verify through it."""
    v, results = project.get("verify"), project.get("results")
    if v is None or results is None or v["base_hash"] != results["model_hash"]:
        return None
    files = ["model.json", *(job["waves"] for job in v["jobs"]), *(v.get("far_field") or {}).values()]
    return v if all((Path(v["run_dir"]) / file).is_file() for file in files) else None


_UNREAD = object()  # antenna_lines' far field when its caller read none (None, read, is "none")


def antenna_lines(path: Path, project: dict, res: ChainResults, *, errors_as_lines: bool = False, far=_UNREAD,
                  far_lay: Layout | None = None) -> tuple[list[tuple[str, dict]], dict | None, Layout | None]:
    """An antenna's lines (Stage 3 design 5.5–5.7), no file written: what antenna_outputs reports before its label and
    files, and what the GUI shows on a read and on each retune: chain_results' `res` lines (I_BASIS up to the
    indicators); with a chain, s11_lines on its S11, then the run's far field's far_field_lines (results.far_field,
    M = 0), or with part ports eta_what_if_lines of a current verify's far field with this chain's P_layout at its
    frequencies (s11_at on `far_lay`, the run's layout there, ascending, built when None), else I_ANTENNA_NO_FAR_FIELD,
    which offers `verify`. `far` stands for that far field when given (None: there is none); else it is read (far_of;
    current_verify first with part ports). A KrsError on that read is raised, or, with `errors_as_lines`, the last line
    in place of those lines. Returns the lines, the far field they read (None without one) and, for the what-if, the
    layout at its frequencies."""
    lines = [*res.lines]
    run_far = bool(project["results"].get("far_field"))
    if res.chain is None:
        return lines, None, None
    lines += s11_lines(project, res.lay.f, res.chain[:, 0, 0])
    if not (run_far or res.refs):
        return lines, None, None
    try:  # the far field's whole read: a run or verify folder moved meanwhile is one line (ruling 9)
        if far is _UNREAD:
            record = project["results"] if run_far else current_verify(project)
            far = record and far_of(record, project)
        if run_far:
            lines += far_field_lines(far) if far else []
        elif far:
            # ponytail: η_rad from verify's ideal network (no package model), the network assumed not to radiate nor
            # to change the board's own loss; the line says what-if
            if far_lay is None:
                far_lay = layout(project, project["results"], np.sort(far["sphere"].f))
            lines += eta_what_if_lines(far, s11_at(path, project, far["sphere"].f, far_lay)[1])
        else:
            lines.append(("I_ANTENNA_NO_FAR_FIELD", {"command": command_line("kicad-rf-studio", "verify", str(path))}))
    except KrsError as err:  # far_of's, layout's or s11_at's E_RESULTS_WAVES
        if not errors_as_lines:
            raise
        lines.append((err.code, err.params))
        far = far_lay = None
    return lines, far, far_lay


def antenna_outputs(path: Path, project: dict, command: str, *,
                    errors_as_lines: bool = False) -> list[tuple[str, dict]]:
    """An antenna's outputs (Stage 3 design 5.5–5.7), which write_outputs writes for it, in run and retune alike: v1's
    layout.s{N}p, and chain.s1p when part ports are closed, with the what-if label as v1's; with results.far_field,
    farfield.csv and antenna_summary.csv, from the run's far field (antenna_lines reads it) and S11 at the sphere's
    frequencies (s11_at); and antenna_summary.png whenever there is a chain, with the run's far field (verify's, which
    the what-if η_tot reads, goes into no file, design 5.7) and the what-if label, rendered, as the last line of its
    title, as v1's summary.png; all written to results/ beside `path` (write, ANTENNA_OUTPUTS, with `command` as
    E_RESULTS_WRITE's advice). Returns the lines to report: antenna_lines' (I_BASIS up to the far field's lines), the
    label's line, then I_OUTPUTS and ANTENNA_LIMITS. Errors as write_outputs takes them, and antenna_lines'
    E_RESULTS_WAVES for the far field (a run or verify folder moved or deleted) is one more such line, in the place of
    the far field's lines and files."""
    res = chain_results(path, project, errors_as_lines=errors_as_lines)
    results, lay, ext = project["results"], res.lay, res.ext
    folder, n = path.parent / "results", len(lay.ports)
    files = {f"layout.s{n}p": touchstone(lay.s, lay.f, [q["name"] for q in lay.ports],
                                         port_map(project, results, lay, range(n)))}
    what_if = {"command": command_line("kicad-rf-studio", "verify", str(path))}
    label = render("I_WHAT_IF", **what_if) if res.what_if else None
    if res.chain is not None and res.refs:
        files["chain.s1p"] = touchstone(res.chain, lay.f, [lay.ports[k]["name"] for k in ext],
                                        port_map(project, results, lay, ext)
                                        + ([english("I_WHAT_IF", **what_if)] if res.what_if else []))
    lines, far, _ = antenna_lines(path, project, res, errors_as_lines=errors_as_lines)
    far = far if results.get("far_field") else None  # the run's alone goes into files: verify's never (design 5.7)
    if far:
        s11 = s11_at(path, project, far["sphere"].f)[0]
        files["farfield.csv"], files["antenna_summary.csv"] = farfield_csv(far), antenna_csv(far, s11)
    if res.chain is not None:
        files["antenna_summary.png"] = antenna_png(lay.f, res.chain[:, 0, 0], project, far,
                                                   path.absolute().parent.name, label)  # `run .` too
    lines += [("I_WHAT_IF", what_if)] if res.what_if else []
    try:
        write(folder, files, ANTENNA_OUTPUTS, command)
    except KrsError as err:  # E_RESULTS_WRITE: a file held open, say
        if not errors_as_lines:
            raise
        lines.append((err.code, err.params))
    else:
        lines.append(("I_OUTPUTS", {"files": ", ".join(sorted(files)), "folder": str(folder)}))
    return [*lines, *((code, {}) for code in ANTENNA_LIMITS)]


def run(path: Path, run_dir: Path | None = None) -> int:
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
    (C-24, C-29). W_GATE_LIMITS (an SI project's W_GATE_LIMITS_SI) follows the gate lines and each verdict when the
    gate limits are not default_gates' (C-10). STOP or Ctrl+C before the jobs start propagates as KeyboardInterrupt
    (exit 130, results untouched); once they run, it stops them, and their verdicts say so. An antenna's run (Stage 3)
    saves its results with far_field null and its settings fingerprint, taken before the jobs; with no part port it
    then transforms its far field and saves again, a transform that fails being an E_ line (_run); its outputs are
    antenna_outputs'. An SI run (Stage 4 design 5.6, 5.8, 5.12 item 2) saves no expected loss (null) but its route
    (si_route) and its settings fingerprint, both taken before the jobs, and its outputs are write_outputs' SI branch
    (Stage 4 design 5.6: its SI lines and files, and si_limits in LIMITS' place). A given `run_dir` stands in for the
    fresh run folder."""
    if not read_project(path)["ports"]:
        raise KrsError("E_NO_PORTS")
    return _locked(path, _run, run_dir)


def _locked(path: Path, body: Callable[[Path, Path], int], run_dir: Path | None = None) -> int:
    """The exit code of `body(path, run_dir)` under the project lock, in `run_dir`, else a fresh run folder, made
    either way, whose events.jsonl gets any KrsError as a message event, then exit 2: the lock contract that run and
    verify share."""
    run_dir = run_dir or runs.run_dir_for(path.absolute().parent.name)  # absolute: as in cost
    with runs.project_lock(path, run_dir, events=True):
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            return body(path, run_dir)
        except KrsError as err:
            runs.emit(run_dir, "message", err.code, err.params)
            return 2


def _run(path: Path, run_dir: Path) -> int:
    """run() under the lock, with `run_dir` made: an antenna run saves its S as v1 does, its results with far_field
    null and its settings fingerprint (fingerprint, Stage 3 design 5.8), taken before the jobs so that a failed
    openEMS probe costs no job, then, with no part port, transforms its far field after its job and saves again; a
    transform that fails is an E_ line, and one stopped leaves S kept (Stage 3 design 5.5). An SI run's results gain
    its route (si_route, Stage 4 design 5.6) and its settings fingerprint (Stage 4 design 5.8), both taken before the
    jobs; v1's and an antenna's gain no route."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    if isinstance(built := _model_phase(path, emit), int):
        return built
    project, board, geom, model = built
    gates, preset = project["gates"], project["preset"]
    # before prepare: an error here costs no job; design 5.6: v1's loss budget does not apply to SI
    loss = None if si(project) else expected_loss(geom, project["f0_hz"])
    route = si_route(board, geom, project) if si(project) else None
    fp = fingerprint(project) if antenna(project) or si(project) else None  # likewise a failed openEMS probe
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
    if antenna(project):
        data["results"]["far_field"] = None
        data["results"]["fingerprint"] = fp
    if si(project):
        data["results"] |= {"route": route, "fingerprint": fp}
    rerun = command_line("kicad-rf-studio", "run", str(path))
    rewrite = command_line("kicad-rf-studio", "retune", str(path))
    _save(path, data, rerun)
    emit("result", "I_RESULTS", {"kept": kept, "runs": len(done), "wall": duration(wall_s), "path": str(path)})
    lines = []
    if "nf2ff" in model.spec:  # an antenna with no part port
        # S's files first, their lines unsaid, so that a stopped transform leaves them
        write_outputs(path, data, rewrite, errors_as_lines=True)
        try:
            paths = far_field(run_dir / Path(done[0]["waves"]).parent, project["far_field"]["step_deg"])
            data["results"]["far_field"] = {grid: p.relative_to(run_dir).as_posix() for grid, p in paths.items()}
            _save(path, data, rerun)
        except KrsError as err:  # the transform's, or the save's E_RESULTS_WRITE: S kept, results/ as project.json says
            data["results"]["far_field"] = None
            lines.append((err.code, err.params))
    lines += write_outputs(path, data, rewrite, errors_as_lines=True)
    for code, params in lines:
        emit("message" if code.startswith("E_") else "result", code, params)
    return 2 if any(code.startswith("E_") for code, _ in lines) else 0


def _model_phase(path: Path, emit: Callable[..., None]) -> tuple[dict, Board, Geometry, Model] | int:
    """The model phase that run and verify share under the lock (spec 6.1, C-42): the project at `path`, its board,
    its geometry and its model, with W_FILLS_AS_SAVED and load()'s notes as message events through `emit` (runs.emit
    bound to the run folder). Instead the exit code where it stops: stops()'s, or 3 when a mesh gate blocks, its gates
    as verdict events followed by gate_lines against default_gates (C-10)."""
    project, board, geom, notes = load(path)
    for code, params in [("W_FILLS_AS_SAVED", {}), *notes]:
        emit("message", code, params)
    if stop := stops(notes):
        return stop
    model = build_model(project, board, geom)
    if model.blocked:
        for code, params in model.blocked:
            emit("verdict", code, params)
        for code, params in gate_lines(project["gates"], default_gates(project)):  # C-10
            emit("message", code, params)
        return 3
    return project, board, geom, model


def simulate(model: Model, project: dict, run_dir: Path) -> tuple[list[dict], dict, float] | None:
    """The job phase of a built `model` (one with a spec) in `run_dir`, which run and verify share (spec 6.1): prepare
    (small for an antenna, si for an SI project) and the setup gate, its blocking gates as verdict events and its
    warnings as message events, then gate_lines and None when it blocks; else I_GATES_PASSED (I_GATES_PASSED_PML for a
    spec with a boundary, whose gates include the absorber), gate_lines and the cost lines, then run_ports on every
    port of the model at the project's preset, and the per-job speed of the level it ran at refreshed in the
    calibration (D-16), except by an antenna's run (Stage 3 design 5.9) and by a run whose spec holds a Debye material
    (debye_cells, Stage 4 plan 4 ruling D-4). Returns (the jobs as project.json's results records them, setup.json, the
    job phase's wall time in s). STOP or Ctrl+C before the jobs start propagates as KeyboardInterrupt; once they run,
    it stops them, and their verdicts say so."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    gates, defaults = project["gates"], default_gates(project)
    threads, pool, per_job_mcs = prepare(model, partial(emit, "message"), run_dir, small=antenna(project),
                                         si=si(project))
    setup, blocked, warnings = setup_gate(model, project, run_dir, runs.load_settings(), threads)
    for code, params in blocked:
        emit("verdict", code, params, 0)
    for code, params in warnings:
        emit("message", code, params, 0)
    if blocked:
        for code, params in gate_lines(gates, defaults):  # C-10
            emit("message", code, params)
        return None
    emit("message", "I_GATES_PASSED_PML" if "boundary" in model.spec else "I_GATES_PASSED",
         {"dt": f"{setup['dt']:.4e}"})
    for code, params in gate_lines(gates, defaults):
        emit("message", code, params)
    for code, params in cost_notes(model, project, setup, threads, pool, per_job_mcs):
        emit("cost", code, params)
    done, speeds, wall_s = run_ports(model, run_dir, setup, threads, pool, project["preset"], gates,
                                     defaults=defaults)
    # spec 6.4: refreshed from the run's Speed lines; a run whose every job died measured nothing; and an antenna's
    # speed holds the PML and the small model, which cost applies to the calibration's own (Stage 3 design 5.9); a
    # Debye cell's speed is no plain one's: a run with Debye refreshes no level (Stage 4 plan 4 ruling D-4)
    if speeds and not antenna(project) and not debye_cells(model.spec):
        settings = runs.load_settings()
        # D-16: only the level this run used; aggregate_mcs stays the calibration's
        settings["machines"][runs.machine_key()].setdefault("levels", {})[str(pool)] = sum(speeds) / len(speeds) / 1e6
        runs.save_settings(settings)
    return done, setup, wall_s


def run_ports(model: Model, run_dir: Path, setup: dict, threads: int, pool: int, preset: str, gates: dict,
              ports: list[int] | None = None, t_max: float | None = None,
              defaults: dict = GATES) -> tuple[list[dict], list[float], float]:
    """The jobs of a built `model` in `run_dir` once its setup gate passed (`setup`: setup.json), which simulate and
    the P0 harnesses share (spec 6.1): I_RUN_START; one job job-{k}-{name} per port number k in `ports` (1-based,
    default every port) to `t_max` (default the spec's ceiling: an SI job's openEMS runs to RING_CEILING × T_max, and
    the stop rule ends it at T_max unless its residual falls fast enough, Stage 4 plan 4 ruling T-2), `pool` at once
    with `threads` threads each under the stop rule at `preset`, with I_PROGRESS as its energy log grows; each job's
    verdict (classify_job) followed by gate_lines(`gates`, `defaults`), then its excitation arrays et and ht removed
    (D-17), the run folder itself kept (C-23). The residuals I_PROGRESS and a verdict without a cut report are
    last_sample's over the stop rule's window, an SI pulse's window_s.
    Returns (the jobs as project.json's results record them, openEMS's speed in cells/s of each job that wrote its
    stats, the job phase's wall time in s). STOP or Ctrl+C stops the jobs, and their verdicts say so."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    names, exc, dt = [q["name"] for q in model.spec["ports"]], model.spec["excitation"], setup["dt"]
    ports = range(1, len(names) + 1) if ports is None else ports
    t_max = ceiling(exc) if t_max is None else t_max
    jobs = {runs.write_job(runs.job_dir(run_dir, k, names[k - 1]), k, "run", threads, t_max): k for k in ports}
    live, rows = {}, {}  # each job's live verdict, and the energy rows its last I_PROGRESS saw

    def watch(job: Path) -> bool:
        """Whether the stop rule has a verdict on `job`; I_PROGRESS when its energy log has a new row."""
        k = jobs[job]
        rec = records(job, len(names), dt)
        live[job] = stop_rule(rec, k - 1, preset, exc)
        if len(rec.e) > rows.get(job, 0) and len(rec.t_u):
            rows[job] = len(rec.e)
            t, r = last_sample(rec, exc.get("window_s", WINDOW_S))
            speed = read_run_stats((job / "openEMS_run_stats.txt").read_text(encoding="utf-8"))[1][-1]
            emit("progress", "I_PROGRESS", {"port": names[k - 1], "t_ns": f"{t * 1e9:.2f}", "residual_db": f"{r:.1f}",
                                            "speed_mcs": f"{speed / 1e6:.1f}"}, k)
        return live[job] is not None

    emit("message", "I_RUN_START", {"runs": len(jobs), "pool": pool, "folder": str(run_dir)})
    start = time.monotonic()
    out = runs.run_jobs(list(jobs), pool, run_dir, runs.load_settings(), watch)
    wall_s = time.monotonic() - start

    done, speeds = [], []  # each job's results, and openEMS's speed (cells/s) of each job that wrote its stats
    for job, k in jobs.items():
        rec = records(job, len(names), dt)
        kind, verdict = classify_job(job, out[job], live.get(job), rec, k, preset, exc)
        t_stop, r_last = last_sample(rec, exc.get("window_s", WINDOW_S))
        t, r = (verdict.t, verdict.residual_db) if verdict else (t_stop, r_last)
        r = r if r is not None and math.isfinite(r) else None  # a diverged job's NaN is no residual, nor in JSON
        emit("verdict", VERDICTS[kind], {"port": names[k - 1], "t_ns": None if t is None else f"{t * 1e9:.2f}",
                                         "residual_db": None if r is None else f"{r:.1f}", "log": str(job / LOG)}, k)
        for code, params in gate_lines(gates, defaults):
            emit("message", code, params)
        for array in ("et", "ht"):  # up to 32 MB a job, and nothing reads them
            with contextlib.suppress(OSError):  # Windows: an antivirus or the indexer may still hold it; it stays
                (job / array).unlink(missing_ok=True)
        waves = f"{job.name}/waves.npz"
        done.append({"port": names[k - 1], "verdict": kind, "t_cut": verdict.t if verdict else None, "t_stop": t_stop,
                     "residual_db": r, "waves": waves if (run_dir / waves).is_file() else None})
        if (stats := job / "openEMS_stats.txt").is_file() and (s := read_stats(stats.read_text(encoding="utf-8"))):
            speeds.append(s["speed"])  # a killed or crashed job has none, or a part of one
    return done, speeds, wall_s


def far_field(job: Path, step_deg: int = 5) -> dict[str, Path]:
    """The far-field transform (Stage 3 design 5.5) of the finished job in folder `job`, whose model spec records a far
    field. One worker in mode "nf2ff", in a folder of its own beside the job (job-0-nf2ff-<token>, a new
    `secrets.token_hex(4)` at each call), reads the job's dumps and writes <job>/nf2ff-<token>-<grid>.h5 for each of
    worker.GRIDS, the sphere at `step_deg`, so a second transform never reads or overwrites the first's. Returns those
    paths by grid. Raises what check_job raises, naming the job T_JOB_FAR_FIELD."""
    finished = json.loads((job / "job.json").read_text(encoding="utf-8"))
    token, settings = secrets.token_hex(4), runs.load_settings()
    work = runs.write_job(runs.job_dir(job.parent, 0, f"nf2ff-{token}"), finished["port"], "nf2ff", 1,
                          finished["t_max"], dumps=f"../{job.name}", out=f"nf2ff-{token}", step_deg=step_deg)
    out = runs.run_jobs([work], 1, job.parent, settings)
    runs.check_job(work, out[work], "T_JOB_FAR_FIELD", settings)
    return {grid: job / f"nf2ff-{token}-{grid}.h5" for grid in GRIDS}


def far_of(record: dict, project: dict | None = None) -> dict | None:
    """far_field_of of the run `record` holds, project.json's results or its verify (Stage 3 design 5.5): its far_field
    files and its first job's waves, in its run_dir, and, with `project`, its far_field.f_hz, to which far_field_of
    snaps the recorded frequencies; None when it records no far field. Raises far_field_of's E_RESULTS_WAVES."""
    if not record.get("far_field"):
        return None
    run_dir = Path(record["run_dir"])
    return far_field_of({grid: run_dir / file for grid, file in record["far_field"].items()},
                        run_dir / record["jobs"][0]["waves"], project["far_field"]["f_hz"] if project else ())


def results_of(project: dict, model: Model) -> dict:
    """The results in `project` when they are the last run's of `model` (spec 7.8, C-22, C-23): E_NO_RESULTS without
    any; E_RESULTS_STALE when the model has no spec (E_EDGE_LINT), its spec_hash is not the one the run recorded, or
    the run recorded no loss_expected or, in an SI project, no route (Stage 4 design 5.6): a run before this version."""
    # ponytail: rebuilds the model (1.2–3.2 s on lpf915) to compare hashes; Stage 2 may cache it
    if "results" not in project:
        raise KrsError("E_NO_RESULTS")
    results = project["results"]
    if (model.spec is None or spec_hash(model.spec) != results.get("model_hash") or "loss_expected" not in results
            or si(project) and "route" not in results):
        raise KrsError("E_RESULTS_STALE")
    return results


def fingerprint(project: dict) -> dict:
    """An antenna's settings fingerprint (Stage 3 design 5.8), recorded with each run's and verify's results:
    project.json's fields that set the model or the far field but no part value, the lid height and the start pad among
    them (typed per project, not in the board); the copper model (copper_model); the flat window "flat_s" only when
    project.json sets it, so that the records made before it still compare; and the versions of this app and of
    openEMS as a worker sees it (runs.openems_versions: metadata in an isolated subprocess, nothing imported). An SI
    project's (Stage 4 design 5.8): its preset, region, interface, f_max_hz, rise_s, marker_hz, target_ohm, stackup,
    dielectric, lid and lid_height_mm, its mesh without max_cell_mm's value but with "d_fill", whether it is null (the d
    fill, gate P4-C), so a d-fill run never compares with a set cell's; "ends" (its external ports' signal pads, in
    order, so two projects of other lines or victims never compare) and the versions; t_max_s and window_s, the stop
    window, stay out, as they follow the lines' 2D εeff and length, which a variant may change."""
    if si(project):
        # ponytail: max_cell_mm's value out, so a hand-edited coarser cell compares too; whether it is null in, as the
        # d fill and a set cell differ by more than the thresholds (gate P4-C); a recorded factor if users edit it
        keys = ("preset", "region", "interface", "f_max_hz", "rise_s", "marker_hz", "target_ohm", "stackup",
                "dielectric", "lid", "lid_height_mm")
        return {**{key: project[key] for key in keys},
                "mesh": {**{key: v for key, v in project["mesh"].items() if key != "max_cell_mm"},
                         "d_fill": project["mesh"].get("max_cell_mm") is None},
                "ends": [q["signal"] for q in project["ports"]], "app": __version__,
                "openems": runs.openems_versions()[0]}
    keys = ("preset", "mesh", "region", "band", "f0_hz", "t_max_s", "air_gap_mm", "boundary", "far_field", "stackup",
            "lid_height_mm")
    flat = {"flat_s": project["flat_s"]} if "flat_s" in project else {}
    return {**{key: project[key] for key in keys}, "start": project["chain"]["start"], "copper": copper_model(project),
            **flat, "app": __version__, "openems": runs.openems_versions()[0]}


def assign(project: dict, assignments: list[str], folder: Path) -> dict:
    """A deep copy of `project` with each assignment "REF=RIGHT" stored, split at the first "=" (C-17, C-18): a RIGHT
    FILE:series or FILE:shunt sets the part's s2p to FILE, as relative_path stores it against `folder` (a relative
    FILE is read from the working directory, as `new` reads BOARD), its value and model kept; any other RIGHT is
    stored verbatim as its value, its s2p None, when port_value reads it (so a C of 0 is refused). Refusals, the first
    in argument order: E_RETUNE_ARG (no "="), E_RETUNE_TWICE, E_RETUNE_UNKNOWN (no such part; it names the retunable
    ones, in project order), E_RETUNE_ROLE (copper, open or grid), E_RETUNE_VALUE. For an antenna (Stage 3 design
    5.7) or an SI project (Stage 4 design 5.7), a RIGHT that values.bypass reads is stored as typed too: 0 Ω on a
    series part or on a part across two chain nets, open on a shunt part, an SI project's chain being its lines merged
    (chain_of); E_RETUNE_SHORT_SHUNT (0 Ω to a net off the chain) and E_RETUNE_OPEN_SERIES refuse the converse, and
    E_RETUNE_ANTENNA_VALUE, which names the bypass syntax, stands for E_RETUNE_VALUE."""
    # ponytail: a file on another drive is stored absolute without a warning; a moved project then meets E_S2P_MISSING
    new = copy.deepcopy(project)
    by_ref, seen, bypasses = parts(new), set(), antenna(new) or si(new)
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
        elif bypasses and (z := bypass(ref, right)) is not None:
            # ponytail: the tracer's shunt list decides: a series part beside a parallel one is still refused open; a
            # shunt 0R the board itself holds keeps its 0 Ω, so verify then meets E_PORT_SHORT; start it open in new
            # if a board ships one
            chain = chain_of(new)
            if z == 0 and ref in {q.ref for q in chain.shunt} and not set(part["nets"]) <= set(chain.nets):
                raise KrsError("E_RETUNE_SHORT_SHUNT", ref=ref, net=part["nets"][1])
            if z == math.inf and ref in {q.ref for q in chain.series}:
                raise KrsError("E_RETUNE_OPEN_SERIES", ref=ref)
            part["value"], part["s2p"] = right, None
        elif port_value(ref, right) is None:
            raise KrsError("E_RETUNE_ANTENNA_VALUE" if bypasses else "E_RETUNE_VALUE", ref=ref, value=right)
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
    one raises before anything is stored (C-20). An SI project's retune (Stage 4 design 5.7) redraws its TDRs, its
    mixed-mode S and its crosstalk from the N-port closed at the new values, an S2P file read from the grid's first
    point above DC."""
    read_project(path)  # before the lock, as in run: its file needs the project's folder, which a typo lacks
    # ponytail: results/ stands in for the lock's run folder, so E_LOCKED names results/ while a retune holds the lock
    with runs.project_lock(path, path.resolve().parent / "results"):
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


def _full_record(path: Path) -> tuple[dict, dict, Layout, str]:
    """The full simulation `compare` reads of the project at `path` (Stage 3 and Stage 4 design 5.8), whatever its
    kind: its results checked against its current model as retune checks them (load, build_model, results_of: Stage 1
    7.8); with no part port on its chain or lines, its run (results); with part ports, its current verify
    (current_verify) when that verify's values are, as text, the part ports' values project.json holds; and that
    record's layout. Returns (project, record, layout, source: T_RUN or T_VERIFY). E_COMPARE_NO_RESULT {path} for no
    results or stale ones (results_of's E_NO_RESULTS and E_RESULTS_STALE, the model built outside that catch), no such
    record, one with no fingerprint (made before this version), or a record whose files are gone (layout's
    E_RESULTS_WAVES). It starts no worker."""
    project, board, geom, _ = load(path)
    model = build_model(project, board, geom)
    try:
        results = results_of(project, model)
    except KrsError:  # E_NO_RESULTS or E_RESULTS_STALE
        raise KrsError("E_COMPARE_NO_RESULT", path=str(path)) from None
    values = {ref: q["value"] for ref, q in parts(project).items() if q["role"] in (PORT, CURVE_PORT)}
    if not values:
        record, source = results, "T_RUN"
    else:
        # ponytail: values compared as text, so 4p7 and 4.7pF read as different; port_value equality if users trip on it
        # ponytail: verify's parts are ideal at their stored values (C-38), so an S2P file applied to a part is not what
        # compare compares, and a chain part off 90° (E_VERIFY_CURVE) leaves its project nothing to compare
        record, source = current_verify(project), "T_VERIFY"
        if record is not None and record["values"] != values:
            record = None
    if record is None or "fingerprint" not in record:
        raise KrsError("E_COMPARE_NO_RESULT", path=str(path))
    try:  # a run folder moved or deleted since: nothing compare can use, as a deleted verify folder
        lay = layout(project, record)
    except KrsError as err:
        if err.code != "E_RESULTS_WAVES":
            raise
        raise KrsError("E_COMPARE_NO_RESULT", path=str(path)) from None
    return project, record, lay, source


def antenna_result(path: Path) -> dict:
    """The full simulation `compare` reads of the project at `path` (Stage 3 design 5.8): E_COMPARE_KIND {path} for a
    project that is not an antenna's (read_project, before any board is read); then its results checked against its
    current model as retune checks them (load, build_model, results_of: Stage 1 7.8); with no part port on its chain,
    its run (results); with part ports, its current verify (current_verify) when that verify's values are, as text,
    the part ports' values project.json holds. Its S11 on the band grid (that record's one-port layout), its far field
    (far_of, None without one), its fingerprint, its source (T_RUN or T_VERIFY) and its run folder.
    E_COMPARE_NO_RESULT {path} for no results or stale ones (results_of's E_NO_RESULTS and E_RESULTS_STALE, the model
    built outside that catch), no such record, one with no fingerprint (made before this version), or a record whose
    files are gone (layout's or far_of's E_RESULTS_WAVES). It starts no worker."""
    if not antenna(read_project(path)):
        raise KrsError("E_COMPARE_KIND", path=str(path))
    project, record, lay, source = _full_record(path)
    try:  # a run folder moved or deleted since, as in _full_record
        far = far_of(record, project)
    except KrsError as err:
        if err.code != "E_RESULTS_WAVES":
            raise
        raise KrsError("E_COMPARE_NO_RESULT", path=str(path)) from None
    return {"path": path, "project": project, "f": lay.f, "s11": lay.s[:, 0, 0], "far": far,
            "fingerprint": record["fingerprint"], "source": source, "run_dir": record["run_dir"]}


# an SI reading's settings that no model spec holds: read at project.json's current values, as Results reads them
# (A-67); the tolerance is left out, since no delta reads it and compare.png draws the base's band alone
SI_READ_AT = ("target_ohm", "marker_hz", "rise_s")


def si_result(path: Path) -> dict:
    """The full simulation `compare` reads of the SI project at `path` (Stage 4 design 5.8): _full_record's run or
    current verify, read (read, at the run's route's εeff) from that record's layout, which is the chain itself:
    verify's layout holds its external ports alone, its parts in the grid, and the run's at M = 0 its chain. Its
    reading, fingerprint, source (T_RUN or T_VERIFY) and run folder. Its fingerprint holds project.json's current
    SI_READ_AT, which it reads at, over the record's, so two projects edited alike compare at those values and two
    edited apart are refused (E_COMPARE_SETTINGS). No kind check of its own: compare_projects, its one caller, checks
    both projects' kinds first. Raises _full_record's E_COMPARE_NO_RESULT. It starts no worker."""
    project, record, lay, source = _full_record(path)
    return {"path": path, "project": project,
            "reading": read(lay.s, lay.f, project, project["results"]["route"]["eeff"]),
            "fingerprint": {**record["fingerprint"], **{key: project[key] for key in SI_READ_AT}},
            "source": source, "run_dir": record["run_dir"]}


def compare_projects(base: Path, variant: Path, output: Path | None = None,
                     emit: Callable[[str, dict], None] | None = None) -> int:
    """`compare BASE VARIANT` (Stage 3 design 5.8, Stage 4 design 5.8) on two antenna projects or two SI projects,
    returning its exit code: first, before any board is read, each project's kind, E_COMPARE_KIND {path} for the
    first, base then variant, that is not of the base's kind, an antenna or an SI project (a base of neither refused as
    not an antenna); then each project's result (antenna_result or si_result, the base's first); E_COMPARE_SETTINGS
    {fields}, the differing fingerprint keys sorted and joined by ", ", when their fingerprints differ; then
    compare.csv (deltas_csv of deltas, or of si_deltas) and compare.png (compare_png, or si_png of both readings under
    I_PLOT_SI_COMPARE_TITLE, each curve named by its project's folder, path.absolute().parent.name) written to
    `output`, the working folder (Path.cwd()) when None (write, COMPARE_OUTPUTS, E_RESULTS_WRITE advising this command
    with -o); then `emit(code, params)` for each line, which prints it by default, as retune's: I_ANTENNA_RELATIVE
    (I_SI_RELATIVE), I_COMPARE_BASIS {role, path, source, run_dir} for the base then the variant, delta_lines
    (si_delta_lines), I_OUTPUTS, ANTENNA_LIMITS (the base's si_limits); and 0. A refused write is an E_ line in
    I_OUTPUTS' place, the other lines still printed (Stage 1 7.5), and 2. It starts no worker; a refusal before the
    write writes nothing."""
    is_si = si(read_project(base))  # a base of neither kind fails the antenna's check, as before
    for path in (base, variant):
        data = read_project(path)
        if not (si(data) if is_si else antenna(data)):
            raise KrsError("E_COMPARE_KIND", path=str(path))
    result = si_result if is_si else antenna_result
    b, v = result(base), result(variant)
    keys = b["fingerprint"].keys() | v["fingerprint"].keys()
    if fields := sorted(key for key in keys if b["fingerprint"].get(key) != v["fingerprint"].get(key)):
        raise KrsError("E_COMPARE_SETTINGS", fields=", ".join(fields))
    folder = output or Path.cwd()
    names = [r["path"].absolute().parent.name for r in (b, v)]  # `compare . ../b` too
    # the base's project: its band, f0 and far field, or its grid and lines, the variant shares by the fingerprint
    if is_si:
        rows = si_deltas(b["project"], b["reading"], v["reading"])
        png = si_png([(names[0], b["reading"]), (names[1], v["reading"])], b["project"],
                     render("I_PLOT_SI_COMPARE_TITLE", base=names[0], variant=names[1]))
        label, shown, limits = "I_SI_RELATIVE", si_delta_lines(b["project"], rows), si_limits(b["project"])
    else:
        rows = deltas(b["project"], b["f"], (b["s11"], b["far"]), (v["s11"], v["far"]))
        png = compare_png(b["f"], [(name, r["s11"], r["far"]) for name, r in zip(names, (b, v))], b["project"])
        label, shown, limits = "I_ANTENNA_RELATIVE", delta_lines(b["project"], rows), ANTENNA_LIMITS
    files = {"compare.csv": deltas_csv(rows), "compare.png": png}
    lines = [(label, {}),
             *(("I_COMPARE_BASIS", {"role": role, "path": str(r["path"]), "source": r["source"],
                                    "run_dir": r["run_dir"]}) for role, r in (("T_BASE", b), ("T_VARIANT", v))),
             *shown]
    try:
        write(folder, files, COMPARE_OUTPUTS,
              command_line("kicad-rf-studio", "compare", str(base), str(variant), "-o", str(folder)))
    except KrsError as err:  # E_RESULTS_WRITE: a viewer holds compare.png, say
        lines.append((err.code, err.params))
    else:
        lines.append(("I_OUTPUTS", {"files": ", ".join(sorted(files)), "folder": str(folder)}))
    emit = emit or (lambda code, params: print(render(code, **params)))
    for code, params in [*lines, *((code, {}) for code in limits)]:
        emit(code, params)
    return 2 if any(code.startswith("E_") for code, _ in lines) else 0


def verify(path: Path, run_dir: Path | None = None) -> int:
    """`verify` on the project at `path` (spec 3.2, 7.6, C-36..C-38), returning its exit code as run does (C-22).
    Before the lock: E_VERIFY_NO_PARTS when no part is a port or a curve_port (a single trace), E_VERIFY_CURVE for the
    first curve_port, E_NO_RESULTS, E_VERIFY_PORTS for fewer than 2 external ports, an antenna's one external port
    excepted (Stage 3 design 5.7). Then as in run, under the lock in a fresh run folder whose events.jsonl gets every
    line, with any KrsError a message event and exit 2: W_FILLS_AS_SAVED and load()'s notes, stopping with stops(); the
    model, 3 when a mesh gate blocks; results_of and the run's layout N-port; verify's model (verify_spec) and the part
    ports' loads at their ideal values, the part models and S2P files ignored (C-38), every refusal before any job. Then
    simulate on verify's model, its external ports the only jobs: 3 when its setup gate blocks, and unless every job
    kept S, W_VERIFY_NOT_KEPT and 4 with nothing stored. Else verify's own N-port is compared with the run's closed by
    those loads, the noisier of the run's and the project's presets setting the null floor; the comparison goes to
    project.json's verify (its results kept), then verify.s{P}p to results/ with its port map and grid lines, a refusal
    of either an E_ line, so that a held file costs only that file. The lines follow: I_VERIFY_RESULTS when the
    comparison was stored, I_VERIFY_COMPARE, I_VERIFY_NULL or W_VERIFY_NULL_UNMATCHED for each null (I_VERIFY_NO_NULLS
    for none), the indicator lines with a 2-port's loss budget in its verify form (the parts in the grid, no part loss
    removed), the E_ lines as message events, I_OUTPUTS when verify.s{P}p was written, I_VERIFY_SCOPE and LIMITS; then
    0, or 2 after an E_ line. A given `run_dir` stands in for the fresh run folder. An SI project's verify is v1's with
    SI's comparison (Stage 4 design 5.7)."""
    project = read_project(path)  # before the lock, as in run
    by_ref = parts(project)
    if not any(q["role"] in (PORT, CURVE_PORT) for q in by_ref.values()):
        raise KrsError("E_VERIFY_NO_PARTS")
    if curve := next((ref for ref, q in by_ref.items() if q["role"] == CURVE_PORT), None):
        raise KrsError("E_VERIFY_CURVE", ref=curve)
    if "results" not in project:
        raise KrsError("E_NO_RESULTS")
    # the external ports, as _split counts them; compare() reads S21 and S11, compare_s11 an antenna's S11 alone
    if len(project["ports"]) < 2 and not antenna(project):
        raise KrsError("E_VERIFY_PORTS", ports=len(project["ports"]))
    return _locked(path, _verify, run_dir)


def _verify(path: Path, run_dir: Path) -> int:
    """verify() under the lock, with `run_dir` made; an antenna's verify model records its far field (far_field_box),
    its loads read its bypasses, and _verify_antenna ends it (Stage 3 design 5.5–5.7). An SI project's (Stage 4 design
    5.7) is v1's with the antenna's bypasses (verify_spec's and the loads'), each load evaluated on above_dc(lay.f) as
    chain_results' are, its settings fingerprint taken before the jobs and stored in its verify block, and SI's
    comparison, compare_verify of verify's own reading and the retune's (read at the run's route's εeff), in place of
    compare. Its lines after I_VERIFY_RESULTS: verify's own si_lines, I_VERIFY_COMPARE_SI, then I_VERIFY_LEVEL or
    I_VERIFY_LEVEL_SHORT per level or one I_VERIFY_NO_LEVELS, in place of I_VERIFY_COMPARE and the nulls; the indicator
    lines with no loss budget; the E_ lines; I_OUTPUTS; I_VERIFY_SCOPE_SI and si_limits in place of I_VERIFY_SCOPE and
    LIMITS. v1's lines and files are unchanged."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    if isinstance(built := _model_phase(path, emit), int):
        return built
    project, board, geom, model = built
    ant = antenna(project)
    results = results_of(project, model)
    lay = layout(project, results)
    by_ref, (ext, refs) = parts(project), _split(lay)
    values = {ref: by_ref[ref]["value"] for ref in refs}
    dump = runs.job_dir(Path(results["run_dir"]), 0, "setup") / "operator_dump.vtr"
    vspec = verify_spec(model.spec, by_ref, dump, results["dt"],
                        far_field=far_field_box(project, board, geom) if ant else None, bypasses=si(project))
    fz = above_dc(lay.f)  # the loads' grid, as chain_results': lay.f itself off DC (v1's, an antenna's)
    zk = loads({ref: z_value(ref, values[ref], None, fz, bypasses=ant or si(project)) for ref in refs}, refs,
               results["c_box"], fz)  # the ideal values, the part models and S2P files ignored (C-38)
    fp = fingerprint(project) if ant or si(project) else None  # as every refusal, before any job
    if (out := simulate(replace(model, spec=vspec), project, run_dir)) is None:
        return 3
    done, _, wall_s = out
    kept = sum(j["verdict"] in KEPT for j in done)
    if kept < len(done):  # nothing compared or stored
        emit("result", "W_VERIFY_NOT_KEPT", {"kept": kept, "runs": len(done), "wall": duration(wall_s),
                                             "folder": str(run_dir)})
        return 4
    own = layout(project, {"run_dir": str(run_dir), "jobs": done})
    retuned = terminate(lay.s, ext, zk, lay.f)  # the retune at the same ideal values
    if ant:
        return _verify_antenna(path, run_dir, project, vspec, values, own, retuned[:, 0, 0], done, wall_s, fp)
    k0, p = lay.markers[0], len(own.ports)
    if si(project):
        mine = read(own.s, own.f, project, results["route"]["eeff"])
        cmp = compare_verify(mine, read(retuned, lay.f, project, results["route"]["eeff"]))
    else:
        # 10 × the S tolerance of the noisier preset, the run's or verify's own
        floor = 10 * max(PRESETS[results["preset"]][1], PRESETS[project["preset"]][1])
        cmp = compare(own.s, retuned, lay.f, k0, floor)
    command = command_line("kicad-rf-studio", "verify", str(path))
    # the comparison is stored first, then verify.s{P}p written; a refusal of either is a line, so the comparison is
    # still printed and a held file costs only that file
    lines, errors, outputs = [], [], []
    try:
        data = load_project(path)  # as it is now: only verify is replaced
        data["verify"] = {"model_hash": spec_hash(vspec), "base_hash": results["model_hash"], "values": values,
                          "run_dir": str(run_dir), "jobs": done, "compare": cmp,
                          **({"fingerprint": fp} if si(project) else {})}  # v1's keeps its six keys
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
    if si(project):
        k = np.abs(own.f - cmp["f_hz"]).argmin()  # the grid point of the largest |ΔS|
        lines += [*si_lines(project, mine, results["route"]),
                  ("I_VERIFY_COMPARE_SI", {"ds_max": f"{cmp['ds_max']:.4f}", "f_mhz": f"{cmp['f_hz'] / 1e6:g}",
                                           "a_db": f"{own.a_db[k]:.1f}"})]
        for level, (z, z_retune, short) in zip(("T_LOWEST", "T_HIGHEST"), cmp["levels"] or ()):
            lines.append(("I_VERIFY_LEVEL_SHORT" if short else "I_VERIFY_LEVEL",
                          {"level": level, "verify": f"{z:.2f}", "retune": f"{z_retune:.2f}"}))
        if cmp["levels"] is None:
            lines.append(("I_VERIFY_NO_LEVELS", {}))
        lines += indicator_lines(own.f, own.a_db, own.s, None, None)
        scope, limits = "I_VERIFY_SCOPE_SI", si_limits(project)
    else:
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
        lines += indicator_lines(own.f, own.a_db, own.s, p_layout, results["loss_expected"], in_grid=True)
        scope, limits = "I_VERIFY_SCOPE", LIMITS
    lines += [*errors, *outputs, (scope, {}), *((code, {}) for code in limits)]
    for code, params in lines:
        emit("message" if code.startswith("E_") else "result", code, params)
    return 2 if errors else 0


def _verify_antenna(path: Path, run_dir: Path, project: dict, vspec: dict, values: dict[str, str], own: Layout,
                    retuned: np.ndarray, done: list[dict], wall_s: float, fp: dict) -> int:
    """_verify's end for an antenna (Stage 3 design 5.5–5.7), with `own` verify's one-port layout and `retuned` the
    retune's S11 at the same ideal values; `results` is project["results"], as results_of checked it. The comparison
    (compare_s11, k0 own's f0 marker) is stored in project.json's verify with far_field null and `fp`, the settings
    fingerprint _verify took before the jobs (fingerprint(project): a failed openEMS probe costs no job), and
    I_VERIFY_RESULTS emitted at once, as _run emits I_RESULTS before its transform. Then verify.s1p (port_map and
    grid_lines, as v1's) and verify_summary.png without a far field are written (ANTENNA_VERIFY_OUTPUTS), so that a
    stopped transform leaves them, as it leaves a run's S. Only when the comparison was stored, the far field is
    transformed from verify's job (far_field, the project's step), stored and read back (far_of), and all four files
    written again with it, S11 at the far field's frequencies from verify's own layout there (no part port: layout
    gives it in any order). That second write supersedes the first, whose refusal is said only when no second write
    follows. A refusal of a store, a write or the transform is an E_ line; a stopped transform propagates, the
    comparison stored and verify's S file kept. The lines after I_VERIFY_RESULTS: s11_lines of verify's S11,
    I_VERIFY_COMPARE_S11, I_VERIFY_SHIFT or I_RESONANCE_NOT_COMPARED, far_field_lines, indicator_lines with no loss
    budget, the E_ lines, I_OUTPUTS naming the files of the write that stands when it succeeded,
    I_VERIFY_SCOPE_ANTENNA and ANTENNA_LIMITS; each emitted as v1's are; 0, or 2 after an E_ line."""
    emit = partial(runs.emit, run_dir)  # (kind, code, params, job=None)
    results, k0, s11 = project["results"], own.markers[0], own.s[:, 0, 0]
    cmp = compare_s11(s11, retuned, own.f, k0)
    command = command_line("kicad-rf-studio", "verify", str(path))
    errors = []  # the store's and the transform's refusals
    try:
        data = load_project(path)  # as it is now: only verify is replaced
        data["verify"] = {"model_hash": spec_hash(vspec), "base_hash": results["model_hash"], "values": values,
                          "run_dir": str(run_dir), "jobs": done, "compare": cmp, "far_field": None,
                          "fingerprint": fp}
        _save(path, data, command)
    except KrsError as err:  # E_RESULTS_WRITE for project.json, or E_PROJECT_UNREADABLE after a hand edit meanwhile
        errors.append((err.code, err.params))
        data = None
    else:
        emit("result", "I_VERIFY_RESULTS", {"runs": len(done), "wall": duration(wall_s), "path": str(path)})
    folder, name = path.parent / "results", path.absolute().parent.name  # `verify .` too
    basis = {**results, "run_dir": str(run_dir), "jobs": done, "preset": project["preset"]}
    # ponytail: verify.s1p's grid lines name the grid parts only; a bypassed part is in project.json's verify.values
    comments = port_map(project, basis, own, [0]) + grid_lines(vspec["grid"], values)
    files = {"verify.s1p": touchstone(own.s, own.f, [q["name"] for q in own.ports], comments),
             "verify_summary.png": antenna_png(own.f, s11, project, None, name)}  # no label: verify is no what-if

    def write_files() -> tuple[str, dict]:
        """`files` written into results/: I_OUTPUTS naming them, else write's E_RESULTS_WRITE (a file held open)."""
        try:
            write(folder, files, ANTENNA_VERIFY_OUTPUTS, command)
        except KrsError as err:
            return err.code, err.params
        return "I_OUTPUTS", {"files": ", ".join(sorted(files)), "folder": str(folder)}

    written, far = write_files(), None
    if data is not None:  # with project.json refused, the far field could not be recorded
        try:
            paths = far_field(run_dir / Path(done[0]["waves"]).parent, project["far_field"]["step_deg"])
            data["verify"]["far_field"] = {grid: p.relative_to(run_dir).as_posix() for grid, p in paths.items()}
            _save(path, data, command)
            far = far_of(data["verify"], project)
        except KrsError as err:  # the transform's, the save's or far_of's: the first write stands
            errors.append((err.code, err.params))
        else:
            files["verify_farfield.csv"] = farfield_csv(far)
            files["verify_summary.csv"] = antenna_csv(far, layout(project, basis, far["sphere"].f).s[:, 0, 0])
            files["verify_summary.png"] = antenna_png(own.f, s11, project, far, name)
            written = write_files()  # supersedes the first write
    if cmp["shift"] is None:
        dip_line = ("I_RESONANCE_NOT_COMPARED", {})
    else:
        dip_line = ("I_VERIFY_SHIFT", {"f_res_mhz": f"{cmp['f_res_hz'] / 1e6:.1f}",
                                       "f_res_retune_mhz": f"{cmp['f_res_retune_hz'] / 1e6:.1f}",
                                       "shift_pct": f"{100 * cmp['shift']:+.2f}"})
    lines = [*s11_lines(project, own.f, s11),
             ("I_VERIFY_COMPARE_S11", {"f0_mhz": f"{own.f[k0] / 1e6:g}", "a_db": f"{own.a_db[k0]:.1f}",
                                       "ds11": f"{cmp['ds11_f0']:.4f}", "ds11_max": f"{cmp['ds11_max']:.4f}"}),
             dip_line, *(far_field_lines(far) if far else ()),
             *indicator_lines(own.f, own.a_db, own.s, None, results["loss_expected"]),
             *errors, written, ("I_VERIFY_SCOPE_ANTENNA", {}), *((code, {}) for code in ANTENNA_LIMITS)]
    for code, params in lines:
        emit("message" if code.startswith("E_") else "result", code, params)
    return 2 if any(code.startswith("E_") for code, _ in lines) else 0


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
    runs.check_job(job, runs.run_jobs([job], 1, run_dir, settings)[job], "T_JOB_XML", settings)
    xml = str(job / "model.xml")
    if (exe := appcsxcad(settings)) is None:
        raise KrsError("E_APPCSXCAD_MISSING", path=xml, command=runs.install_command())
    open_viewer(exe, job)
    print(render("I_PREVIEW", path=xml))
    return 0
