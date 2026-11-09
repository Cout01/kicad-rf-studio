# SPDX-License-Identifier: GPL-3.0-or-later
"""The review's rules (Stage 5 design 5.2), each finding measured against its threshold and the threshold's public
source: R1, a tagged run over a void of its reference net; R2, a tagged via that changes its reference with no return
near, for information; R3, a tagged track near the board edge; R4, a gap over L in a shield's via fence, or the board
edge's. R1 and R3 read the tagged tracks in groups, a net's tracks on one layer with one reference, less the exclusions
(5.1): the hulls of the connectors, the footprints with a keep-out and the printed antennas, grown by EXCLUDE_H·h. Every
mm value is rounded to 1e-3 before it is compared or stored."""
from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass
from functools import cache

import numpy as np
import shapely
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import substring

from kicad_rf_studio.core.kicad.board import Board, Track, Via
from kicad_rf_studio.core.kicad.shapes import XY
from kicad_rf_studio.core.kicad.tracer import Classes, _copper, _netted, _prefix, antenna_kind
from kicad_rf_studio.core.review.planes import PlaneMap, Ref, centre_line, cover, reference

RUN_MIN = 1.0  # mm: the shortest bare run R1 counts, a cut measured on three public boards (f4)
ANTIPAD = 0.6  # mm: a void within its lone hole's radius plus this is the hole's antipad (r1)
EXCLUDE_H = 3.0  # the exclusion hulls grow by this many h (r1, A4)
R2_FLOOR = 2.0  # mm: R2's d is max(L, this) (A5, f4)
EDGE_K = 2.0  # R3's k: a tagged track under k·h from the board edge (A6)
FENCE_REACH = 1.0  # mm: R4's fence is the ground vias this near its line (A7, f4)
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
    net: str | None  # None for R4
    layer: str | None  # None for R4's board edge
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


def r2(board: Board, classes: Classes, pm: PlaneMap, tags: Collection[str], l_mm: float) -> list[Finding]:
    """R2, a tagged via that changes its reference, for information (design 5.2; AR-1), in board.vias order. The
    via's tracks are its net's with an end within its radius (+1 µm) and a reference, top to bottom: `from` is the
    first one's reference and `to` the last one's. Between two nets, a return is a capacitor (letters "C") whose two
    netted copper pads sit on exactly those nets, as far as its nearer pad centre; between two layers of one net, a via
    of that net whose span holds both. It fires when no return lies within d = max(L, R2_FLOOR). `classes` is not
    read."""
    d = max(round(l_mm, 3), R2_FLOOR)
    caps = [(fp.uuid, _netted(fp)) for ref, fp in board.footprints.items() if _prefix(ref) == "C"]

    def span(v: Via) -> set[str]:  # the copper layers between a via's two
        at = [pm.layers.index(layer) for layer in v.layers]
        return set(pm.layers[min(at):max(at) + 1])

    found = []
    for v in board.vias:
        if v.net not in tags:
            continue
        sides = sorted([(t, ref) for t in board.tracks if t.net == v.net
                        and round(min(math.dist(t.start, v.at), math.dist(t.end, v.at)) - v.diameter / 2, 3) <= 1e-3
                        and (ref := reference(pm, t.layer, centre_line(t)))], key=lambda s: pm.layers.index(s[0].layer))
        if not sides:
            continue
        frm, to = sides[0][1], sides[-1][1]
        if frm.net != to.net:  # a capacitor between the two nets is their return (r5; Olney's rule 15)
            path, kind = "T_EMC_RETURN_CAP", "footprints"
            returns = [(min(math.dist(p.center, v.at) for p in pads), uuid) for uuid, pads in caps
                       if sorted(p.net for p in pads) == sorted((frm.net, to.net))]
        elif frm.layer != to.layer:
            path, kind = "T_EMC_RETURN_VIA", "vias"
            returns = [(math.dist(u.at, v.at), u.uuid) for u in board.vias
                       if u.net == frm.net and {frm.layer, to.layer} <= span(u)]
        else:
            continue
        nearest = min(returns, default=None)
        return_mm = None if nearest is None else round(nearest[0], 3)
        if return_mm is not None and return_mm <= d:
            continue
        kiids = {"tracks": sorted({t.uuid for t, _ in sides}), "vias": [v.uuid], "zones": [], "pads": [],
                 "footprints": []}
        if nearest is not None:
            kiids[kind] = sorted({*kiids[kind], nearest[1]})
        (x, y), r = v.at, v.diameter / 2
        found.append(Finding(
            "R2", "I_EMC_REF_CHANGE",
            {"net": v.net, "from_net": frm.net, "from_layer": frm.layer, "to_net": to.net, "to_layer": to.layer,
             "path": path, "nearest": "T_NONE" if return_mm is None else f"{return_mm:.3f} mm", "limit_mm": f"{d:.3f}"},
            v.net, sides[0][0].layer, frm, (round(x, 3), round(y, 3)),
            tuple(round(c, 3) for c in (x - r, y - r, x + r, y + r)), {"return_mm": return_mm}, d, kiids))
    return found


