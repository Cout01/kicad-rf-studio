# SPDX-License-Identifier: GPL-3.0-or-later
"""An emission project's overrides (Stage 5 design 5.9): its filled voids and added vias, explicit geometry in the
importer's frame (mm, y up), applied to the board at load before the geometry is built, every via checked again for
clearance."""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace

from shapely import unary_union
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.kicad.board import Board, CopperArea, Via
from kicad_rf_studio.core.kicad.shapes import XY, circle, valid_polygons

CLEARANCE = 0.2  # mm: KiCad's default netclass clearance, as f3's probes used it, for an added via and for a fill


def span(board: Board, layers: Sequence[str]) -> list[str]:
    """The copper layers from `layers[0]` to `layers[1]`, in board.copper_layers order: a via's rod spans them all."""
    i, j = sorted(board.copper_layers.index(layer) for layer in layers)
    return list(board.copper_layers[i:j + 1])


def _copper(board: Board, layer: str, net: str, zones: bool) -> Iterator[BaseGeometry]:
    """The copper of every net but `net` on `layer`: its tracks, the pads with copper there, its areas (the zone fills
    only when `zones`) and the discs of the vias whose span holds it."""
    # ponytail: every call walks the whole board; an STRtree per layer when a search calls it at many points
    yield from (t.polygon() for t in board.tracks if t.layer == layer and t.net != net)
    yield from (p.polygon for p in board.all_pads() if layer in p.layers and p.net != net)
    yield from (a.polygon for a in board.areas if a.layer == layer and a.net != net and (zones or a.source != "zone"))
    yield from (circle(v.at, v.diameter / 2) for v in board.vias if v.net != net and layer in span(board, v.layers))


def blocker(board: Board, at: XY, radius: float, net: str, layers: Sequence[str]) -> str | None:
    """Why a via of `net` and `radius` at `at`, joining `layers`, cannot be added: "T_OVERRIDE_COPPER" when its disc
    grown by CLEARANCE meets, on a layer of its span, another net's track, pad, copper graphic or via (another net's
    zone fill takes an antipad instead); else "T_OVERRIDE_EDGE" when that disc is not within the outline; else None."""
    disc = circle(at, radius + CLEARANCE)
    if any(disc.intersects(c) for layer in span(board, layers) for c in _copper(board, layer, net, zones=False)):
        return "T_OVERRIDE_COPPER"
    if board.outline is None or not board.outline.covers(disc):
        return "T_OVERRIDE_EDGE"
    return None


def apply_overrides(board: Board, overrides: list[dict]) -> list[tuple[str, dict]]:
    """Adds project.json's `overrides` to `board`, entry n's uuid "override-<n>", and returns their notes. The vias
    first: one `blocker` refuses is left out with W_OVERRIDE_REFUSED, its point in KiCad's frame; one kept cuts the disc
    of its radius + CLEARANCE out of every other net's zone fill on its span, as KiCad's refill would. Then the fills:
    each is its polygon less every other net's copper on its layer grown by CLEARANCE, as areas of source "override",
    one per part (none when nothing is left)."""
    notes = []
    for n, o in enumerate(overrides):
        if o["kind"] != "via":
            continue
        (x, y), r, net = o["at_mm"], o["diameter_mm"] / 2, o["net"]
        if reason := blocker(board, (x, y), r, net, o["layers"]):
            notes.append(("W_OVERRIDE_REFUSED", {"from": o["from"], "x_mm": f"{x:.3f}", "y_mm": f"{0.0 - y:.3f}",
                                                 "reason": reason}))
            continue
        board.vias.append(Via((x, y), o["diameter_mm"], o["drill_mm"], tuple(o["layers"]), net, f"override-{n}"))
        hole, layers, areas = circle((x, y), r + CLEARANCE), span(board, o["layers"]), []
        for a in board.areas:
            if a.source == "zone" and a.net != net and a.layer in layers and a.polygon.intersects(hole):
                areas += [replace(a, polygon=p) for p in valid_polygons(a.polygon.difference(hole))]  # the antipad
            else:
                areas.append(a)
        board.areas = areas
    for n, o in enumerate(overrides):
        if o["kind"] == "fill":
            others = unary_union([c.buffer(CLEARANCE) for c in _copper(board, o["layer"], o["net"], zones=True)])
            fill = Polygon(o["polygon_mm"]["exterior"], o["polygon_mm"]["holes"]).difference(others)
            board.areas += [CopperArea(o["layer"], o["net"], p, "override", f"override-{n}")
                            for p in valid_polygons(fill)]
    return notes
