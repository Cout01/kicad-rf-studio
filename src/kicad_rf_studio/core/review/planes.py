# SPDX-License-Identifier: GPL-3.0-or-later
"""The plane map and a track's reference (Stage 5 design 5.1, 5.2): the zone fills of the ground and power nets by
layer, and for a track the nearest other copper layer, by dielectric, whose planes touch its centre line, with the net
that covers most of that line there. R1 to R3 read this reference."""
from __future__ import annotations

import re
from dataclasses import dataclass

import shapely
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.geometry.zstack import Slab
from kicad_rf_studio.core.kicad.board import Board, Track
from kicad_rf_studio.core.kicad.shapes import arc_points
from kicad_rf_studio.core.kicad.tracer import Classes, _base

DOTTED_POWER = re.compile(r"\+\d+\.\d+V\w*")  # KiCad's power symbols with a decimal point: +3.3V, +1.8V (f4)


@dataclass(frozen=True)
class Ref:
    """A track's reference: the plane layer and net under it."""
    layer: str
    net: str
    h: float  # the dielectric from the track's copper to `layer`, in mm
    b: float | None  # a stripline's dielectric between the planes on both sides, in mm; None otherwise


@dataclass(frozen=True)
class PlaneMap:
    """A board's planes, with the layers and dielectrics `reference` reads them by."""
    planes: dict[str, dict[str, BaseGeometry]]  # by layer, then net: the union of the net's zone fills there
    gnd: frozenset[str]  # the ground nets, which win a tie
    layers: tuple[str, ...]  # the copper layers, top to bottom
    skipped: tuple[str, ...]  # the layers with a zone left unfilled or hatched, top to bottom
    h: dict[tuple[str, str], float]  # the dielectric between two copper layers, in mm, in both orders


def centre_line(t: Track) -> LineString:
    """A track's centre line: its two ends, or its arc as a polyline."""
    return LineString([t.start, t.end] if t.mid is None else arc_points(t.start, t.mid, t.end))


def plane_nets(board: Board, classes: Classes) -> frozenset[str]:
    """The nets whose zone fills are planes: the ground and power nets, and the dotted supply names `tracer.POWER`
    misses. POWER itself stays as it is: v1, the antenna and SI classify with it."""
    return classes.gnd | classes.power | {n for n in board.nets if DOTTED_POWER.fullmatch(_base(n))}


def plane_map(board: Board, classes: Classes, zs: tuple[Slab, ...]) -> PlaneMap:
    """The board's planes, each plane net's zone fills unioned per (layer, net); the layers whose zone the import
    left unfilled or dropped as hatched, which would read as a void everywhere; and the dielectric between each two
    copper layers of `zs`, summed over the slabs between them."""
    nets, fills = plane_nets(board, classes), {}
    for a in board.areas:
        if a.source == "zone" and a.net in nets:
            fills.setdefault(a.layer, {}).setdefault(a.net, []).append(a.polygon)
    named = {p["layer"] for code, p in board.warnings
             if code == "W_ZONE_NOT_FILLED" or (code == "W_COPPER_DROPPED" and p["kind"] == "T_HATCHED_ZONE")}
    skipped = tuple(layer for layer in board.copper_layers if layer in named)
    at = {s.copper: i for i, s in enumerate(zs) if s.kind == "copper"}  # each copper layer's place in zs
    h = {(a, b): round(sum(s.z1 - s.z0 for s in zs[min(i, j) + 1:max(i, j)] if s.kind == "dielectric"), 6)
         for a, i in at.items() for b, j in at.items() if a != b}
    planes = {layer: {net: shapely.union_all(p) for net, p in by_net.items()} for layer, by_net in fills.items()}
    return PlaneMap(planes, classes.gnd, board.copper_layers, skipped, h)


def cover(pm: PlaneMap, net: str) -> BaseGeometry:
    """`net`'s planes on every layer, unioned."""
    return shapely.union_all([nets[net] for nets in pm.planes.values() if net in nets])


def reference(pm: PlaneMap, layer: str, line: LineString) -> Ref | None:
    """The reference of a track on `layer` whose centre line is `line`, or None when no other layer's plane touches
    the line. Each side's candidate is the nearest other layer, by h, whose planes touch the line; the reference is
    the nearer candidate, the one below on a tie. Its net is the touching one whose planes there cover most of the
    line, then a ground net, then the first name. b is the sum of both sides' h when both have a candidate."""
    def touching(other: str) -> dict[str, BaseGeometry]:
        return {n: g for n, g in pm.planes.get(other, {}).items() if g.intersects(line)}

    def nearest(side: tuple[str, ...]) -> str | None:  # nearest first, so a tie in h goes to the nearer layer
        return min((o for o in side if touching(o)), key=lambda o: pm.h[(layer, o)], default=None)

    i = pm.layers.index(layer)
    above, below = nearest(pm.layers[:i][::-1]), nearest(pm.layers[i + 1:])
    if above is None and below is None:
        return None
    ref = min((o for o in (below, above) if o), key=lambda o: pm.h[(layer, o)])  # below first, so it wins a tie
    covered = {n: round(line.intersection(g).length, 6) for n, g in touching(ref).items()}
    net = min(covered, key=lambda n: (-covered[n], n not in pm.gnd, n))
    b = round(pm.h[(layer, above)] + pm.h[(layer, below)], 6) if above and below else None
    return Ref(ref, net, pm.h[(layer, ref)], b)
