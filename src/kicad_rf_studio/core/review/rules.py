# SPDX-License-Identifier: GPL-3.0-or-later
"""The review's rules (Stage 5 design 5.2), each finding measured against its threshold and the threshold's public
source: R1, a tagged run over a void of its reference net. A rule reads the tagged tracks in groups, a net's tracks on
one layer with one reference, less the exclusions (5.1): the hulls of the connectors, the footprints with a keep-out
and the printed antennas, grown by EXCLUDE_H·h. Every mm value is rounded to 1e-3 before it is compared or stored."""
from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass
from functools import cache

import numpy as np
import shapely
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.kicad.board import Board, Track
from kicad_rf_studio.core.kicad.shapes import XY
from kicad_rf_studio.core.kicad.tracer import Classes, _copper, antenna_kind
from kicad_rf_studio.core.review.planes import PlaneMap, Ref, centre_line, cover, reference

RUN_MIN = 1.0  # mm: the shortest bare run R1 counts, a cut measured on three public boards (f4)
ANTIPAD = 0.6  # mm: a void within its lone hole's radius plus this is the hole's antipad (r1)
EXCLUDE_H = 3.0  # the exclusion hulls grow by this many h (r1, A4)
EDGE_K = 2.0  # R3's k: a tagged track under k·h from the board edge (A6)
SOURCES: dict[str, str] = {  # each rule's source, in English: review.json's limit_source
    "R1": "LearnEMC: splitting or gapping a ground plane is almost always a bad idea; Ansys SIwave's Net Crossing "
          "Split; HyperLynx DRC's signal traces crossing plane splits; a run of 1 mm or more, measured on three "
          "public boards",
    "R2": "TI SLLA656: stitching vias within 200 mils, closer is better; Siemens: manage reference plane changes",
    "R3": "LearnEMC: route critical nets at least 2X from the board edge",
    "R4": "lambda/20 at f_max: Bahl; Harper; Archambeault"}


@dataclass
class Finding:
    """A rule's finding, in the importer's frame (mm, y up)."""
    rule: str
    code: str  # its message
    params: dict  # the message's, as text; review_board adds n, x_mm and y_mm
    net: str
    layer: str
    ref: Ref | None
    at: XY  # its place
    bounds: tuple[float, float, float, float]
    measured: dict
    limit: float
    # tracks, vias, zones, pads and footprints, each a sorted list of distinct KIIDs: a zone's covers all its fills
    kiids: dict[str, list[str]]
    id: str = ""
    n: int = 0
    tag_source: str | None = None


@dataclass(frozen=True)
class Group:
    """A net's tagged tracks on one layer with one reference: lines[i] is tracks[i]'s centre line less the
    exclusions grown by EXCLUDE_H·ref.h, possibly empty."""
    net: str
    layer: str
    ref: Ref
    tracks: tuple[Track, ...]
    lines: tuple[BaseGeometry, ...]


def exclusions(board: Board, classes: Classes) -> list[BaseGeometry]:
    """The hulls R1 and R3 leave out, in reference order (design 5.1): the convex hull of the copper pads of each
    connector and of each footprint with a keep-out, and of each printed antenna's with its copper graphics. A
    footprint gives one hull."""
    hulls = []
    for ref, fp in sorted(board.footprints.items()):
        printed = antenna_kind(board, ref) == "printed"
        if ref in classes.connectors or fp.keepout or printed:
            drawn = [a.polygon for a in board.areas if a.ref == ref] if printed else []
            hulls.append(shapely.union_all([p.polygon for p in _copper(fp)] + drawn).convex_hull)
    return hulls


def groups(board: Board, pm: PlaneMap, tags: Collection[str],
           hulls: list[BaseGeometry]) -> tuple[list[Group], list[str]]:
    """The tagged tracks of nonzero length grouped by (net, layer, reference), each reference taken from the track's
    whole centre line, and the sorted nets with a track that has no reference (AR-5). A track with another layer of
    pm.skipped at most ref.h away is left out, as is one with no reference when any layer is skipped: that layer might
    have been its reference, which W_EMC_LAYER_SKIPPED says, so its net is not named."""
    by: dict[tuple[str, str, Ref], list] = {}
    lost = set()
    for t in board.tracks:
        line = centre_line(t)
        if t.net not in tags or round(line.length, 3) == 0:
            continue
        ref = reference(pm, t.layer, line)
        if ref is None:
            if not pm.skipped:
                lost.add(t.net)
        elif not any(s != t.layer and pm.h[(t.layer, s)] <= ref.h for s in pm.skipped):
            by.setdefault((t.net, t.layer, ref), []).append((t, line))
    hull, found = shapely.union_all(hulls), []
    for (net, layer, ref), pairs in by.items():
        tracks, lines = zip(*pairs)
        cut = hull.buffer(EXCLUDE_H * ref.h)
        found.append(Group(net, layer, ref, tracks, tuple(line.difference(cut) for line in lines)))
    return found, sorted(lost)


