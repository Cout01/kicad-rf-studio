# SPDX-License-Identifier: GPL-3.0-or-later
"""The FDTD mesh (spec 5.4), in mm: the x, y and z lines the mesh rule places for a geometry."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np
import shapely
from shapely.geometry import LineString
from shapely.geometry.polygon import orient

from kicad_rf_studio.core.geometry.copper import SIMPLIFY
from kicad_rf_studio.core.geometry.zstack import substrate_h
from kicad_rf_studio.core.mesh.rule import cell_size, dz0, xy_lines, z_lines

if TYPE_CHECKING:
    from collections.abc import Iterable

    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.geometry.copper import Piece
    from kicad_rf_studio.core.geometry.sections import Section
    from kicad_rf_studio.core.geometry.vias import Rod
    from kicad_rf_studio.core.mesh.protect import Protected

ALONG = 50  # a segment runs along an axis when it leaves it by under 1/ALONG of its length (and under 2·SIMPLIFY)


@dataclass(frozen=True)
class Mesh:
    """The lines of each axis, d and dz0. `pinned` holds, per axis, the rule's own lines, which never move: the walls,
    the edge lines, the protected extent's ends and its fill in x and y; the walls, the copper faces and the dz0 lines
    in z. The timestep-floor reference reads their smallest steps. `edges` holds the protected in-plane copper edges per
    axis as (position, inside sign), for the edge lint. `snapped_rods` are the geometry's rods with every curve's centre
    moved to the nearest x and y lines."""
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    d: float
    dz0: float
    pinned: dict[str, np.ndarray]
    edges: dict[str, list[tuple[float, int]]]
    snapped_rods: tuple[Rod, ...] = ()


def build_mesh(geom: Geometry, prot: Protected, n: int,
               extra_edges: dict[str, list[tuple[float, int]]] | None = None) -> Mesh:
    """The mesh of `geom` for the protected set `prot`, n cells across the narrowest width or gap (2 standard, 3 fine).
    Each in-plane axis comes from xy_lines with the protected edges (_edges; those at a section's cut are preferred in
    collisions) and `extra_edges`, which the edge lint's re-mesh passes and which keep their own pattern, the extent
    of the protected area and port boxes, and the vertices of every copper piece, rod and lid as free coordinates; z
    comes from z_lines. A rod that is not solid moves to the nearest x and y lines in `snapped_rods`; `geom` is not
    changed."""
    region, zs = geom.region, geom.zs
    h, coarse, walls = substrate_h(zs), region.coarse, region.walls
    d = cell_size(geom.sections, geom.track_width, n, 20 * coarse, geom.track_gap)  # the coarse cell is λ_min/20
    t_m = geom.mask.t_m if geom.mask is not None else 0.0
    edges, prefer = _edges(geom.pieces, prot, geom.sections)
    force = {axis: sorted(set((extra_edges or {}).get(axis, ()))) for axis in "xy"}
    for axis in "xy":
        edges[axis] = sorted({*edges[axis], *force[axis]})
    shapes = [pc.polygon for pc in geom.pieces] + ([geom.lid.plate, geom.lid.walls] if geom.lid is not None else [])
    free = np.vstack([shapely.get_coordinates(shapes), np.reshape([r.at for r in geom.rods], (-1, 2))])
    box = shapely.total_bounds([*prot.area.values(), *prot.boxes])  # NaN when nothing is protected
    lines, pinned = {}, {}
    for k, axis in enumerate("xy"):
        extent = (box[k], box[k + 2]) if not np.isnan(box[k]) else (np.inf, -np.inf)
        lines[axis], pinned[axis] = xy_lines(edges[axis], extent, walls[2 * k:2 * k + 2], free[:, k], d, coarse,
                                             prefer[axis], force[axis])
    dz = dz0(t_m, d, h)
    z = z_lines(zs, d, t_m, h, walls[4:], coarse=coarse)
    cu = [s for s in zs if s.kind == "copper"]
    pinned["z"] = z[np.isin(z, [*walls[4:], *(v for s in cu for v in (s.z0, s.z1, round(s.z0 - dz, 6),
                                                                      round(s.z1 + dz, 6)))])]
    rods = tuple(r if r.solid else replace(r, at=(_nearest(lines["x"], r.at[0]), _nearest(lines["y"], r.at[1])))
                 for r in geom.rods)
    return Mesh(lines["x"], lines["y"], z, d, dz, pinned, edges, rods)


def _edges(pieces: list[Piece], prot: Protected, sections: Iterable[Section] = ()
           ) -> tuple[dict[str, list[tuple[float, int]]], dict[str, set[tuple[float, int]]]]:
    """The protected in-plane copper edges, per axis, as sorted (position, inside sign): the segments of the outlines
    of copper, solid or sheet (R-P2-18: a sheet's edges take edge_lines too, and the lint checks them), that run along
    y or x and lie in the protected area of their layer for more than SIMPLIFY. Each (layer, net)'s pieces are united
    first, so the hole split's cuts are not edges. A segment the 10 µm simplification tilted (a track's edge where its
    round cap began) still runs along its axis when it leaves it by under 2·SIMPLIFY and 1/ALONG of its length, and
    sits at its middle. Also, per axis, the edges that cross a section's cut on its layer: the cross-section fit2d
    checks (spec 5.5) is theirs."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for pc in pieces:
        groups[pc.layer, pc.net].append(pc.polygon)
    cuts: dict[tuple[str, str], list[float]] = defaultdict(list)  # (layer, axis of the edges): where sections are cut
    for s in sections:
        cuts[s.layer, "y" if s.axis == "x" else "x"].append(s.cut[0] if s.axis == "x" else s.cut[1])
    zones = {layer: area.buffer(1e-4) for layer, area in prot.area.items()}  # 0.1 µm for the grid
    found: dict[str, set[tuple[float, int]]] = {"x": set(), "y": set()}
    at_cut: dict[str, set[tuple[float, int]]] = {"x": set(), "y": set()}
    for (layer, _), polygons in groups.items():
        for p in shapely.get_parts(shapely.union_all(polygons)):
            p = orient(p)  # the copper is left of every ring
            for ring in (p.exterior, *p.interiors):
                xy = np.asarray(ring.coords)
                for (x0, y0), (x1, y1) in zip(xy[:-1], xy[1:]):
                    dx, dy = x1 - x0, y1 - y0
                    if abs(dx) <= min(2 * SIMPLIFY, abs(dy) / ALONG):
                        axis, at, inside = "x", (x0 + x1) / 2, -1 if dy > 0 else 1
                    elif abs(dy) <= min(2 * SIMPLIFY, abs(dx) / ALONG):
                        axis, at, inside = "y", (y0 + y1) / 2, 1 if dx > 0 else -1
                    else:
                        continue
                    if LineString([(x0, y0), (x1, y1)]).intersection(zones[layer]).length > SIMPLIFY:
                        found[axis].add(edge := (round(float(at), 6), inside))
                        a, b = sorted((x0, x1) if axis == "y" else (y0, y1))
                        if any(a <= c <= b for c in cuts[layer, axis]):
                            at_cut[axis].add(edge)
    return {axis: sorted(v) for axis, v in found.items()}, at_cut


def _nearest(lines: np.ndarray, v: float) -> float:
    """The line of `lines` (sorted, two or more) nearest `v`."""
    i = int(np.clip(np.searchsorted(lines, v), 1, len(lines) - 1))
    return float(lines[i] if lines[i] - v < v - lines[i - 1] else lines[i - 1])
