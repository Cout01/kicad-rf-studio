# SPDX-License-Identifier: GPL-3.0-or-later
"""What `cost`, `run` and `preview` share (spec 6.1): a project read with its board and geometry, and its model built
through the mesh gates."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.mesh.gates import check_fit2d, dt_floor_reference, fit2d, mesh_with_lint
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import GRID
from kicad_rf_studio.core.model.ports import ends, nominal_boxes, place
from kicad_rf_studio.core.model.spec import grid_entry, model_spec
from kicad_rf_studio.core.project import board_file, board_hash, mesh_n, read_project

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
