# SPDX-License-Identifier: GPL-3.0-or-later
"""The measured sections (spec 5.5), in mm: the straight runs of the measured nets along x or y, which fit2d and the
2D readout of `cost` check, and the cross-section cut across each one where it is bare line."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace

import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.cs2d import CrossSection, Rect
from kicad_rf_studio.core.geometry.copper import SIMPLIFY, Piece
from kicad_rf_studio.core.geometry.mask import MaskModel, smeared_epsilon
from kicad_rf_studio.core.geometry.zstack import Slab, substrate_h
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import XY

ALIGN = 1.5e-6  # mm: ends one 1e-6 mm grid step apart still share x or y; the half step is float noise
REACH = 1e4  # mm, half the cut a gap is looked for along: past any crop
BOX_H = 10  # cross_section's default box_h: the box runs this many substrate heights past the line and the stack
NEAR = 1.0  # track widths past a run's edges within which its copper must not change where it is cut
MODES = ("none", "exact", "smeared")


@dataclass(frozen=True)
class Section:
    """A straight run of a measured net's track along `axis` ("x" or "y"), from `start` to `end` (the lower end
    first), `length` between its track ends. `cut` is the point of its centre line where it is bare line (_bare_cut),
    and `gap` the smaller distance from its copper to other copper on its layer across the cut there, None when the
    cut meets none in the crop. Copper of another net, or of none, that touches the run is no gap (_gap)."""
    net: str
    layer: str
    axis: str
    start: XY
    end: XY
    width: float
    gap: float | None
    length: float
    cut: XY


def _merge(spans: Iterable[tuple[float, float]]) -> list[list[float]]:
    """`spans` (lo, hi) in order, those that touch or overlap joined."""
    out: list[list[float]] = []
    for lo, hi in sorted(spans):
        if out and lo <= out[-1][1] + ALIGN:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def _bare_cut(sec: Section, board: Board, pieces: list[Piece]) -> XY:
    """The middle of `sec`'s longest bare stretch; `sec.cut` (the run's middle) when it has none. Along a bare stretch
    the copper of its layer within NEAR track widths of the track does not change (it has no edge there but along the
    run), no other copper of its net touches the track and no pad with copper on its layer comes that near: the
    cross-section is the line's (spec 5.5), not that of a stub, a via, a part or another track's end, any of which can
    sit at the middle."""
    # ponytail: an edge counts as along the run while it moves under 2 SIMPLIFY across it, so the flat chord at the tip
    # of another net's round end or via ring stays free (about 0.15 mm on a 0.6 mm end); it wins only on a run with no
    # longer bare stretch. Upgrade: stop the whole along-span of any other-net part that ends inside the band.
    a, k = (0, 1) if sec.axis == "x" else (1, 0)  # the coordinates along and across the run
    lo, hi, c, w = sec.start[a], sec.end[a], sec.start[k], sec.width

    def band(d0: float, d1: float) -> Polygon:  # the run from lo to hi, from d0 to d1 off its centre line
        return box(lo, c + d0, hi, c + d1) if a == 0 else box(c + d0, lo, c + d1, hi)

    near, e = band(-w / 2 - NEAR * w, w / 2 + NEAR * w), w / 2 + 2 * SIMPLIFY
    rim = band(-e - SIMPLIFY, -e).union(band(e, e + SIMPLIFY))  # just past the track's edges and their simplification
    stops = [p.polygon.intersection(near).bounds[a::2] for p in board.all_pads()
             if sec.layer in p.layers and p.polygon.intersects(near)]
    for pc in pieces:
        if pc.layer == sec.layer and pc.polygon.intersects(near):
            for ring in shapely.get_rings(shapely.get_parts(pc.polygon.intersection(near))):
                xy = shapely.get_coordinates(ring)
                stops += [(min(p[a], q[a]), max(p[a], q[a])) for p, q in zip(xy, xy[1:])
                          if abs(p[k] - q[k]) > 2 * SIMPLIFY]
            if pc.net == sec.net:
                stops += [g.bounds[a::2] for g in shapely.get_parts(pc.polygon.intersection(rim)) if g.area > 0]
    free, x = [], lo
    for s0, s1 in sorted(stops):
        free.append((x, s0))
        x = max(x, s1)
    x0, x1 = max([*free, (x, hi)], key=lambda f: f[1] - f[0])
    if x1 <= x0:
        return sec.cut
    m = round(float(x0 + x1) / 2, 6)
    return (m, c) if a == 0 else (c, m)


def _cut(sec: Section, half: float) -> tuple[LineString, int, float]:
    """The cut through `sec.cut`, perpendicular to `sec` and `half` long either side of its centre line; the index of
    the coordinate along the cut (y for a run along x) and the centre line's place on it."""
    mx, my = sec.cut
    if sec.axis == "x":
        return LineString([(mx, my - half), (mx, my + half)]), 1, my
    return LineString([(mx - half, my), (mx + half, my)]), 0, mx


