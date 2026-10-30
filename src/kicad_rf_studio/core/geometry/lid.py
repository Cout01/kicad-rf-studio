# SPDX-License-Identifier: GPL-3.0-or-later
"""The shield lid (spec 5.2), in mm: a PEC plate over a shield's frame and PEC walls on its frame pads."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon

from kicad_rf_studio.core.geometry.copper import clean
from kicad_rf_studio.core.geometry.region import Region
from kicad_rf_studio.core.geometry.zstack import Slab
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.tracer import Classes


@dataclass(frozen=True)
class Lid:
    """The lid of shield `ref`: a `plate` at `z1` over the convex hull of its frame pads, and `walls` on the pads
    alone, from `z0`, the top copper's top face, up to `z1`, so the gaps in the frame (the connector opening) stay
    open. Both are clipped to the crop like the copper and lie on the 1e-6 mm grid."""
    ref: str
    plate: Polygon
    walls: MultiPolygon
    z0: float
    z1: float


def find_lid(board: Board, classes: Classes, region: Region, zs: tuple[Slab, ...],
             project: dict) -> tuple[Lid | None, list[tuple[str, dict]]]:
    """The lid over the ROI and its gate entry. A shield on the top side covers the ROI when its plate, the convex hull
    of its pads on the top copper, overlaps it. The lid is on when harmonics are shown, unless project.json's `lid`
    says otherwise (plan Decisions); then it is lid_height_mm high, and E_LID_HEIGHT names the covering shields when
    that is missing or not finite and above 0, as `new --lid-height` checks it (plan 3's `run` refuses on it)."""
    on = project.get("lid")
    if not (project["harmonics"] > 1 if on is None else on):
        return None, []
    # ponytail: a shield on the bottom side gets no lid, though its THT legs reach the top copper; add one under the
    # board if it matters
    top = [s for s in zs if s.kind == "copper"][-1]
    covering = {}  # ref -> (plate area over the ROI, plate, frame pads)
    for ref in sorted(r for r in classes.shields if r in board.footprints and board.footprints[r].layer == top.copper):
        frame = GeometryCollection([p.polygon for p in board.footprints[ref].pads if top.copper in p.layers])
        plate = frame.convex_hull
        if (area := plate.intersection(region.roi).area) > 0:
            covering[ref] = (area, plate, frame)
    if not covering:
        return None, []
    height = project.get("lid_height_mm")  # hand-edited: 0 put the plate on the traces, NaN on the bottom wall
    if height is None or not 0 < height < np.inf:
        return None, [("E_LID_HEIGHT", {"refs": ", ".join(covering)})]
    # ponytail: one lid, the shield over most of the ROI, or of the board for an antenna (Geometry holds one Lid); an
    # antenna's other shields are named in W_LIDS_LEFT_OUT
    ref = max(covering, key=lambda r: covering[r][0])
    _, plate, frame = covering[ref]
    return Lid(ref, clean(plate, region.crop).geoms[0], clean(frame, region.crop), top.z1,
               round(top.z1 + height, 6)), []


def snap_lid(lid: Lid, z: np.ndarray) -> Lid:
    """`lid` with its plate on the nearest line of `z`: a line of its own made 8.3 µm slivers and halved dt (spec 5.2).
    build_mesh raises the top wall over the lid first."""
    return replace(lid, z1=float(z[np.abs(z - lid.z1).argmin()]))
