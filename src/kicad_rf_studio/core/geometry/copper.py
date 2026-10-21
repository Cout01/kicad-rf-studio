# SPDX-License-Identifier: GPL-3.0-or-later
"""The copper pipeline (spec 5.3), in mm. Per (layer, net) the board's copper is made valid, united, clipped to the
through-crop, simplified at 10 µm, put on the 1e-6 mm grid and cut into pieces with no holes, each solid or a sheet.
The connectivity check (spec 5.1) finds where those pieces and the vias break a net or join two."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass

import numpy as np
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

from kicad_rf_studio.core.geometry.vias import Rod
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import circle

GRID = 1e-6  # mm, the grid every coordinate lies on
SIMPLIFY = 0.01  # mm, the farthest the simplification moves an outline
SOLID_T = 30  # copper with a width or a gap below SOLID_T times its thickness is solid
FACING = np.cos(np.radians(30))  # two edges face each other when their normals are within 30° of opposite


@dataclass(frozen=True)
class Piece:
    """A polygon of copper with no holes, on the grid and normalised. A solid piece has its layer's thickness; the
    others are sheets."""
    layer: str
    net: str
    polygon: Polygon
    # ponytail: informational since plan 3: the CSX builds every piece solid (C-5); sheets come back only if P0 shows
    # a gain
    solid: bool


def _polygons(g: BaseGeometry) -> MultiPolygon:
    """The polygons of `g`, without the lines and points an overlay can leave beside them."""
    return MultiPolygon([p for p in shapely.get_parts(g) if isinstance(p, Polygon) and not p.is_empty])


def _grid(g: BaseGeometry) -> MultiPolygon:
    """The polygons of `g` on the grid, which can split or drop the thinnest."""
    return _polygons(shapely.set_precision(_polygons(g), GRID))


def clean(geom: BaseGeometry, crop: Polygon) -> MultiPolygon:
    """Steps 1–5 of the pipeline: each part of `geom` made valid on its own (make_valid on overlapping parts of one
    MultiPolygon would cut their overlap out), their union, the clip to `crop`, the simplification, which keeps the
    topology, and the grid. Normalised."""
    g = _polygons(shapely.union_all(shapely.make_valid(shapely.get_parts(geom))))
    g = _polygons(g.intersection(crop)).simplify(SIMPLIFY, preserve_topology=True)
    return shapely.normalize(_grid(g))


def split_holes(p: Polygon) -> list[Polygon]:
    """Step 6: `p` cut into polygons with no holes; every part a cut makes goes back on the grid. Each cut is vertical,
    at the x of the vertex of the first hole nearest that hole's centroid, so it runs through the hole and opens it: a
    cut through the hole's leftmost vertex only touches a round hole, which then stays a hole."""
    queue, out = [p], []
    while queue:
        q = queue.pop()
        if not q.interiors:
            out.append(q)
            continue
        hole = q.interiors[0]
        mid = Polygon(hole).centroid.x
        x = min((v[0] for v in hole.coords), key=lambda v: abs(v - mid))
        _, y0, x1, y1 = q.bounds
        right = box(x, y0 - 1, x1 + 1, y1 + 1)
        queue += [*_grid(q.intersection(right)).geoms, *_grid(q.difference(right)).geoms]
    return out


def _faces_itself(g: Polygon, d: float) -> bool:
    """Whether two edges of `g` face each other across empty space nearer than `d`, as across a slot, between a
    hairpin's arms or over a small hole. A probe swept `d` out of the copper from each edge, starting half the
    simplification off it and its ends, must meet an edge whose normal is within 30° of opposite: edges that meet at a
    corner (90°, 45°) only lean into each other's probes."""
    g = orient(g)  # exterior counter-clockwise, holes clockwise: the copper is left of every edge
    rings = [np.asarray(ring.coords) for ring in (g.exterior, *g.interiors)]
    a, b = np.concatenate([c[:-1] for c in rings]), np.concatenate([c[1:] for c in rings])
    length = np.hypot(*(b - a).T)
    a, b, length = a[length > 0], b[length > 0], length[length > 0]
    u = (b - a) / length[:, None]
    n = u @ np.array([[0, -1], [1, 0]])  # (uy, -ux): out of the copper
    k, e = length > SIMPLIFY, SIMPLIFY / 2  # an edge shorter than the two offsets sends no probe
    p0, p1 = a[k] + e * (u[k] + n[k]), b[k] + e * (n[k] - u[k])
    probes = shapely.polygons(np.stack([p0, p1, p1 + (d - e) * n[k], p0 + (d - e) * n[k]], axis=1))
    i, j = STRtree(shapely.linestrings(np.stack([a, b], axis=1))).query(probes, "intersects")
    return bool((np.sum(n[k][i] * n[j], axis=1) < -FACING).any())


def is_solid(piece_geom: Polygon, others: BaseGeometry, t: float) -> bool:
    """Whether copper of thickness `t` must be solid: a width of `piece_geom`, a gap inside it (`_faces_itself`) or
    its gap to `others` is below 30·t. A width is below when an opening by 15·t takes copper away, deeper than half
    the simplification: on the grid, an opening also shaves nanometre slivers off a wide outline. The opening is
    mitred, so a wide shape keeps its corners (a round one cuts every corner off), and only the copper it takes counts
    (a mitred one squares off a rounded corner)."""
    r = SOLID_T / 2 * t
    opened = piece_geom.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")
    narrow = not piece_geom.difference(opened).buffer(-SIMPLIFY / 2).is_empty
    return narrow or piece_geom.distance(others) < 2 * r or _faces_itself(piece_geom, 2 * r)


