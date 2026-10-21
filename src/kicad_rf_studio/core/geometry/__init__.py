# SPDX-License-Identifier: GPL-3.0-or-later
"""The simulation geometry of a board (spec 5.1-5.3), in mm."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kicad_rf_studio.core.kicad.stackup import Stackup
from kicad_rf_studio.core.kicad.tracer import Chain, ChainPart, classify
from kicad_rf_studio.core.project import region_expand_h

if TYPE_CHECKING:  # the types only: importing a submodule must not pull in the others
    from kicad_rf_studio.core.geometry.copper import Piece
    from kicad_rf_studio.core.geometry.lid import Lid
    from kicad_rf_studio.core.geometry.mask import MaskModel
    from kicad_rf_studio.core.geometry.region import Region
    from kicad_rf_studio.core.geometry.sections import Section
    from kicad_rf_studio.core.geometry.vias import Rod
    from kicad_rf_studio.core.geometry.zstack import Slab
    from kicad_rf_studio.core.kicad.board import Board
    from kicad_rf_studio.core.mesh.protect import Protected


@dataclass
class Geometry:
    """What build_geometry derives from a board and its project.json: the region, the z-stack, the copper pieces, the
    protected set, the vias as rods, the masks by the outer copper layer they lie on (the F mask first; a side with
    none is absent), the measured sections, the shield lid (None without one), every warning and E_ gate entry in
    `notes`, `track_width`, the narrowest track of the measured nets, and `track_gap`, sections.staircase_gap (None
    without a staircased track), which the d rule takes with the sections' widths and gaps."""
    region: Region
    zs: tuple[Slab, ...]
    pieces: list[Piece]
    protected: Protected
    rods: list[Rod]
    masks: dict[str, MaskModel]
    sections: list[Section]
    lid: Lid | None
    notes: list[tuple[str, dict]]
    track_width: float
    track_gap: float | None


def chain_of(project: dict) -> Chain:
    """The chain project.json holds, as `new` writes it."""
    c = project["chain"]
    series, shunt = (tuple(ChainPart(p["ref"], tuple(p["pads"]), tuple(p["nets"])) for p in c[key])
                     for key in ("series", "shunt"))
    return Chain(c["start"], c["end"], tuple(c["nets"]), series, shunt)


def build_geometry(board: Board, project: dict) -> Geometry:
    """The geometry of `board` for the chain of `project` (project.json), Tasks 2-6 and 11 in order: the z-stack of
    its stackup and the region (its ports, its band, `region.expand_h`); the copper pieces; the protected set, which
    takes the pads of the other parts that are ports, curve ports or in the grid too (spec 5.4: the part pads); the
    rods, solid in it, and the connectivity check; the F and B masks; the measured sections; the shield lid. `notes`
    holds their warnings and E_ gate entries in that order, which the caller reports and blocks on; `track_width` is
    inf when the measured nets have no track. Raises KrsError: E_STACKUP_LAYERS, E_DIELECTRIC_THICKNESS,
    E_CHAIN_OFF_OUTLINE."""
    # imported here, so that importing a submodule still pulls in none of the others, nor core.mesh, built on them
    from kicad_rf_studio.core.geometry.copper import connectivity, copper_pieces
    from kicad_rf_studio.core.geometry.lid import find_lid
    from kicad_rf_studio.core.geometry.mask import mask_model
    from kicad_rf_studio.core.geometry.region import build_region, f_max
    from kicad_rf_studio.core.geometry.sections import sections, staircase_gap
    from kicad_rf_studio.core.geometry.vias import via_rods
    from kicad_rf_studio.core.geometry.zstack import substrate_h, zstack
    from kicad_rf_studio.core.mesh.protect import protected_set

    chain, classes = chain_of(project), classify(board, project.get("classes"))
    zs = zstack(Stackup.from_json(project["stackup"]), board.copper_layers)
    region = build_region(board, chain, project.get("ports", []), zs, f_max(project), region_expand_h(project))
    thickness = {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.kind == "copper"}
    pieces, notes = copper_pieces(board, region.crop, thickness)
    pads = tuple(name for part in project.get("others", ()) if part["role"] in ("port", "curve_port", "grid")
                 for name in part["pads"])
    protected = protected_set(board, chain, classes, pieces, substrate_h(zs), pads=pads)
    rods = via_rods(board, region.crop, zs, protected)
    notes += connectivity(pieces, rods, region.roi, chain.nets, region.crop)
    secs, staircased = sections(board, chain.nets, pieces)
    lid, gate = find_lid(board, classes, region, zs, project)
    width = min((t.width for t in board.tracks if t.net in chain.nets), default=math.inf)
    copper = [s.copper for s in zs if s.kind == "copper"]  # bottom to top
    masks = {layer: m for layer, side in ((copper[-1], "F"), (copper[0], "B"))
             if (m := mask_model(board, pieces, zs, region.crop, side)) is not None}
    return Geometry(region, zs, pieces, protected, rods, masks, secs, lid, notes + staircased + gate, width,
                    staircase_gap(board, chain.nets, pieces))
