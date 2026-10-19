# SPDX-License-Identifier: GPL-3.0-or-later
"""Solder-mask openings: where the mask leaves the board bare, as polygons in mm with y up."""
from shapely import unary_union
from shapely.geometry import MultiPolygon

from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import valid_polygons


def mask_openings(board: Board, side: str) -> MultiPolygon:
    """The openings of the solder mask on `side` ("F" or "B"), a MultiPolygon that is empty when nothing opens.

    A pad that lists the side's mask opens its outline grown by its margin, with or without copper (a hole listed on
    the masks opens, a paste-only pad does not). The margin is the first one that is set of the pad's own, its
    footprint's and the board's pad_to_mask_clearance, so a zero wins over a larger value further out, and a negative
    margin shrinks the opening. A pad whose file lists no copper layer (a mask-only pad) takes no margin, as in
    pcbnew. Shapes drawn on the mask layer open it as they are. When the board has a solder_mask_min_width, every
    web of mask narrower than it is closed, which merges the openings on both sides."""
    # ponytail: two corners cut, each a known ceiling.
    # - Vias are not opened (their tenting is not read), so an untented via is covered here. Upgrade: read the
    #   tenting into Via and add its pad to `shapes`.
    # - A mask-only unplated hole (np_thru_hole whose file lists no copper) takes the margin like any pad, where
    #   pcbnew gives it 0. `layers` is empty for it as for a hole that covers its pad, which pcbnew does give the
    #   margin, so the check below leaves np_thru_hole alone. Upgrade: record on Pad whether its file lists copper.
    shapes = list(board.mask_graphics[side])
    for fp in board.footprints.values():
        for pad in fp.pads:
            if side in pad.mask_sides:
                no_copper = pad.kind != "np_thru_hole" and not pad.layers  # pcbnew gives such a pad no margin
                margins = (0.0 if no_copper else pad.mask_margin, fp.mask_margin, board.pad_to_mask_clearance)
                shapes.append(pad.polygon.buffer(next(m for m in margins if m is not None)))
    openings = unary_union(shapes)
    if board.solder_mask_min_width > 0:
        half = board.solder_mask_min_width / 2
        openings = openings.buffer(half).buffer(-half)
    return MultiPolygon(valid_polygons(openings))