def copper_pieces(board: Board, crop: Polygon,
                  thickness: dict[str, float]) -> tuple[list[Piece], list[tuple[str, dict]]]:
    """The copper of `board` in `crop` as pieces, top layer first, from its tracks, areas, pads and via rings per
    (layer, net). A pad adds copper on exactly its `layers`, none for a paste-only pad or a covered NPTH, with every
    part of a MultiPolygon; a via adds a ring of its diameter on the two layers it joins. The pieces of one cleaned
    polygon share its `solid`, whose gaps are inside it and to every other polygon on the layer, of any net;
    `thickness` gives each layer's t. A (layer, net) whose copper in the crop is all lost in the cleanup is a
    W_COPPER_EMPTIED."""
    groups: dict[tuple[str, str], list[BaseGeometry]] = defaultdict(list)
    for t in board.tracks:
        groups[t.layer, t.net].append(t.polygon())
    for a in board.areas:
        groups[a.layer, a.net].append(a.polygon)
    for p in board.all_pads():
        for layer in p.layers:
            groups[layer, p.net].append(p.polygon)
    for v in board.vias:  # ponytail: rings on the two layers it joins; inner rings when a 4-layer board needs them
        for layer in v.layers:
            groups[layer, v.net].append(circle(v.at, v.diameter / 2))
    cleaned, warnings = {}, []
    for (layer, net), geoms in sorted(groups.items()):
        cleaned[layer, net] = g = clean(GeometryCollection(geoms), crop)
        if g.is_empty and shapely.area(shapely.intersection(geoms, crop)).sum() > 0:
            warnings.append(("W_COPPER_EMPTIED", {"net": net, "layer": layer}))
    pieces = []
    for layer in board.copper_layers:
        polygons = [(net, p) for (on, net), g in cleaned.items() if on == layer for p in g.geoms]
        tree, t = STRtree([p for _, p in polygons]), thickness[layer]
        for i, (net, p) in enumerate(polygons):
            near = MultiPolygon([polygons[j][1] for j in tree.query(p, "dwithin", SOLID_T * t) if j != i])
            solid = is_solid(p, near, t)
            pieces += [Piece(layer, net, shapely.normalize(q), solid) for q in split_holes(p)]
    return pieces, warnings


def connectivity(pieces: list[Piece], rods: list[Rod], roi: BaseGeometry, nets: Collection[str],
                 crop: Polygon) -> list[tuple[str, dict]]:
    """The opens and shorts of `nets`. Pieces on one layer that touch are joined, and a rod joins the pieces its
    barrel touches. The pieces are clipped to `crop`, so a net's parts that run out of it may join outside it: they
    count as one. A net of `nets` in two or more parts is open: E_OPEN_IN_ROI when two of them reach `roi`, else
    W_OPEN_IN_MARGIN. Copper of another net touching theirs is a short: E_SHORT_IN_ROI when the touch lies in `roi`,
    else W_SHORT_IN_MARGIN. Copper with no net floats, so it is never open and shorts nothing. Opens come first, by
    net, then shorts, by pair of nets."""
    # ponytail: a rod joins every layer, as a through via does; a blind or buried via needs its layer span here
    geoms = [pc.polygon for pc in pieces] + [Point(r.at).buffer(r.radius) for r in rods]
    layers = [pc.layer for pc in pieces] + [None] * len(rods)
    names = [pc.net for pc in pieces] + [r.net for r in rods]
    if not geoms:  # STRtree's bulk query cannot take an empty list
        return []
    a, b = STRtree(geoms).query(geoms, "intersects")
    touch = [(i, j) for i, j in zip(a, b) if i < j and (layers[i] == layers[j] or None in (layers[i], layers[j]))]
    same = np.array([(i, j) for i, j in touch if names[i] == names[j]], dtype=int).reshape(-1, 2)
    graph = coo_matrix((np.ones(len(same)), (same[:, 0], same[:, 1])), shape=(len(geoms), len(geoms)))
    part = connected_components(graph, directed=False)[1]
    # the parts that run out of the crop count as one; the simplification and the grid can pull a cut edge up to
    # SIMPLIFY and a hair off the crop's edge
    part[np.isin(part, part[shapely.dwithin(geoms, crop.boundary, 2 * SIMPLIFY)])] = -1
    in_roi = shapely.intersects(geoms, roi)
    notes = []
    for net in sorted(set(nets) - {""}):
        parts = {part[k] for k, n in enumerate(names) if n == net}
        if len(parts) > 1:
            inside = {part[k] for k, n in enumerate(names) if n == net and in_roi[k]}
            notes.append(("E_OPEN_IN_ROI" if len(inside) > 1 else "W_OPEN_IN_MARGIN", {"net": net}))
    shorts: dict[tuple[str, ...], bool] = {}
    for i, j in touch:
        if names[i] != names[j] and names[i] and names[j] and (names[i] in nets or names[j] in nets):
            pair = tuple(sorted((names[i], names[j])))
            shorts[pair] = shorts.get(pair, False) or geoms[i].intersection(geoms[j]).intersects(roi)
    return notes + [("E_SHORT_IN_ROI" if hit else "W_SHORT_IN_MARGIN", {"nets": ", ".join(pair)})
                    for pair, hit in sorted(shorts.items())]
