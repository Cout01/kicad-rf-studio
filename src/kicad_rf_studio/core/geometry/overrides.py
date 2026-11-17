# SPDX-License-Identifier: GPL-3.0-or-later
"""An emission project's overrides (Stage 5 design 5.9): its filled voids and added vias, explicit geometry in the
importer's frame (mm, y up), made from one review finding when `new` writes the variant (make_overrides), applied to
the board at load before the geometry is built (apply_overrides), every via checked again for clearance."""
from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path

import shapely
from shapely import unary_union
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.kicad.board import Board, CopperArea, Via
from kicad_rf_studio.core.kicad.shapes import XY, circle, valid_polygons
from kicad_rf_studio.core.messages import KrsError, reason
from kicad_rf_studio.core.project import board_hash

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


def _cleared(board: Board, polygon: Polygon, layer: str, net: str) -> list[Polygon]:
    """The parts of a fill `polygon` of `net` on `layer` that keep CLEARANCE from every other net's copper there, zone
    fills included."""
    others = unary_union([c.buffer(CLEARANCE) for c in _copper(board, layer, net, zones=True)])
    return valid_polygons(polygon.difference(others))


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


def _refused(finding: str, at: XY, why: str) -> tuple[str, dict]:
    """W_OVERRIDE_REFUSED for an added via of `finding` at `at`, its point shown in KiCad's frame."""
    return "W_OVERRIDE_REFUSED", {"from": finding, "x_mm": f"{at[0]:.3f}", "y_mm": f"{0.0 - at[1]:.3f}", "reason": why}


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
        if why := blocker(board, (x, y), r, net, o["layers"]):
            notes.append(_refused(o["from"], (x, y), why))
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
            fill = Polygon(o["polygon_mm"]["exterior"], o["polygon_mm"]["holes"])
            board.areas += [CopperArea(o["layer"], o["net"], p, "override", f"override-{n}")
                            for p in _cleared(board, fill, o["layer"], o["net"])]
    return notes


def read_review(path: str | Path, finding: str) -> dict:
    """review.json at `path` (Stage 5 design 5.3), UTF-8 JSON of schema 1; otherwise E_OVERRIDE_REVIEW {path, finding,
    reason}, `path` as given and `reason` the read error's (reason()) or T_REVIEW_SCHEMA."""
    file = Path(path)
    try:
        if not file.is_file():  # Windows reads a folder as PermissionError, so look before reading (as load_project)
            raise IsADirectoryError() if file.exists() else FileNotFoundError()
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:  # ValueError: UnicodeError or json.JSONDecodeError
        raise KrsError("E_OVERRIDE_REVIEW", path=str(path), finding=finding, reason=reason(e)) from None
    # ponytail: a file of schema 1 is taken to hold review_json's keys, so a hand edit that drops one ends in
    # E_INTERNAL; a key check here if that turns up
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise KrsError("E_OVERRIDE_REVIEW", path=str(path), finding=finding, reason="T_REVIEW_SCHEMA")
    return data


def via_size(board: Board, net: str) -> tuple[float, float, tuple[str, str]]:
    """The (diameter, drill, layers) an added via of `net` takes: the most common among `net`'s vias, a tie going to
    the smaller diameter; with none, KiCad's default via, 0.6 mm with a 0.3 mm drill, from the top layer to the
    bottom."""
    counts = Counter((v.diameter, v.drill, v.layers) for v in board.vias if v.net == net)
    return min(counts, key=lambda size: (-counts[size], size),
               default=(0.6, 0.3, (board.copper_layers[0], board.copper_layers[-1])))


