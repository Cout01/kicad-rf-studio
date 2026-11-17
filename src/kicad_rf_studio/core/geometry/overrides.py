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
STEP_MM, ANGLE_DEG = 0.1, 15  # R2's search (return_via): its radius grows by STEP_MM mm, its angle by ANGLE_DEG degrees


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


def _plane(board: Board, layer: str, net: str) -> BaseGeometry:
    """The union of `net`'s zone fills on `layer`."""
    return unary_union([a.polygon for a in board.areas if (a.source, a.layer, a.net) == ("zone", layer, net)])


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


def return_via(board: Board, at: XY, r_signal: float, d: float, size: tuple[float, float, tuple[str, str]], net: str,
               planes: Sequence[str]) -> XY | None:
    """R2's return via (design 5.9) for a signal via of radius `r_signal` at `at`: the first point at radius ρ =
    r_signal + size's radius + CLEARANCE, growing by STEP_MM while ρ ≤ d, at each ρ the angles 0°, ANGLE_DEG, … < 360°
    from +x, counter-clockwise, where a via of `net` and `size` (via_size's) clears, `blocker` None, and the zone fills
    of `net` on both `planes` layers cover its disc; None when no point does."""
    r, fills = size[0] / 2, [_plane(board, layer, net) for layer in planes]
    rho0 = r_signal + r + CLEARANCE
    # ponytail: 24 points a radius, and blocker walks the whole board at each one the fills cover; an STRtree per layer
    # if a large board with no room turns slow
    for k in range(math.floor(round((d - rho0) / STEP_MM, 9)) + 1):  # rounded: (2 - 0.8) / 0.1 is 11.999999999999998
        rho = rho0 + k * STEP_MM
        for deg in range(0, 360, ANGLE_DEG):
            p = (at[0] + rho * math.cos(math.radians(deg)), at[1] + rho * math.sin(math.radians(deg)))
            if all(fill.covers(circle(p, r)) for fill in fills) and blocker(board, p, r, net, size[2]) is None:
                return p
    return None


def _fill(board: Board, f: dict, pitch: float) -> tuple[list[dict], list[tuple[str, dict]]]:
    """R1's variant (the pitch unused): the hole of U, the union of the zone fills of (ref_layer, ref_net), that holds
    the finding's place, filled with ref_net less every other net's copper on ref_layer grown by CLEARANCE, an entry
    per part. No such hole, or no part left, is E_OVERRIDE_NONE (T_OVERRIDE_NOT_A_VOID): the run crosses a split
    between two nets or the plane's edge."""
    layer, net, (x, y) = f["ref_layer"], f["ref_net"], f["at_mm"]
    at = Point(x, 0.0 - y)  # review.json's KiCad frame to the importer's
    plane = _plane(board, layer, net)
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


def _return(board: Board, f: dict, pitch: float) -> tuple[list[dict], list[tuple[str, dict]]]:
    """R2's variant (the pitch unused), for a change between two layers of one net: one via of that net, the planes',
    of via_size's size, at return_via's point within the finding's d of the signal via, the finding's net's via at
    at_mm (1 µm), joining from_layer's and to_layer's planes. E_OVERRIDE_NONE: T_OVERRIDE_TWO_NETS for a change between
    two nets, which only a capacitor would join (deferred), and T_OVERRIDE_NO_ROOM with no point."""
    p, (x, y) = f["params"], f["at_mm"]
    if p["from_net"] != p["to_net"]:
        raise KrsError("E_OVERRIDE_NONE", finding=f["id"], reason="T_OVERRIDE_TWO_NETS")
    # ponytail: via_size's layers are taken as given, so a net whose most common via is blind may get a return that
    # misses a plane; a check that span(board, size[2]) holds both layers if such a board turns up
    plane, size = p["from_net"], via_size(board, p["from_net"])
    # the review's sha256 is this board's file's, so the via it found is there
    signal = next(v for v in board.vias if v.net == f["net"] and math.dist(v.at, (x, 0.0 - y)) <= 1e-3)
    at = return_via(board, signal.at, signal.diameter / 2, f["limit"], size, plane, (p["from_layer"], p["to_layer"]))
    if at is None:
        raise KrsError("E_OVERRIDE_NONE", finding=f["id"], reason="T_OVERRIDE_NO_ROOM")
    return [{"kind": "via", "at_mm": list(at), "diameter_mm": size[0], "drill_mm": size[1], "layers": list(size[2]),
             "net": plane, "from": f["id"]}], []