def return_share(d: float, h: float, b: float | None) -> float:
    """The share of a track's ideal return current that lies past a plane edge `d` from its copper (design 5.2 R3):
    over one plane `h` below, ½ − atan(d/h)/π, from Johnson and Graham's 1/(1 + (x/h)²); between planes `b` apart,
    (2/π)·atan(e^(−π·d/b)) (r5)."""
    if b is None:
        return 0.5 - math.atan(d / h) / math.pi
    return 2 / math.pi * math.atan(math.exp(-math.pi * d / b))


def r3(board: Board, groups: list[Group], edge_k: float) -> list[Finding]:
    """R3, a tagged track near the board edge (design 5.2; AR-4). A track's d is the distance from its entry in its
    group's lines to the outline's boundary, less half its width, so the exclusions apply and an empty entry is not
    measured; it is flagged when 0 < d < k·h. A group's flagged entries that meet merge into parts, one finding each,
    with d the least of its tracks'. A finding's place is the midpoint of its part's stretch within k·h + w/2 of the
    boundary, and its bounds are its tracks' copper. With no outline, R3 finds nothing."""
    if board.outline is None:
        return []
    edge, found = board.outline.boundary, []
    for g in groups:
        ref, h = g.ref, round(g.ref.h, 3)
        limit = round(edge_k * h, 3)
        flagged = [(t, line, d) for t, line in zip(g.tracks, g.lines)
                   if not line.is_empty and 0 < (d := round(line.distance(edge) - t.width / 2, 3)) < limit]
        parts: list[list] = []
        for item in flagged:  # an entry joins every part it meets, and those parts merge with it
            meets = [any(round(item[1].distance(o[1]), 3) == 0 for o in p) for p in parts]
            joined = [o for p, m in zip(parts, meets) if m for o in p]
            parts = [p for p, m in zip(parts, meets) if not m] + [[item, *joined]]
        for part in parts:
            tracks, d = [t for t, _, _ in part], min(d for _, _, d in part)
            stretch = shapely.line_merge(shapely.union_all(
                [line.intersection(edge.buffer(limit + t.width / 2)) for t, line, _ in part]))
            # a buffer's round join is chords, 16 a quadrant, up to 0.12 % inside its arc: a part whose nearest point
            # faces a concave corner of the outline that close to k·h + w/2 misses the band, and is placed there
            mid = stretch.interpolate(0.5, normalized=True) if not stretch.is_empty else shapely.get_point(
                shapely.shortest_line(shapely.union_all([line for _, line, _ in part]), edge), 0)
            share = round(100 * return_share(d, h, ref.b), 1)
            found.append(Finding(
                "R3", "W_EMC_EDGE",
                {"net": g.net, "layer": g.layer, "d_mm": f"{d:.3f}", "k": f"{edge_k:g}", "kh_mm": f"{limit:.3f}",
                 "h_mm": f"{h:.3f}", "ref_layer": ref.layer, "share_pct": f"{share:.1f}"},
                g.net, g.layer, ref, (round(mid.x, 3), round(mid.y, 3)),
                tuple(round(float(v), 3) for v in shapely.total_bounds([t.polygon() for t in tracks])),
                {"d_mm": d, "h_mm": h, "k": edge_k, "share_pct": share}, limit,
                {"tracks": sorted({t.uuid for t in tracks}), "vias": [], "zones": [], "pads": [], "footprints": []}))
    return found


