# SPDX-License-Identifier: GPL-3.0-or-later
"""The protected set (spec 5.4), in mm: the copper that the mesh rule fills at one cell size d, and the vias that
stay solid."""
from __future__ import annotations

from dataclasses import dataclass

import shapely
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.geometry.copper import Piece, _grid
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import circle
from kicad_rf_studio.core.kicad.tracer import Chain, Classes


@dataclass(frozen=True)
class Protected:
    """The protected set of a chain. `area` holds, per copper layer, the copper of the measured `nets`, the chain
    parts' pads and the reference (GND) copper within reach of the measured nets; `vias` are the uuids of the vias
    and plated holes (thru_hole pads) that stay solid; `boxes` are the port boxes (plan 3)."""
    nets: frozenset[str]
    area: dict[str, BaseGeometry]
    vias: frozenset[str]
    boxes: tuple[Polygon, ...]


def protected_set(board: Board, chain: Chain, classes: Classes, pieces: list[Piece], h: float,
                  reach_h: float = 3.0, boxes: tuple[Polygon, ...] = ()) -> Protected:
    """The protected set of `chain`, whose nets are the measured nets. The reach, `reach_h` substrate heights `h`
    (provisional: P0-B checks it), is measured in plane from the measured nets' copper on every layer. The GND copper
    within it is protected, cut where the reach ends, and so is every GND via whose ring comes within it; the measured
    nets' own vias are protected wherever they are. A plated hole (a thru_hole pad) is a via whose ring is its pad.
    `area` is on the 1e-6 mm grid."""
    nets = frozenset(chain.nets)
    measured = shapely.union_all([pc.polygon for pc in pieces if pc.net in nets])
    reach = reach_h * h
    within = measured.buffer(reach)
    names = {name for part in chain.series + chain.shunt for name in part.pads}
    area = {}
    for layer in board.copper_layers:
        shapes = [pc.polygon for pc in pieces if pc.layer == layer and pc.net in nets]
        shapes += [pc.polygon.intersection(within) for pc in pieces if pc.layer == layer and pc.net in classes.gnd]
        shapes += [p.polygon for p in board.all_pads() if p.name in names and layer in p.layers]
        area[layer] = _grid(shapely.union_all(shapes))
    rings = [(v.uuid, v.net, circle(v.at, v.diameter / 2)) for v in board.vias]
    rings += [(p.uuid, p.net, p.polygon) for p in board.all_pads() if p.kind == "thru_hole"]
    vias = frozenset(uuid for uuid, net, ring in rings
                     if net in nets or (net in classes.gnd and shapely.dwithin(measured, ring, reach)))
    return Protected(nets, area, vias, tuple(boxes))