def _spans(g: BaseGeometry, line: LineString, k: int) -> list[tuple[float, float]]:
    """Where `line` crosses `g`, as (lo, hi) along coordinate `k`, on the 1e-6 mm grid."""
    return [(round(float(c.min()), 6), round(float(c.max()), 6))
            for p in shapely.get_parts(g.intersection(line)) if p.length > 0
            for c in [shapely.get_coordinates(p)[:, k]]]


def _strips(pieces: list[Piece], layer: str, line: LineString, k: int) -> list[tuple[str, float, float]]:
    """Where `line` crosses the copper of `layer`, as (net, lo, hi): a net's pieces that touch (as a hole split leaves
    them) make one strip."""
    spans: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for pc in pieces:
        if pc.layer == layer:
            spans[pc.net] += _spans(pc.polygon, line, k)
    return [(net, lo, hi) for net, s in spans.items() for lo, hi in _merge(s)]


def _gap(sec: Section, pieces: list[Piece]) -> float | None:
    line, k, c = _cut(sec, REACH)
    # other copper that touches the run's body (within ALIGN) is a short or floating copper, never a gap, as in
    # staircase_gap: at the cut the simplification can leave a hair (0.36 µm) between it and the track
    body = LineString([sec.start, sec.end]).buffer(sec.width / 2, cap_style="flat")
    strips = _strips([pc for pc in pieces if pc.net == sec.net or not shapely.dwithin(pc.polygon, body, ALIGN)],
                     sec.layer, line, k)
    # the copper under the middle of the run, or the track's own width if the pieces hold none there
    lo, hi = next(((a, b) for net, a, b in strips if net == sec.net and a <= c <= b),
                  (c - sec.width / 2, c + sec.width / 2))
    gaps = [a - hi for _, a, _ in strips if a >= hi] + [lo - b for _, _, b in strips if b <= lo]
    return round(min(gaps), 6) if gaps else None


def sections(board: Board, nets: Iterable[str], pieces: list[Piece]) -> tuple[list[Section], list[tuple[str, dict]]]:
    """The straight runs of the tracks of `nets`, by net in that order, then by place. A track whose ends share x or y
    within 1e-6 mm is one, joined on its layer with the collinear tracks of its width that it touches. Any other track
    of a net (a 45° segment, an arc) is staircased in the model, which P0-A measured past the 5 % Z0 budget: one
    E_STAIRCASED per net, a geometry gate (D-27). `pieces` and the board's pads place each cut, `pieces` give the
    gaps."""
    out, notes = [], []
    for net in nets:
        runs: dict[tuple[str, str, float, float], list[tuple[float, float]]] = defaultdict(list)
        staircased = False
        for t in board.tracks:
            if t.net != net or t.start == t.end:  # a zero-length track runs nowhere: no run, nothing staircased
                continue
            (x0, y0), (x1, y1) = t.start, t.end
            if t.mid is None and abs(y1 - y0) < ALIGN:
                runs[t.layer, "x", round(y0, 6), t.width].append((min(x0, x1), max(x0, x1)))
            elif t.mid is None and abs(x1 - x0) < ALIGN:
                runs[t.layer, "y", round(x0, 6), t.width].append((min(y0, y1), max(y0, y1)))
            else:
                staircased = True
        if staircased:
            notes.append(("E_STAIRCASED", {"net": net}))
        found = []
        for (layer, axis, at, width), spans in runs.items():
            for lo, hi in _merge(spans):
                lo, hi = round(lo, 6), round(hi, 6)
                ends = ((lo, at), (hi, at)) if axis == "x" else ((at, lo), (at, hi))
                mid = tuple(round((u + v) / 2, 6) for u, v in zip(*ends))
                sec = Section(net, layer, axis, *ends, width, None, round(hi - lo, 6), mid)
                sec = replace(sec, cut=_bare_cut(sec, board, pieces))
                found.append(replace(sec, gap=_gap(sec, pieces)))
        out += sorted(found, key=lambda s: (s.start, s.end, s.layer))
    return out, notes


