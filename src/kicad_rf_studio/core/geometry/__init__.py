# SPDX-License-Identifier: GPL-3.0-or-later
"""The simulation geometry of a board (spec 5.1-5.3), in mm."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import shapely

from kicad_rf_studio.core.kicad.stackup import Stackup
from kicad_rf_studio.core.kicad.tracer import Chain, ChainPart, classify
from kicad_rf_studio.core.project import (ANTENNA_BOUNDARY, antenna, copper_model, mesh_reach_h, region_expand_h,
                                          region_margin_scale, si)

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
    without a staircased track), which the d rule takes with the sections' widths and gaps. `antenna`: an antenna's
    geometry (Stage 3 design 5.3), whose mesh exempts its two-layer pairs (core.mesh._pairs) from the edge lint's third
    test. An SI project's (Stage 4 design 5.3) has `layers`, its lines' copper layers (sections.line_layers), whose
    thinnest dielectric sets d and the reach, `legs`, a pair's two measured lines' nets (None without a pair), and
    `stairs`, the copper bounds (x0, y0, x1, y1) of its lines' staircased tracks (sections.off_axis), which its mesh
    fills at d; every other geometry has none of them."""
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
    antenna: bool = False
    layers: tuple[str, ...] = ()
    legs: tuple[frozenset[str], frozenset[str]] | None = None
    stairs: tuple[tuple[float, float, float, float], ...] = ()

    def partners(self, net: str) -> frozenset[str]:
        """The nets of an SI pair's other line for a net of one of its lines (`legs`), else none."""
        p, n = self.legs or (frozenset(), frozenset())
        return n if net in p else p if net in n else frozenset()


def chain_of(project: dict) -> Chain:
    """The chain project.json holds, as `new` writes it; an SI project's lines merged (Stage 4 design 5.1): the first
    line's start and end, every line's nets in order, every series part, then every shunt part. `new` stores a part on
    two lines once and refuses a net two lines share (E_SI_LINE_SHARED), so none repeats."""
    chains = [line["chain"] for line in project["lines"]] if si(project) else [project["chain"]]
    series, shunt = (tuple(ChainPart(p["ref"], tuple(p["pads"]), tuple(p["nets"])) for c in chains for p in c[key])
                     for key in ("series", "shunt"))
    return Chain(chains[0]["start"], chains[0]["end"], tuple(n for c in chains for n in c["nets"]), series, shunt)


