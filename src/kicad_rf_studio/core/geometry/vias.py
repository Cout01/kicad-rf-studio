# SPDX-License-Identifier: GPL-3.0-or-later
"""Vias as rods (spec 5.1), in mm: a via of the protected set is a solid PEC cylinder of its drill, and any other a
PEC curve, which the mesh snaps to its lines so that it cannot fall between them. A plated hole (a thru_hole pad) has
a barrel too, and is a via here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry import Point, Polygon

from kicad_rf_studio.core.geometry.zstack import Slab
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import XY

if TYPE_CHECKING:  # core.mesh builds on core.geometry, so nothing here imports it at run time
    from kicad_rf_studio.core.mesh.protect import Protected


@dataclass(frozen=True)
class Rod:
    """A via's or a plated hole's barrel, from z0 to z1: a cylinder of `radius` (half its drill) when `solid`, else a
    curve at `at`."""
    net: str
    at: XY
    radius: float
    z0: float
    z1: float
    solid: bool


def via_rods(board: Board, crop: Polygon, zs: tuple[Slab, ...], prot: Protected) -> list[Rod]:
    """The vias and plated holes whose centre lies in `crop`, each from the bottom face of the lowest copper layer it
    joins to the top face of the highest, on the 1e-6 mm grid. A rod is solid when its via's or pad's uuid is in
    `prot.vias`."""
    faces = {s.copper: (s.z0, s.z1) for s in zs if s.kind == "copper"}
    # ponytail: a slot is a rod of its width; a slot-shaped barrel when one matters
    holes = [(v.net, v.at, v.drill, v.layers, v.uuid) for v in board.vias]
    holes += [(p.net, p.at, p.drill, p.layers, p.uuid) for p in board.all_pads() if p.kind == "thru_hole" and p.layers]
    rods = []
    for net, (x, y), drill, layers, uuid in holes:
        if crop.intersects(Point(x, y)):
            z = [z for layer in layers for z in faces[layer]]
            at = round(x, 6), round(y, 6)  # a turned footprint puts a pad's hole off the 1e-6 mm grid
            rods.append(Rod(net, at, round(drill / 2, 6), min(z), max(z), uuid in prot.vias))
    return rods
