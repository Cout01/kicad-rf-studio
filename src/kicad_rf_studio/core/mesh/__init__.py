# SPDX-License-Identifier: GPL-3.0-or-later
"""The FDTD mesh (spec 5.4), in mm: the x, y and z lines the mesh rule places for a geometry."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from itertools import permutations
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
    from kicad_rf_studio.core.mesh.rule import Edge

ALONG = 50  # a segment runs along an axis when it leaves it by under 1/ALONG of its length (and under 2·SIMPLIFY)
VIA_MARGIN_MM = 1.0  # an SI mesh fills d this far either side of a measured net's via (r1: 1 mm); gate P4-C may move it


@dataclass(frozen=True)
class Mesh:
    """The lines of each axis, d and dz0. `pinned` holds, per axis, the rule's own lines, which never move: the walls,
    the edge lines, the protected extent's ends and its fill in x and y; the walls, the copper faces and the dz0 lines
    in z. The timestep-floor reference reads their smallest steps. `edges` holds the protected in-plane copper edges per
    axis as (position, inside sign), for the edge lint. `snapped_rods` are the geometry's rods with every curve's centre
    moved to the nearest x and y lines; a solid rod that holds no mesh node is snapped as well, a curve there (plan 4
    ruling R-11). `exempt` holds, per axis, the edges the lint spares its third test: an antenna's two-layer pairs
    (_pairs), none for any other geometry."""
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    d: float
    dz0: float
    pinned: dict[str, np.ndarray]
    edges: dict[str, list[tuple[float, int]]]
    snapped_rods: tuple[Rod, ...] = ()
    exempt: dict[str, frozenset[Edge]] = field(default_factory=dict)


def build_mesh(geom: Geometry, prot: Protected, n: int, extra_edges: dict[str, list[tuple[float, int]]] | None = None,
               *, max_cell: float | None = None) -> Mesh:
    """The mesh of `geom` for the protected set `prot`, n cells across the narrowest width, gap or substrate height (2
    standard, 3 fine).
    Each in-plane axis comes from xy_lines with the protected edges (_edges; those at a section's cut are preferred in
    collisions) and `extra_edges`, which the edge lint's re-mesh passes and which keep their own pattern, the extent
    of the protected area and port boxes, and the vertices of every copper piece, rod and lid as free coordinates; z
    comes from z_lines, with the top wall raised by as much as the lid rises above the board, so it stays as far from
    the lid as from the board (R-P2-3; spec 5.2: the lid is never the boundary) and snap_lid finds a line near its
    top. A rod that is not solid moves to the nearest x and y lines in `snapped_rods`, and a solid rod that holds no
    mesh node is snapped as well, a curve there (plan 4 ruling R-11): no (x, y) node lies within its radius of its
    centre, the boundary included, as openEMS includes a node there. Cells wider than its drill can fall around it (the
    d fill on a thick board), and openEMS would lose its barrel silently. No line moves, and `geom` is not changed. For
    an antenna's geometry alone (Geometry.antenna), each axis's xy_lines also takes its two-layer pairs (_pairs), which
    the edge lint spares its third test, and the Mesh holds them in `exempt`; every other geometry exempts none.
    The substrate h, which d, the edge patterns and z take, is that of the geometry's layers (Geometry.layers: an SI
    project's lines'; the top layer's without them). With `max_cell` (an SI project's mesh.max_cell_mm, Stage 4 design
    5.3) each in-plane axis takes xy_lines' SI rule: the edges keep their patterns, d fills only the spans of _spans
    (every solid rod, and every staircased track's copper) and the extent's other cells grade up to max_cell. A rod
    that is not solid is snapped to the lines (`snapped_rods`) and needs no span. With None, d fills the whole extent,
    as for v1 and an antenna."""
    region, zs = geom.region, geom.zs
    h, coarse, walls = substrate_h(zs, geom.layers), region.coarse, region.walls
    d = cell_size(geom.sections, geom.track_width, n, 20 * coarse, geom.track_gap, h)  # the coarse cell is λ_min/20
    t_m = max((m.t_m for m in geom.masks.values()), default=0.0)
    edges, prefer = _edges(geom.pieces, prot, geom.sections)
    exempt = {axis: frozenset(v) for axis, v in _pairs(geom.pieces, prot).items()} if geom.antenna else {}
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
                                             prefer[axis], force[axis], h, exempt.get(axis, frozenset()),
                                             max_cell=max_cell, spans=_spans(geom, prot, k))
    z_walls = walls[4:]
    if geom.lid is not None:
        z_walls = (walls[4], round(walls[5] + max(0.0, geom.lid.z1 - zs[-1].z1), 6))
    dz = dz0(t_m, d, h)
    z = z_lines(zs, d, t_m, h, z_walls, coarse=coarse)
    cu = [s for s in zs if s.kind == "copper"]
    pinned["z"] = z[np.isin(z, [*z_walls, *(v for s in cu for v in (s.z0, s.z1, round(s.z0 - dz, 6),
                                                                   round(s.z1 + dz, 6)))])]
    # the node nearest a rod's centre lies on its nearest x and y lines; to 1e-9 mm, so that a node on the boundary
    # (all on the 1e-6 mm grid) compares equal to the radius
    near = [(_nearest(lines["x"], r.at[0]), _nearest(lines["y"], r.at[1])) for r in geom.rods]
    rods = tuple(r if r.solid and round(math.dist(at, r.at), 9) <= r.radius else replace(r, at=at, solid=False)
                 for r, at in zip(geom.rods, near))
    return Mesh(lines["x"], lines["y"], z, d, dz, pinned, edges, rods, exempt)


def _spans(geom: Geometry, prot: Protected, k: int) -> list[tuple[float, float]]:
    """The SI rule's spans on in-plane axis `k` (0 for x, 1 for y), on the 1e-6 mm grid: every solid rod by its own
    coordinate on that axis, whatever its other one, VIA_MARGIN_MM either side for a measured net's (`prot.nets`) and
    its radius for any other (a stitching or thermal via); then every staircased track's copper bounds along the axis
    (Geometry.stairs). xy_lines lines a coordinate only d or more past the extent, so a rod whose centre lies just past
    it on one axis would otherwise keep no line on the other."""
    # ponytail: another rod keeps d over its barrel only; its ring and the planes' antipads grade, which P4-C's twin
    # measures
    spans = [(r.at[k] - m, r.at[k] + m) for r in geom.rods if r.solid
             for m in [VIA_MARGIN_MM if r.net in prot.nets else r.radius]]
    spans += [(s[k], s[k + 2]) for s in geom.stairs]
    return [(round(a, 6), round(b, 6)) for a, b in spans]


def _edges(pieces: list[Piece], prot: Protected, sections: Iterable[Section] = ()
           ) -> tuple[dict[str, list[tuple[float, int]]], dict[str, set[tuple[float, int]]]]:
    """The protected in-plane copper edges, per axis, as sorted (position, inside sign): the segments of the outlines
    of copper, solid or sheet (R-P2-18: a sheet's edges take edge_lines too, and the lint checks them), that run along
    y or x and lie in the protected area of their layer for more than SIMPLIFY. Each (layer, net)'s pieces are united
    first, so the hole split's cuts are not edges. A segment the 10 µm simplification tilted (a track's edge where its
    round cap began) still runs along its axis when it leaves it by under 2·SIMPLIFY and 1/ALONG of its length, and
    sits at its middle. Also, per axis, the edges that cross a section's cut on its layer: the cross-section fit2d
    checks (spec 5.5) is theirs; and the edges of the same sign whose segment reaches one of theirs across the axis,
    pieces of the same physical edge that the simplification tilted (a strip's edge past a mid-line pad, ending on its
    round cap, sat 1.6 µm deeper than the cut edge and took the cell from it: fit2d −4.21 %, −1.49 % as a cut edge)."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for pc in pieces:
        groups[pc.layer, pc.net].append(pc.polygon)
    cuts: dict[tuple[str, str], list[float]] = defaultdict(list)  # (layer, axis of the edges): where sections are cut
    for s in sections:
        cuts[s.layer, "y" if s.axis == "x" else "x"].append(s.cut[0] if s.axis == "x" else s.cut[1])
    zones = {layer: area.buffer(1e-4) for layer, area in prot.area.items()}  # 0.1 µm for the grid
    found: dict[str, set[tuple[float, int]]] = {"x": set(), "y": set()}
    at_cut: dict[str, set[tuple[float, int]]] = {"x": set(), "y": set()}
    spans: dict[str, dict[tuple[float, int], list[list[float]]]] = {"x": defaultdict(list), "y": defaultdict(list)}
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
                        spans[axis][edge].append(sorted((x0, x1) if axis == "x" else (y0, y1)))  # across the axis
                        a, b = sorted((x0, x1) if axis == "y" else (y0, y1))
                        if any(a <= c <= b for c in cuts[layer, axis]):
                            at_cut[axis].add(edge)
    for axis in "xy":
        at_cut[axis] |= {e for e in found[axis] for c in at_cut[axis] if e[1] == c[1] and any(
            a0 <= b1 + 1e-6 and b0 <= a1 + 1e-6 for a0, a1 in spans[axis][e] for b0, b1 in spans[axis][c])}
    return {axis: sorted(v) for axis, v in found.items()}, at_cut


def _pairs(pieces: list[Piece], prot: Protected) -> dict[str, set[Edge]]:
    """The protected edges, per axis, that another copper layer's opposite edge meets, the metal on its other side, as
    on a two-layer helix (Stage 3 design 5.3): no line passes the lint's third test for both."""
    # ponytail: pairs by position across layers only, so two unrelated edges that happen to coincide are exempt too;
    # computed for an antenna's geometry alone
    per_layer = [_edges([pc for pc in pieces if pc.layer == layer], prot)[0] for layer in {pc.layer for pc in pieces}]
    return {axis: {e for a, b in permutations(per_layer, 2) for e in a[axis] for f in b[axis]
                   if e[1] == -f[1] and abs(e[0] - f[0]) <= 2 * SIMPLIFY} for axis in "xy"}


def _nearest(lines: np.ndarray, v: float) -> float:
    """The line of `lines` (sorted, two or more) nearest `v`."""
    i = int(np.clip(np.searchsorted(lines, v), 1, len(lines) - 1))
    return float(lines[i] if lines[i] - v < v - lines[i - 1] else lines[i - 1])