def build_geometry(board: Board, project: dict) -> Geometry:
    """The geometry of `board` for the chain of `project` (project.json), Tasks 2-6 and 11 in order: the z-stack of
    its stackup and the region (its ports, its band, `region.expand_h` and `region.margin_scale`); the copper pieces;
    the protected set (its reach `mesh.reach_h`), which takes the pads of the other parts that are ports, curve ports
    or in the grid too (spec 5.4: the part pads); the rods, solid in it, and the connectivity check; the F and B masks;
    the measured sections; the shield lid. `notes` holds their warnings and E_ gate entries in that order, which the
    caller reports and blocks on; `track_width` is inf when the measured nets have no track. Raises KrsError:
    E_STACKUP_LAYERS, E_DIELECTRIC_THICKNESS, E_CHAIN_OFF_OUTLINE.
    For an antenna (Stage 3 design 5.2, 5.3), whose copper load() has given the feed net (tracer.adopt), the Geometry
    has `antenna` set. Its region is board_region's: the measured region as the ROI, the whole board inside the walls.
    A touch within its join pads (antenna.join), grown by 2·SIMPLIFY, is no short. W_STAIRCASED names the feed net,
    the chain's last, when the antenna's copper graphics are staircased (sections.staircased) and the sections have
    not named it. Every top-side shield on the board is a lid candidate, and W_LIDS_LEFT_OUT names those the one lid
    leaves out. W_AIR_BOX comes last when the air box is not the one gate P3-C tested, ANTENNA_BOUNDARY past a gap of
    λ/4 at f_lo (air_gap) or more.
    An antenna's sheet copper (Stage 3 design 5.3) is a stack whose copper layers have no thickness.
    For an SI project (Stage 4 design 5.1-5.3) the chain is its lines merged (chain_of), so every line's copper and
    parts are measured. Its `layers`, the lines' copper layers (sections.line_layers), give the region and the
    protected set their substrate height, substrate_h(zs, layers): the thinnest dielectric next to them, which grows
    the ROI and sets the reach. `legs` are a pair's two measured lines' nets, and `stairs` the copper bounds of each of
    the lines' tracks that the mesh staircases (sections.off_axis), its round ends included. W_STAIRCASED_SI, which
    states gate P4-B's 45° pairs, names its staircased nets in W_STAIRCASED's place."""
    # imported here, so that importing a submodule still pulls in none of the others, nor core.mesh, built on them
    from kicad_rf_studio.core.geometry.copper import SIMPLIFY, connectivity, copper_pieces
    from kicad_rf_studio.core.geometry.lid import find_lid
    from kicad_rf_studio.core.geometry.mask import mask_model
    from kicad_rf_studio.core.geometry.region import air_gap, board_region, build_region, f_max
    from kicad_rf_studio.core.geometry.sections import line_layers, off_axis, sections, staircase_gap, staircased
    from kicad_rf_studio.core.geometry.vias import via_rods
    from kicad_rf_studio.core.geometry.zstack import substrate_h, zstack
    from kicad_rf_studio.core.mesh.protect import protected_set

    chain, classes = chain_of(project), classify(board, project.get("classes"))
    ports, ant = project.get("ports", []), antenna(project)
    layers = line_layers(board, chain.nets) if si(project) else ()  # none: the top layer's substrate, as before
    stack = project["stackup"]
    if ant and copper_model(project) == "sheet":  # each copper slab collapses onto its dielectric face, the masks on it
        stack = {**stack, "layers": [{**layer, "thickness_mm": 0.0} if layer["kind"] == "copper" else layer
                                     for layer in stack["layers"]]}
    zs = zstack(Stackup.from_json(stack), board.copper_layers)
    # ponytail: the antenna group is the footprint's own copper; a radiator drawn as tracks on the feed net (fit2d would
    # measure it as feed line) or as board graphics or zones outside the footprint is not in it
    if ant:
        region = board_region(board, chain, ports, zs, f_max(project), region_expand_h(project))
    else:
        region = build_region(board, chain, ports, zs, f_max(project), region_expand_h(project),
                              region_margin_scale(project), layers=layers)
    thickness = {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.kind == "copper"}
    pieces, notes = copper_pieces(board, region.crop, thickness)
    pads = tuple(name for part in project.get("others", ()) if part["role"] in ("port", "curve_port", "grid")
                 for name in part["pads"])
    protected = protected_set(board, chain, classes, pieces, substrate_h(zs, layers), reach_h=mesh_reach_h(project),
                              pads=pads)
    rods = via_rods(board, region.crop, zs, protected)
    join = None
    if ant and project["antenna"]["join"]:
        join = shapely.union_all([p.polygon for name in project["antenna"]["join"] for p in board.pads(name)
                                  if p.layers]).buffer(2 * SIMPLIFY)
    notes += connectivity(pieces, rods, region.roi, chain.nets, region.crop, join)
    secs, stairs = sections(board, chain.nets, pieces)
    feed = chain.nets[-1]  # the net the antenna's copper took
    if ant and ("W_STAIRCASED", {"net": feed}) not in stairs and staircased(
            a.polygon for a in board.areas if a.ref == project["antenna"]["ref"]):
        stairs.append(("W_STAIRCASED", {"net": feed}))
    if si(project):  # gate P4-B's 45° pairs, in an SI project's own words (A-58)
        stairs = [("W_STAIRCASED_SI", p) if c == "W_STAIRCASED" else (c, p) for c, p in stairs]
    lid, gate = find_lid(board, classes, replace(region, roi=region.crop) if ant else region, zs, project)
    width = min((t.width for t in board.tracks if t.net in chain.nets), default=math.inf)
    copper = [s.copper for s in zs if s.kind == "copper"]  # bottom to top
    masks = {layer: m for layer, side in ((copper[-1], "F"), (copper[0], "B"))
             if (m := mask_model(board, pieces, zs, region.crop, side)) is not None}
    if ant and lid is not None:
        left = [r for r in sorted(classes.shields)  # the other top-side shields, find_lid's candidates
                if r != lid.ref and r in board.footprints and board.footprints[r].layer == copper[-1]]
        if left:
            gate.append(("W_LIDS_LEFT_OUT", {"ref": lid.ref, "refs": ", ".join(left)}))
    if ant:
        default, gap = air_gap(project["band"]["f_lo_hz"]), project["air_gap_mm"]
        if project["boundary"] != ANTENNA_BOUNDARY or gap < default:
            gate.append(("W_AIR_BOX", {"gap_mm": f"{gap:.1f}", "quarter_mm": f"{default:.1f}",
                                       "boundary": project["boundary"]}))  # an event before plan 4 carries these
    legs, stair_bounds = None, ()
    if si(project):
        legs = tuple(frozenset(x["chain"]["nets"]) for x in project["lines"][:2]) if project["pair"] else None
        stair_bounds = tuple(t.polygon().bounds for t in board.tracks if t.net in chain.nets and off_axis(t))
    return Geometry(region, zs, pieces, protected, rods, masks, secs, lid, notes + stairs + gate, width,
                    staircase_gap(board, chain.nets, pieces), ant, layers, legs, stair_bounds)