def _fence(board: Board, f: dict, pitch: float) -> tuple[list[dict], list[tuple[str, dict]]]:
    """R3's variant, a fence along the stretch R3 measured (the controller's ruling on Task 12: the whole centre lines
    put vias inside a connector): S is the finding's tracks' centre lines less R3's own exclusions, the union of
    exclusions(board, classify(board)) grown by EXCLUDE_H·h_mm, then merged, within limit + w/2 of the outline's
    boundary. A point Q every `pitch` along each line of S from its start moves toward its nearest boundary point B, to
    w/2 + (|QB| − w/2)/2 from Q, halfway across the gap between the track's copper and the edge (builder's choice,
    design 6), w the widest of the finding's tracks whose line holds Q. A via of via_size(ref_net) there is kept when
    `blocker` is None and ref_net's zone fills on ref_layer cover its disc; otherwise it is left out with
    W_OVERRIDE_REFUSED, T_OVERRIDE_OFF_PLANE for the plane. None kept is E_OVERRIDE_NONE (T_OVERRIDE_NO_ROOM)."""
    # here, so that pipeline's load imports no review; classify with no options, as the review's _load does
    from kicad_rf_studio.core.kicad.tracer import classify
    from kicad_rf_studio.core.review.planes import centre_line
    from kicad_rf_studio.core.review.rules import EXCLUDE_H, exclusions

    net, ids, edge = f["ref_net"], set(f["kiids"]["tracks"]), board.outline.boundary  # R3 finds nothing without one
    # ponytail: h_mm is review.json's, rounded to 1e-3, so the hulls may grow up to 1.5 µm off R3's ref.h; R3's own h
    # needs the plane map, which needs the stackup make_overrides is not given
    cut = shapely.union_all(exclusions(board, classify(board))).buffer(EXCLUDE_H * f["h_mm"])
    tracks = [(t, centre_line(t).difference(cut)) for t in board.tracks if t.uuid in ids]
    s = shapely.line_merge(shapely.union_all([line.intersection(edge.buffer(f["limit"] + t.width / 2))
                                              for t, line in tracks]))
    (diameter, drill, layers), fill = via_size(board, net), _plane(board, f["ref_layer"], net)
    entries, notes = [], []
    for line in shapely.get_parts(s):
        for k in range(math.floor(round(line.length / pitch, 9)) + 1):  # rounded, as _densify's n
            q = line.interpolate(k * pitch)
            w = max(t.width for t, centre in tracks if centre.distance(q) < 1e-6)
            qb = shapely.shortest_line(q, edge)
            at = qb.interpolate(w / 2 + (qb.length - w / 2) / 2).coords[0]
            why = blocker(board, at, diameter / 2, net, layers) or (
                None if fill.covers(circle(at, diameter / 2)) else "T_OVERRIDE_OFF_PLANE")
            if why:
                notes.append(_refused(f["id"], at, why))
            else:
                entries.append({"kind": "via", "at_mm": list(at), "diameter_mm": diameter, "drill_mm": drill,
                                "layers": list(layers), "net": net, "from": f["id"], "pitch_mm": pitch})
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
    variant = {"R1": _fill, "R2": _return, "R3": _fence, "R4": _densify}[f["rule"]]
    return variant(board, f, pitch or review["settings"]["l_mm"])
