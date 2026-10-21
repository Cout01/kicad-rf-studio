# SPDX-License-Identifier: GPL-3.0-or-later
"""The mesh gates (spec 5.5), in mm: the edge lint with its one automatic re-mesh, fit2d against the 2D reference, and
the reference of the timestep floor, which plan 3 compares with openEMS's dt."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.constants import c as C_0

from kicad_rf_studio.core.cs2d import solve
from kicad_rf_studio.core.geometry.sections import cross_section
from kicad_rf_studio.core.mesh import build_mesh
from kicad_rf_studio.core.messages import KrsError

if TYPE_CHECKING:
    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.geometry.sections import Section
    from kicad_rf_studio.core.mesh import Mesh
    from kicad_rf_studio.core.mesh.protect import Protected

FIT2D_LIMIT = 0.03  # spec 5.5: above 3 % in Z0 the run is blocked (P0-A confirms the threshold)


@dataclass(frozen=True)
class LintHit:
    """A protected copper edge at `edge` across `axis` that fails the lint: `reason` is "on_edge",
    "inside_too_close" or "outside_closer"."""
    axis: str
    edge: float
    reason: str


@dataclass(frozen=True)
class Fit:
    """fit2d of `section`: Z0 on the mesh lines and on cs2d's own grid (Ω), and `err`, |z0_mesh/z0_ref − 1|."""
    section: Section
    z0_mesh: float
    z0_ref: float
    err: float


def edge_lint(mesh: Mesh) -> list[LintHit]:
    """The in-plane protected copper edges of `mesh` (Mesh.edges; the copper's z faces carry lines and are exempt)
    with a line on them, their nearest inside line nearer than d/8, or their first outside line no farther than that
    inside line: a tie ties the outer line to the metal under openEMS's inclusive rule (T7). The distances go to 1e-9
    mm, so that a tie on the 1e-6 mm grid compares equal (float noise put either line ahead)."""
    hits = []
    for axis in "xy":
        lines = getattr(mesh, axis)
        for e, inside in mesh.edges.get(axis, ()):
            off = np.round((lines - e) * inside, 9)  # > 0 inside the metal
            near_in, near_out = off[off > 0].min(initial=np.inf), -off[off < 0].max(initial=-np.inf)
            reason = ("on_edge" if (off == 0).any() else "inside_too_close" if near_in < mesh.d / 8
                      else "outside_closer" if near_out <= near_in else None)
            if reason:
                hits.append(LintHit(axis, e, reason))
    return hits


def mesh_with_lint(geom: Geometry, prot: Protected, n: int) -> Mesh:
    """build_mesh's mesh, linted; on a failure rebuilt once (spec 5.5) with the failing edges as `extra_edges`, which
    keep their own pattern. Raises E_EDGE_LINT, naming the first edge that still fails: a neighbour may fail instead
    after the re-mesh (T10)."""
    mesh = build_mesh(geom, prot, n)
    if hits := edge_lint(mesh):
        bad = {(h.axis, h.edge) for h in hits}
        mesh = build_mesh(geom, prot, n, {axis: [e for e in mesh.edges[axis] if (axis, e[0]) in bad] for axis in "xy"})
        if hits := edge_lint(mesh):
            raise KrsError("E_EDGE_LINT", axis=hits[0].axis, edge_mm=hits[0].edge, reason=hits[0].reason)
    return mesh


def fit2d(geom: Geometry, mesh: Mesh) -> list[Fit]:
    """Each section's Z0 on the mesh against the 2D reference (spec 5.5), the mask in both, in the one box
    cross_section gives (R-P2-16): on the mesh lines across the section and `mesh.z`, the coat smeared over dz0 as in
    the FDTD model, against cs2d's own grid with the exact mask. A mesh that puts a grid node on the line and on
    another conductor (a short in FDTD) or holds no grid edge in it (the line is lost) carries no such line: z0_mesh
    0 and err 1, never a skip or NaN (T7)."""
    fits = []
    for sec in geom.sections:
        ref = solve(cross_section(sec, geom.pieces, geom.zs, geom.mask, "exact")).z0
        cs = cross_section(sec, geom.pieces, geom.zs, geom.mask, "smeared", mesh.dz0)
        try:
            z0 = solve(cs, mesh.y if sec.axis == "x" else mesh.x, mesh.z).z0
        except ValueError:
            z0 = 0.0
        fits.append(Fit(sec, z0, ref, abs(z0 / ref - 1)))
    return fits


def check_fit2d(fits: list[Fit]) -> None:
    """Raises E_FIT2D for the section that misses the reference most, when it misses it by more than 3 %."""
    worst = max(fits, key=lambda f: f.err, default=None)
    if worst is not None and worst.err > FIT2D_LIMIT:
        raise KrsError("E_FIT2D", net=worst.section.net, layer=worst.section.layer, err_pct=round(100 * worst.err, 2),
                       limit_pct=round(100 * FIT2D_LIMIT))


def dt_floor_reference(mesh: Mesh) -> float:
    """The timestep floor's reference (spec 5.5), in s: the vacuum Courant step 1/(c0·√(dx⁻² + dy⁻² + dz⁻²)) of the
    smallest cells the rule places, the smallest steps of the mesh's x, y and z lines. Every line of a Mesh is the
    rule's; Mesh.pinned alone can miss the smallest cell (T10: lpf915 once had a 30.3 µm x cell between pinned lines
    35.2 µm apart), and a reference over the Courant step of the final lines could trip plan 3's 0.8 floor on our own
    mesh."""
    return 1 / (C_0 * math.sqrt(sum((np.diff(v).min() * 1e-3) ** -2 for v in (mesh.x, mesh.y, mesh.z))))