def _fill(board: Board, f: dict, pitch: float) -> tuple[list[dict], list[tuple[str, dict]]]:
    """R1's variant (the pitch unused): the hole of U, the union of the zone fills of (ref_layer, ref_net), that holds
    the finding's place, filled with ref_net less every other net's copper on ref_layer grown by CLEARANCE, an entry
    per part. No such hole, or no part left, is E_OVERRIDE_NONE (T_OVERRIDE_NOT_A_VOID): the run crosses a split
    between two nets or the plane's edge."""
    layer, net, (x, y) = f["ref_layer"], f["ref_net"], f["at_mm"]
    at = Point(x, 0.0 - y)  # review.json's KiCad frame to the importer's
    plane = unary_union([a.polygon for a in board.areas if (a.source, a.layer, a.net) == ("zone", layer, net)])
    hole = next((h for p in shapely.get_parts(plane) for h in map(Polygon, p.interiors) if h.contains(at)), None)
    parts = [] if hole is None else _cleared(board, hole, layer, net)
    if not parts:
        raise KrsError("E_OVERRIDE_NONE", finding=f["id"], reason="T_OVERRIDE_NOT_A_VOID")
    return [{"kind": "fill", "layer": layer, "net": net,
             "polygon_mm": {"exterior": shapely.get_coordinates(p.exterior).tolist(),
                            "holes": [shapely.get_coordinates(r).tolist() for r in p.interiors]},
             "from": f["id"]} for p in parts], []


def _densify(board: Board, f: dict, pitch: float) -> tuple[list[dict], list[tuple[str, dict]]]:
    """R4's variant: A and B, the vias of kiids.vias in that order, with n = ceil(gap/pitch) − 1 vias between them at
    A + (B − A)·k/(n + 1), k = 1 to n, each of A's diameter, drill, layers and net; one `blocker` refuses is left out
    with W_OVERRIDE_REFUSED. E_OVERRIDE_NONE: T_OVERRIDE_NO_PAIR without two vias, T_OVERRIDE_PITCH for n ≤ 0,
    T_OVERRIDE_NO_ROOM with none kept."""
    vias = {v.uuid: v for v in board.vias}
    pair = [vias[u] for u in f["kiids"]["vias"] if u in vias]
    if len(pair) < 2:
        raise KrsError("E_OVERRIDE_NONE", finding=f["id"], reason="T_OVERRIDE_NO_PAIR")
    a, b = pair[:2]
    n = math.ceil(round(f["measured"]["gap_mm"] / pitch, 9)) - 1  # rounded: 0.9 / 0.3 is 3.0000000000000004, not 3
    if n <= 0:
        raise KrsError("E_OVERRIDE_NONE", finding=f["id"], reason="T_OVERRIDE_PITCH")
    entries, notes = [], []
    # ponytail: n has no cap, so a pitch of microns walks the board in blocker once per via, thousands of times; a cap
    # on n if a caller ever passes one
    for k in range(1, n + 1):
        at = (a.at[0] + (b.at[0] - a.at[0]) * k / (n + 1), a.at[1] + (b.at[1] - a.at[1]) * k / (n + 1))
        if why := blocker(board, at, a.diameter / 2, a.net, a.layers):
            notes.append(_refused(f["id"], at, why))
        else:
            entries.append({"kind": "via", "at_mm": list(at), "diameter_mm": a.diameter, "drill_mm": a.drill,
                            "layers": list(a.layers), "net": a.net, "from": f["id"], "pitch_mm": pitch})
    if not entries:
        raise KrsError("E_OVERRIDE_NONE", finding=f["id"], reason="T_OVERRIDE_NO_ROOM")
    return entries, notes


def make_overrides(board: Board, review: dict, finding: str, pitch: float | None,
                   path: str) -> tuple[list[dict], list[tuple[str, dict]]]:
    """The overrides of a variant made from finding `finding` of `review`, a review.json as read_review returns it,
    and their notes (Stage 5 design 5.9). `path` is the review file as given, which E_OVERRIDE_REVIEW names: its reason
    T_REVIEW_OTHER_BOARD when the review's board sha256 is not `board`'s file's, checked first, then
    T_REVIEW_NO_FINDING for an id the review does not hold. The pitch is `pitch` (mm), else the review's L. Every point
    read from review.json, in KiCad's frame, is taken as (x, −y), and every entry's "from" is the finding's id. The
    finding's rule picks its variant, which raises E_OVERRIDE_NONE {finding, reason} when it gives no entry."""
    if review["board"]["sha256"] != board_hash(board.path):
        raise KrsError("E_OVERRIDE_REVIEW", path=path, finding=finding, reason="T_REVIEW_OTHER_BOARD")
    f = next((x for x in review["findings"] if x["id"] == finding), None)
    if f is None:
        raise KrsError("E_OVERRIDE_REVIEW", path=path, finding=finding, reason="T_REVIEW_NO_FINDING")
    return {"R1": _fill, "R4": _densify}[f["rule"]](board, f, pitch or review["settings"]["l_mm"])