def staircase_gap(board: Board, nets: Iterable[str], pieces: list[Piece]) -> float | None:
    """The narrowest gap of the measured `nets` that no section measures: from each of their staircased tracks (a 45°
    segment or an arc) to the copper of the other nets on its layer; None without such a track or copper. The d rule
    takes it with the sections' widths and gaps (spec 5.4: the smallest width or gap of the measured nets): from the
    width alone, coupon_gcpw_45 got d = 0.3 and a mesh that joined LINE and GND at grid nodes (verifier). Copper that
    touches the track is a short, which the connectivity check reports, not a gap."""
    # ponytail: other nets only, so a staircased hairpin's gap to its own arm is not seen (a section's gap counts it).
    nets, gaps = set(nets), []
    for t in board.tracks:
        (x0, y0), (x1, y1) = t.start, t.end
        if t.net in nets and t.start != t.end and (t.mid is not None or min(abs(x1 - x0), abs(y1 - y0)) >= ALIGN):
            other = [pc.polygon for pc in pieces if pc.layer == t.layer and pc.net != t.net]
            gaps += [g for g in shapely.distance(t.polygon(), other) if g > 0]
    return round(float(min(gaps)), 6) if gaps else None


def cross_section(sec: Section, pieces: list[Piece], zs: tuple[Slab, ...], mask: MaskModel | None, mode: str,
                  dz0: float | None = None, box_h: float = BOX_H) -> CrossSection:
    """The cut perpendicular to `sec` at `sec.cut`, `box_h` substrate heights past its edges either side, through every
    piece it meets there, each as thick as its layer: the strip of `sec`'s net under its centre line is the signal,
    and any other conductor ground, its net's other copper too (as signal, a hairpin's two arms read as one line of
    half the Z0, and an arm cut at the box's side touched its 0 V face). The dielectric layers span the cut, and so
    does each inner copper layer (a copper layer between two dielectrics), at the mean εr of those two: on a pressed
    board their resin fills its gaps. The copper wins where it lies, since cs2d holds a conductor's nodes whatever
    dielectric is under it. The outer copper layers are in air, with the mask (Decisions): `mode` "none", or no
    `mask`, leaves it out; "exact" fills the gaps between the outer conductors over their z-cell and lays a coat t_m
    thick on the copper and the gaps; "smeared" fills the same gaps and smears the coat over the first z-cell, `dz0`
    thick, as the FDTD model does. The box runs `box_h` substrate heights past the stack too, in air: the default BOX_H
    reads a microstrip's Z0 about 0.7 % under a 45 h box, which P0-A's 2D references take (D-14); fit2d's two solves
    share the box, so its bias cancels there."""
    if mode not in MODES:
        raise ValueError(f"cross-section mode {mode!r} is not one of {MODES}")
    m = box_h * substrate_h(zs)
    line, k, c = _cut(sec, sec.width / 2 + m)
    lo, hi = round(c - sec.width / 2 - m, 6), round(c + sec.width / 2 + m, 6)
    own = (sec.net, sec.layer)
    conductors = [Rect(a, b, s.z0, s.z1, role="signal" if (net, s.copper) == own and a <= c <= b else "ground")
                  for s in zs if s.kind == "copper" for net, a, b in _strips(pieces, s.copper, line, k)]
    dielectrics = [Rect(lo, hi, s.z0, s.z1, s.eps_r) for s in zs if s.kind == "dielectric"]
    dielectrics += [Rect(lo, hi, s.z0, s.z1, (a.eps_r + b.eps_r) / 2) for a, s, b in zip(zs, zs[1:], zs[2:])
                    if s.kind == "copper" and a.kind == b.kind == "dielectric"]
    if mask is not None and mode != "none":
        t, eps = (mask.t_m, mask.eps_m) if mode == "exact" else (dz0, smeared_epsilon(mask.t_m, mask.eps_m, dz0))
        z0 = mask.z_coat0 if mask.side == "F" else round(mask.z_coat0 - t, 6)  # the coat runs away from the board
        dielectrics += [Rect(a, b, *mask.z_fill, mask.eps_m) for a, b in _spans(mask.gap_fill, line, k)]
        dielectrics += [Rect(a, b, z0, round(z0 + t, 6), eps) for a, b in _spans(mask.coat, line, k)]
    box = (lo, hi, round(zs[0].z0 - m, 6), round(zs[-1].z1 + m, 6))
    return CrossSection(tuple(conductors), tuple(dielectrics), box)