def r1(board: Board, pm: PlaneMap, groups: list[Group], l_mm: float) -> list[Finding]:
    """R1, a tagged net over a void or split in its reference (design 5.2; AR-2): one finding per bare run of a
    group's merged lines at least RUN_MIN long, bare where no plane of the reference net covers it on any layer. The
    run's void is the connected part of the outline (with none, the cover's bounding box) less that cover which holds
    its midpoint. A void that holds exactly one via centre or plated hole with every vertex within the hole's radius
    plus ANTIPAD (+1 µm) is the hole's antipad, and its run is dropped (D-2: a via's diameter/2, a plated pad's copper
    half-extent, at least its drill/2). The extent is the void's spread along the unit normal of the run's chord."""
    l_mm = round(l_mm, 3)
    holes = [(Point(v.at), v.diameter / 2) for v in board.vias] + [
        (Point(p.at), max(p.drill / 2, shapely.hausdorff_distance(Point(p.at), p.polygon)))
        for p in board.all_pads() if p.kind == "thru_hole"]

    @cache
    def planes(net: str) -> BaseGeometry:
        return cover(pm, net)

    @cache
    def voids(net: str) -> np.ndarray:
        outline = board.outline if board.outline is not None else box(*planes(net).bounds)
        return shapely.get_parts(outline.difference(planes(net)))

    found = []
    for g in groups:
        ref = g.ref
        bare = shapely.line_merge(shapely.union_all(g.lines)).difference(planes(ref.net))
        for run in shapely.get_parts(bare):
            run_mm = round(run.length, 3)
            if run_mm < RUN_MIN:
                continue
            mid = run.interpolate(0.5, normalized=True)
            void = next((v for v in voids(ref.net) if round(v.distance(mid), 3) == 0), None)
            if void is None:  # a run off the outline, or with no outline, off the cover's bounding box
                continue
            lone = [(c, r) for c, r in holes if void.contains(c)]
            if len(lone) == 1:
                [(c, r)] = lone  # a point's hausdorff distance to a polygon is its farthest vertex's
                if round(shapely.hausdorff_distance(c, void) - r - ANTIPAD, 3) <= 1e-3:
                    continue
            (x0, y0), (x1, y1) = run.coords[0], run.coords[-1]
            # ponytail: a bare run that closes on itself has no chord, so its extent reads 0; its first segment's
            # normal if such a loop turns up
            across = shapely.get_coordinates(void) @ (y0 - y1, x1 - x0) / (math.hypot(x1 - x0, y1 - y0) or 1.0)
            extent = round(float(np.ptp(across)), 3)
            tracks ={t.uuid for t, line in zip(g.tracks, g.lines) if round(line.distance(run), 3) == 0}
            zones = {a.uuid for a in board.areas if (a.source, a.layer, a.net) == ("zone", ref.layer, ref.net)
                     and round(a.polygon.distance(run), 3) <= l_mm}
            found.append(Finding(
                "R1", "W_EMC_GAP_CROSSING",
                {"net": g.net, "layer": g.layer, "run_mm": f"{run_mm:.3f}", "ref_net": ref.net, "ref_layer": ref.layer,
                 "h_mm": f"{ref.h:.3f}", "extent_mm": f"{extent:.3f}", "l_mm": f"{l_mm:.3f}"},
                g.net, g.layer, ref, (round(mid.x, 3), round(mid.y, 3)), tuple(round(v, 3) for v in run.bounds),
                {"run_mm": run_mm, "extent_mm": extent, "l_mm": l_mm}, RUN_MIN,
                {"tracks": sorted(tracks), "vias": [], "zones": sorted(zones), "pads": [], "footprints": []}))
    return found
