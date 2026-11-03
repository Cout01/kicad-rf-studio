# SPDX-License-Identifier: GPL-3.0-or-later
"""The simulated region (spec 5.1), in mm: the ROI around the chain, the walls past it and the through-crop past them.
Copper, substrate and vias run through the walls to the crop, so no net is cut at the ROI. An antenna's region holds
the whole board (board_region, Stage 3 design 5.2)."""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import shapely
from shapely.geometry import MultiPolygon, Point, Polygon, box

from kicad_rf_studio.core.geometry.zstack import Slab, substrate_h
from kicad_rf_studio.core.kicad.board import OUTLINE_GRID, Board
from kicad_rf_studio.core.kicad.shapes import pt
from kicad_rf_studio.core.kicad.tracer import Chain
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import REACH_H, antenna, pulse_band

C0 = 299_792_458.0  # m/s
WALL_MM, WALL_CELLS = 4.0, 8  # the walls sit 4 mm and 8 coarse cells past the ROI, on all six faces (× margin_scale)
CROP_MM = 1.0  # the through-crop, past the walls


def f_max(project: dict) -> float:
    """The top of the band, in Hz: band(project)[1] for an antenna (Stage 3 design 5.4), else band_factor × harmonics
    × f0."""
    if antenna(project):
        return band(project)[1]
    return project["band_factor"] * project["harmonics"] * project["f0_hz"]


def band(project: dict) -> tuple[float, float]:
    """The band (f1, f2), in Hz: an antenna's pulse band (pulse_band, Stage 3 design 5.4); else from half of f0 to the
    top of the band (spec 5.8)."""
    if antenna(project):
        return pulse_band(project["band"]["f_lo_hz"], project["band"]["f_hi_hz"])
    return project["f0_hz"] / 2, f_max(project)


def lambda_min(f_max: float, eps_r_max: float) -> float:
    """The shortest wavelength in the board, in mm."""
    return C0 * 1e3 / (f_max * math.sqrt(eps_r_max))


def coarse_cell(f_max: float, eps_r_max: float) -> float:
    """The coarse cell, in mm: λ_min/20."""
    return lambda_min(f_max, eps_r_max) / 20


# an SI mesh's largest cell along a line is λ_eff(f_max)/SI_CELLS (Stage 4 design 5.3); gate P4-C may move it
SI_CELLS = 40


def si_max_cell(f_max: float, eps_eff: float) -> float:
    """An SI mesh's max_cell, λ_eff(f_max)/SI_CELLS, in mm: f_max in Hz, eps_eff the lines' 2D εeff (Stage 4 design
    5.3)."""
    return lambda_min(f_max, eps_eff) / SI_CELLS


@dataclass(frozen=True)
class Region:
    roi: Polygon | MultiPolygon  # in pieces only where the outline splits the grown box (a U-shaped board)
    walls: tuple[float, float, float, float, float, float]  # x0, x1, y0, y1, z0, z1
    crop: Polygon
    coarse: float  # the coarse cell, from the stackup's highest εr