def r4(board: Board, classes: Classes, l_mm: float, edge_fence: bool) -> list[Finding]:
    """R4, a gap over L in a via fence (design 5.2; A7; D-1): the shields in sorted order, then, with `edge_fence` and
    an outline, the board edge. A shield's line is the ring of the convex hull of its copper pads on its side, as
    find_lid takes it, covered where those pads lie (within 1e-6); the edge's is the outline's exterior, which covers
    itself. The fence is the vias of a ground net within FENCE_REACH of the line, in order along it. Between two
    consecutive vias A and B, cyclic, the gap is min(covered, max(|AB|, along − dA − dB)): `along` is the line from A's
    projection to B's, `covered` its covered part, and dA and dB the vias' distances to the line, so a side and a corner
    read the pitch, an opening 0 and a cluster the covered stretch it leaves. With fewer than two vias, the whole
    covered length is one gap. A gap over L fires, at the middle of its stretch of the line, or of the whole line with
    fewer than two vias."""
    l_mm = round(l_mm, 3)
    fences = []  # (fence, layer, footprint KIIDs, line, the copper that covers the line within 1e-6)
    for ref in sorted(classes.shields):
        fp = board.footprints[ref]
        pads = shapely.union_all([p.polygon for p in fp.pads if fp.layer in p.layers])
        fences.append((ref, fp.layer, (fp.uuid,), pads.convex_hull.exterior, pads))
    if edge_fence and board.outline is not None:
        fences.append(("T_EMC_BOARD_EDGE", None, (), board.outline.exterior, board.outline))
    found = []
    for fence, layer, footprints, ring, copper in fences:
        cover, n = copper.buffer(1e-6), ring.length
        vias = sorted((v for v in board.vias
                       if v.net in classes.gnd and round(ring.distance(Point(v.at)), 3) <= FENCE_REACH),
                      key=lambda v: ring.project(Point(v.at)))
        if len(vias) < 2:
            gaps = [(ring.intersection(cover).length, [ring], n / 2, vias)]
        else:
            s, gaps = [ring.project(Point(v.at)) for v in vias], []
            for a, b, s0, s1 in zip(vias, vias[1:] + vias[:1], s, s[1:] + [s[0] + n]):  # the last pair wraps round
                stretch = [substring(ring, s0, min(s1, n))] + ([substring(ring, 0, s1 - n)] if s1 > n else [])
                covered = sum(part.intersection(cover).length for part in stretch)
                inner = s1 - s0 - ring.distance(Point(a.at)) - ring.distance(Point(b.at))  # along − dA − dB
                gaps.append((min(covered, max(math.dist(a.at, b.at), inner)), stretch, ((s0 + s1) / 2) % n, [a, b]))
        for gap, stretch, mid, pair in gaps:
            gap = round(gap, 3)
            if gap <= l_mm:
                continue
            lambdas, at = round(gap / (20 * l_mm), 2), ring.interpolate(mid)
            found.append(Finding(
                "R4", "W_EMC_FENCE_PITCH",
                {"fence": fence, "gap_mm": f"{gap:.3f}", "lambdas": f"{lambdas:.2f}", "l_mm": f"{l_mm:.3f}"},
                None, layer, None, (round(at.x, 3), round(at.y, 3)),
                tuple(round(float(v), 3) for v in shapely.total_bounds(stretch)), {"gap_mm": gap, "lambdas": lambdas},
                l_mm, {"tracks": [], "vias": sorted({v.uuid for v in pair}), "zones": [], "pads": [],
                       "footprints": list(footprints)}))
    return found
