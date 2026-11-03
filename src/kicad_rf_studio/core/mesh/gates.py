# SPDX-License-Identifier: GPL-3.0-or-later
"""The mesh gates (spec 5.5), in mm: the edge lint with its one automatic re-mesh, fit2d against the 2D reference, and
the reference of the timestep floor, which plan 3 compares with openEMS's dt."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.constants import c as C_0

from kicad_rf_studio.core.cs2d import ShortError, solve
from kicad_rf_studio.core.geometry.sections import cross_section
from kicad_rf_studio.core.mesh import build_mesh
from kicad_rf_studio.core.mesh.rule import lint_hits
from kicad_rf_studio.core.messages import KrsError

if TYPE_CHECKING:
    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.geometry.sections import Section
    from kicad_rf_studio.core.mesh import Mesh
    from kicad_rf_studio.core.mesh.protect import Protected


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
    that fail the edge lint on their axis's lines, with rule.lint_hits' reasons: a line on them, their nearest inside
    line nearer than d/8, or their first outside line no farther than that inside line (a tie fails), a third test that
    Mesh.exempt's edges, an antenna's two-layer pairs, are spared."""
    return [LintHit(axis, e, reason) for axis in "xy"
            for e, reason in lint_hits(getattr(mesh, axis), mesh.edges.get(axis, ()), mesh.d,
                                       mesh.exempt.get(axis, ()))]


def mesh_with_lint(geom: Geometry, prot: Protected, n: int, *, max_cell: float | None = None) -> Mesh:
    """build_mesh's mesh, at `max_cell` (an SI project's, Stage 4 design 5.3; None for Stage 1's d fill), linted; on a
    failure rebuilt once (spec 5.5) with the failing edges as `extra_edges`, which keep their own pattern. Raises
    E_EDGE_LINT with `n`, naming the first edge that still fails (a neighbour may fail instead after the re-mesh, T10)
    as KiCad shows it: y down, and the reason in words (T_ON_EDGE)."""
    mesh = build_mesh(geom, prot, n, max_cell=max_cell)
    if hits := edge_lint(mesh):
        bad = {(h.axis, h.edge) for h in hits}
        extra = {axis: [e for e in mesh.edges[axis] if (axis, e[0]) in bad] for axis in "xy"}
        mesh = build_mesh(geom, prot, n, extra, max_cell=max_cell)
        if hits := edge_lint(mesh):
            hit = hits[0]
            # ponytail: the term by name; a new reason in rule.lint_hits needs its T_ code
            raise KrsError("E_EDGE_LINT", axis=hit.axis, edge_mm=0.0 - hit.edge if hit.axis == "y" else hit.edge,
                           reason="T_" + hit.reason.upper(), n=n)
    return mesh


def fit2d(geom: Geometry, mesh: Mesh) -> list[Fit]:
    """Each section's Z0 on the mesh against the 2D reference (spec 5.5), the mask of its own side in both (none on
    inner copper), in the one box cross_section gives (R-P2-16): on the mesh lines across the section and `mesh.z`,
    the coat smeared over dz0 as in the FDTD model, against cs2d's own grid with the exact mask. A mesh that puts a
    grid node on the line and on another conductor (a short in FDTD) or holds no grid edge in it (the line is lost)
    carries no such line: z0_mesh 0 and err 1, never a skip or NaN (T7). Raises E_FIT2D_SHORT when other copper
    touches the line at its cut, which leaves the reference no line to solve."""
    fits = []
    for sec in geom.sections:
        mask = geom.masks.get(sec.layer)
        try:
            ref = solve(cross_section(sec, geom.pieces, geom.zs, mask, "exact")).z0
        except ShortError:
            raise KrsError("E_FIT2D_SHORT", net=sec.net, layer=sec.layer) from None
        cs = cross_section(sec, geom.pieces, geom.zs, mask, "smeared", mesh.dz0)
        try:
            z0 = solve(cs, mesh.y if sec.axis == "x" else mesh.x, mesh.z).z0
        except ValueError:
            z0 = 0.0
        fits.append(Fit(sec, z0, ref, abs(z0 / ref - 1)))
    return fits


def check_fit2d(fits: list[Fit], limit: float, n: int) -> None:
    """Raises, for the section that misses the reference most, when it misses it by more than `limit` (project.json's
    gates.fit2d_limit): E_FIT2D at mesh.n `n` under 3, whose advice is the fine mesh, else E_FIT2D_FINE."""
    worst = max(fits, key=lambda f: f.err, default=None)
    if worst is not None and worst.err > limit:
        raise KrsError("E_FIT2D" if n < 3 else "E_FIT2D_FINE", net=worst.section.net, layer=worst.section.layer,
                       err_pct=round(100 * worst.err, 2), limit_pct=f"{100 * limit:g}", n=n)


def dt_floor_reference(mesh: Mesh) -> float:
    """The timestep floor's reference (spec 5.5), in s: the vacuum Courant step 1/(c0·√(dx⁻² + dy⁻² + dz⁻²)) of the
    smallest cells the rule places, the smallest steps of the mesh's x, y and z lines. Every line of a Mesh is the
    rule's; Mesh.pinned alone can miss the smallest cell (T10: lpf915 once had a 30.3 µm x cell between pinned lines
    35.2 µm apart), and a reference over the Courant step of the final lines could trip plan 3's 0.8 floor on our own
    mesh."""
    return 1 / (C_0 * math.sqrt(sum((np.diff(v).min() * 1e-3) ** -2 for v in (mesh.x, mesh.y, mesh.z))))
