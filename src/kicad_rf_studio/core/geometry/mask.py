# SPDX-License-Identifier: GPL-3.0-or-later
"""The solder mask (spec 5.3), in mm: in the outer copper's z-cell it fills the gaps between conductors, and its coat
on the copper and the gaps is smeared over the first z-cell outside it, dz0, which the mesh gives."""
from __future__ import annotations

from dataclasses import dataclass

import shapely
from shapely.geometry import MultiPolygon, Polygon

from kicad_rf_studio.core.geometry.copper import Piece, _grid
from kicad_rf_studio.core.geometry.zstack import Slab
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.mask import mask_openings

T_M = 0.010  # mm, the mask's thickness when the stackup gives none (spec 5.3); a missing εr is 3.3 already (Layer)


def smeared_epsilon(t_m: float, eps_m: float, dz0: float) -> float:
    """The εr of a z-cell `dz0` thick that holds `t_m` of mask of εr `eps_m` and air: (t_m·ε_m + (dz0 − t_m))/dz0.
    Raises ValueError when the mask is thicker than the cell, which the mesh rule (dz0 ≥ t_m) never lets happen."""
    if t_m > dz0:
        raise ValueError(f"a {t_m} mm mask cannot be smeared over a {dz0} mm cell")
    return (t_m * eps_m + (dz0 - t_m)) / dz0


@dataclass(frozen=True)
class MaskModel:
    """The mask on `side` ("F" or "B"), `t_m` thick, of εr `eps_m`. `gap_fill` fills the gaps between the conductors
    of the outer copper layer over its z-cell `z_fill`; `coat` lies on that copper and the gaps, over the first z-cell
    dz0 outside the copper's outer face `z_coat0`: [z_coat0, z_coat0 + dz0] on F and [z_coat0 − dz0, z_coat0] on B.
    Both are on the 1e-6 mm grid and normalised, so the model hash does not depend on the order of the board file."""
    side: str
    eps_m: float
    t_m: float
    gap_fill: MultiPolygon
    coat: MultiPolygon
    z_fill: tuple[float, float]
    z_coat0: float


def mask_model(board: Board, pieces: list[Piece], zs: tuple[Slab, ...], crop: Polygon, side: str) -> MaskModel | None:
    """The mask on `side`, or None when the stackup has none there (its outer layer on that side is not a mask). Its
    thickness and εr are the stackup mask layer's; a thickness the file leaves out reads 0 and becomes T_M. The mask
    lies on the board: `crop` cut to the outline (the crop alone when there is none), less `mask_openings`, is the
    coat; less the copper `pieces` of the outer layer too, it is the gap fill. `mask_openings`' closing
    (solder_mask_min_width) shaves about 1 µm off convex corners (accepted)."""
    mask = zs[-1] if side == "F" else zs[0]
    if mask.kind != "mask":
        return None
    copper = [s for s in zs if s.kind == "copper"][-1 if side == "F" else 0]
    on_board = crop if board.outline is None else crop.intersection(board.outline)
    coat = on_board.difference(mask_openings(board, side))
    gap_fill = coat.difference(shapely.union_all([pc.polygon for pc in pieces if pc.layer == copper.copper]))
    return MaskModel(side, mask.eps_r, round(mask.z1 - mask.z0, 6) or T_M, shapely.normalize(_grid(gap_fill)),
                     shapely.normalize(_grid(coat)), (copper.z0, copper.z1), copper.z1 if side == "F" else copper.z0)
