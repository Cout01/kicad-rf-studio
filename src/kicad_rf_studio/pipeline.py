# SPDX-License-Identifier: GPL-3.0-or-later
"""What `cost`, `run` and `preview` share (spec 6.1): a project read with its board and geometry, its model built
through the mesh gates, the port connectivity gate on openEMS's setup, and the cost model (spec 6.4)."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.mesh.gates import check_fit2d, dt_floor_reference, fit2d, mesh_with_lint
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import GRID
from kicad_rf_studio.core.model.ports import ends, nominal_boxes, place
from kicad_rf_studio.core.model.spec import grid_entry, model_spec
from kicad_rf_studio.core.project import board_file, board_hash, mesh_n, read_project
from kicad_rf_studio.runs import MB_PER_MCELL, MB_PER_WORKER

if TYPE_CHECKING:
    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.kicad.board import Board
    from kicad_rf_studio.core.mesh import Mesh

GEOMETRY_GATES = ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI")  # the geometry's notes that block a run


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


def cost_notes(model: Model, project: dict, setup: dict, threads: int, pool: int,
               per_job_mcs: float) -> list[tuple[str, dict]]:
    """The cost lines (spec 6.4) of a built `model`, from openEMS's setup (setup.json: its dt and the node [n, i, j, k]
    of the smallest timestep) and `pool` jobs at once with `threads` threads each at `per_job_mcs` MC/s a job: the
    cells; the smallest cell; dt against its floor, with the edge that sets it in KiCad's frame; the worst case, every
    run to T_max, in ceil(runs / pool) rounds; the time predicted from the longest stop time of the last run, when it
    has one; the RAM; the main cost (driver)."""
    mesh, ports, dt = model.mesh, model.spec["ports"], setup["dt"]
    nx, ny, nz = len(mesh.x), len(mesh.y), len(mesh.z)
    cells, runs = nx * ny * nz, len(ports)

    def time(t_stop: float) -> str:
        return duration(math.ceil(runs / pool) * cells * (t_stop / dt) / (per_job_mcs * 1e6))

    size, axis, at = smallest_cell(mesh)
    n, *ijk = setup["node"]
    x, y, z = (float(lines[k]) for lines, k in zip((mesh.x, mesh.y, mesh.z), ijk))
    t_max = project["t_max_s"]
    notes = [
        ("I_COST_CELLS", {"nx": nx, "ny": ny, "nz": nz, "mcells": f"{cells / 1e6:.2f}", "n": mesh_n(project),
                          "d_mm": f"{mesh.d:.4f}"}),
        ("I_COST_SMALLEST", {"size_um": f"{size * 1e3:.1f}", "axis": axis, "at_mm": f"{at:.3f}"}),
        ("I_COST_DT", {"dt": f"{dt:.4e}", "floor": f"{project['gates']['dt_floor']:g}", "ref": f"{model.dt_ref:.4e}",
                       "axis": "xyz"[n], "x": f"{x:.3f}", "y": f"{0.0 - y:.3f}", "z": f"{z:.3f}"}),
        ("I_COST_TIME", {"time": time(t_max), "runs": runs, "t_max_ns": f"{t_max * 1e9:g}", "pool": pool,
                         "threads": threads})]
    t_stops = [j["t_stop"] for j in project.get("results", {}).get("jobs", ()) if j["t_stop"] is not None]
    if t_stops:  # a job with no samples has no stop time
        notes.append(("I_COST_PREDICTED", {"time": time(max(t_stops))}))
    gb = pool * (MB_PER_MCELL * cells / 1e6 + MB_PER_WORKER) / 1024
    return [*notes, ("I_COST_RAM", {"gb": f"{gb:.1f}", "pool": pool}),
            driver(mesh, runs, sum(q["part"] for q in ports))]