def build_region(board: Board, chain: Chain, ports: list[dict], zs: tuple[Slab, ...], f_max: float,
                 expand_h: float = 3.0, margin_scale: float = 1.0, layers: Iterable[str] = ()) -> Region:
    """The region of `chain`. The ROI is the bounding box of the copper of the chain's nets (tracks, areas and pads),
    the chain parts' pads and the ports' pads and reference points (project.json's `ports`), grown by `expand_h`
    substrate heights: substrate_h(zs, layers), the thinnest dielectric next to `layers`, an SI project's line layers
    (Stage 4 design 5.3); with none, the top layer's, where v1's and an antenna's chain run. It is clipped to the board
    outline unless it lies inside it to within the outline's 1 µm grid.
    The walls sit `margin_scale` × (WALL_MM + WALL_CELLS coarse cells) past it, on all six faces.
    Every coordinate is quantised to 1e-6 mm. Raises E_CHAIN_OFF_OUTLINE when the chain's nets have no copper, or a
    piece of it (a track, an area, a pad) misses the outline: of several Edge.Cuts loops (a panel, a frame, a coupon
    beside the board) the board reader keeps the largest (R-P2-14). A chain on another loop had an empty ROI (a raw
    GEOS error) or a sliver of the wrong board; copper of its nets on another loop (copy and paste keeps a track's net)
    was measured as a section, broke fit2d past the crop and stretched the ROI. Copper partly off the outline (an
    edge-launch pad) passes. A part pad or a port's reference cannot vouch for the chain: a microstrip coupon's port
    takes the nearest ground copper on its layer, which in a panel can be the main board's."""
    nets = set(chain.nets)
    refs = [port["reference"] for port in ports if port["reference"]]
    names = {name for part in chain.series + chain.shunt for name in part.pads}
    names |= {port["signal"] for port in ports} | {ref["pad"] for ref in refs if "pad" in ref}
    copper = [t.polygon() for t in board.tracks if t.net in nets] + [a.polygon for a in board.areas if a.net in nets]
    copper += [p.polygon for p in board.all_pads() if p.layers and p.net in nets]
    shapes = copper + [p.polygon for p in board.all_pads() if p.layers and p.net not in nets and p.name in names]
    shapes += [Point(pt(*ref["point"])) for ref in refs if "point" in ref]  # project.json's frame has y down
    # every piece: one wholly off the outline lies on another loop, and the box, so the ROI, would stretch toward it
    if not copper or board.outline is not None and not shapely.intersects(board.outline, copper).all():
        raise KrsError("E_CHAIN_OFF_OUTLINE", nets=", ".join(chain.nets))
    x0, y0, x1, y1 = shapely.total_bounds(shapes)
    grow = expand_h * substrate_h(zs, layers)
    roi = box(x0 - grow, y0 - grow, x1 + grow, y1 + grow)
    if board.outline is not None and not board.outline.buffer(OUTLINE_GRID).contains(roi):
        roi = roi.intersection(board.outline)
    roi = shapely.set_precision(roi, 1e-6)
    coarse = coarse_cell(f_max, max(s.eps_r for s in zs if s.eps_r is not None))
    m = margin_scale * (WALL_MM + WALL_CELLS * coarse)
    x0, y0, x1, y1 = roi.bounds
    walls = tuple(round(v, 6) for v in (x0 - m, x1 + m, y0 - m, y1 + m, zs[0].z0 - m, zs[-1].z1 + m))
    crop = box(walls[0] - CROP_MM, walls[2] - CROP_MM, walls[1] + CROP_MM, walls[3] + CROP_MM)
    return Region(roi, walls, shapely.set_precision(crop, 1e-6), coarse)


def air_cell(f_max: float) -> float:
    """An antenna's air cell, λ(f_max)/20, in mm (Stage 3 design 5.3)."""
    return C0 * 1e3 / f_max / 20


def air_gap(f_lo: float) -> float:
    """An antenna's default air gap, λ/4 at f_lo, in mm (Stage 3 design 5.2)."""
    return round(C0 * 1e3 / f_lo / 4, 6)


def board_region(board: Board, chain: Chain, ports: list[dict], zs: tuple[Slab, ...], f_max: float,
                 expand_h: float = REACH_H) -> Region:
    """An antenna's region (Stage 3 design 5.2, 5.3): build_region's ROI at `expand_h`, which is the measured region
    (the antenna's copper takes the feed net, a chain net); the walls are the board's box, its outline's and every
    piece of its copper's bounds, grown by one coarse cell in x and y, and the stack's faces grown by one in z, so no
    copper edge sits on a wall; the crop is the walls' box, which every piece of copper lies inside, so nothing is
    clipped. Every coordinate goes to 1e-6 mm."""
    measured = build_region(board, chain, ports, zs, f_max, expand_h)
    copper = [t.polygon() for t in board.tracks] + [a.polygon for a in board.areas]
    copper += [p.polygon for p in board.all_pads() if p.layers]
    x0, y0, x1, y1 = shapely.total_bounds([board.outline, *copper])  # no outline (None) adds nothing
    c = measured.coarse
    walls = tuple(round(v, 6) for v in (x0 - c, x1 + c, y0 - c, y1 + c, zs[0].z0 - c, zs[-1].z1 + c))
    return Region(measured.roi, walls, box(walls[0], walls[2], walls[1], walls[3]), c)
