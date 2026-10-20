# SPDX-License-Identifier: GPL-3.0-or-later
"""Vias as rods (spec 5.1), in mm: a via of the protected set is a solid PEC cylinder of its drill, and any other a
PEC curve, which the mesh snaps to its lines so that it cannot fall between them."""
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
    """A via's barrel, from z0 to z1: a cylinder of `radius` (half its drill) when `solid`, else a curve at `at`."""
    net: str
    at: XY
    radius: float
    z0: float
    z1: float
    solid: bool


def via_rods(board: Board, crop: Polygon, zs: tuple[Slab, ...], prot: Protected) -> list[Rod]:
    """The vias whose centre lies in `crop`, each from the bottom face of the lower copper layer it joins to the top
    face of the upper one. A via is solid when its uuid is in `prot.vias`."""
    faces = {s.copper: (s.z0, s.z1) for s in zs if s.kind == "copper"}
    rods = []
    for v in board.vias:
        if crop.intersects(Point(v.at)):
            z = [z for layer in v.layers for z in faces[layer]]
            rods.append(Rod(v.net, v.at, round(v.drill / 2, 6), min(z), max(z), v.uuid in prot.vias))
    return rods
