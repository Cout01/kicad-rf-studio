# SPDX-License-Identifier: GPL-3.0-or-later
"""The simulation geometry of a board (spec 5.1-5.3), in mm."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # the types only: importing a submodule must not pull in the others
    from kicad_rf_studio.core.geometry.copper import Piece
    from kicad_rf_studio.core.geometry.lid import Lid
    from kicad_rf_studio.core.geometry.mask import MaskModel
    from kicad_rf_studio.core.geometry.region import Region
    from kicad_rf_studio.core.geometry.sections import Section
    from kicad_rf_studio.core.geometry.vias import Rod
    from kicad_rf_studio.core.geometry.zstack import Slab


@dataclass
class Geometry:
    """What build_geometry derives from a board and its project.json: the region, the z-stack, the copper pieces, the
    vias as rods, the F mask (None without one), the measured sections, the shield lid (None without one), every
    warning and E_ gate entry in `notes`, `track_width`, the narrowest track of the measured nets, and `track_gap`,
    sections.staircase_gap (None without a staircased track), which the d rule takes with the sections' widths and
    gaps."""
    region: Region
    zs: tuple[Slab, ...]
    pieces: list[Piece]
    rods: list[Rod]
    mask: MaskModel | None
    sections: list[Section]
    lid: Lid | None
    notes: list[tuple[str, dict]]
    track_width: float
    track_gap: float | None
