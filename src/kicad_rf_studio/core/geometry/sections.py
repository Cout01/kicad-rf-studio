# SPDX-License-Identifier: GPL-3.0-or-later
"""The measured sections (spec 5.5), in mm: the straight runs of the measured nets along x or y, which fit2d and the
2D readout of `cost` check, and the cross-section cut at the middle of each one."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace

import shapely
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.cs2d import CrossSection, Rect
from kicad_rf_studio.core.geometry.copper import Piece
from kicad_rf_studio.core.geometry.mask import MaskModel, smeared_epsilon
from kicad_rf_studio.core.geometry.zstack import Slab, substrate_h
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import XY

ALIGN = 1.5e-6  # mm: ends one 1e-6 mm grid step apart still share x or y; the half step is float noise
REACH = 1e4  # mm, half the cut a gap is looked for along: past any crop
BOX_H = 10  # the cross-section's box runs this many substrate heights past the line's edges and past the stack
MODES = ("none", "exact", "smeared")


@dataclass(frozen=True)
class Section:
    """A straight run of a measured net's track along `axis` ("x" or "y"), from `start` to `end` (the lower end
    first), `length` between its track ends. `gap` is the smaller distance from its copper to other copper on its
    layer across the cut at its middle, None when the cut meets none in the crop."""
    net: str
    layer: str
    axis: str
    start: XY
    end: XY
    width: float
    gap: float | None
    length: float


def _merge(spans: Iterable[tuple[float, float]]) -> list[list[float]]:
    """`spans` (lo, hi) in order, those that touch or overlap joined."""
    out: list[list[float]] = []
    for lo, hi in sorted(spans):
        if out and lo <= out[-1][1] + ALIGN:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def _cut(sec: Section, half: float) -> tuple[LineString, int, float]:
    """The cut through the middle of `sec`, perpendicular to it and `half` long either side of its centre line; the
    index of the coordinate along the cut (y for a run along x) and the centre line's place on it."""
    mx, my = (sec.start[0] + sec.end[0]) / 2, (sec.start[1] + sec.end[1]) / 2
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
    strips = _strips(pieces, sec.layer, line, k)
    # the copper under the middle of the run, or the track's own width if the pieces hold none there
    lo, hi = next(((a, b) for net, a, b in strips if net == sec.net and a <= c <= b),
                  (c - sec.width / 2, c + sec.width / 2))
    gaps = [a - hi for _, a, _ in strips if a >= hi] + [lo - b for _, _, b in strips if b <= lo]
    return round(min(gaps), 6) if gaps else None


def sections(board: Board, nets: Iterable[str], pieces: list[Piece]) -> tuple[list[Section], list[tuple[str, dict]]]:
    """The straight runs of the tracks of `nets`, by net in that order, then by place. A track whose ends share x or y
    within 1e-6 mm is one, joined on its layer with the collinear tracks of its width that it touches. Any other track
    of a net (a 45° segment, an arc) is staircased in the model: one W_STAIRCASED per net. `pieces` give the gaps."""
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
            notes.append(("W_STAIRCASED", {"net": net}))
        found = []
        for (layer, axis, at, width), spans in runs.items():
            for lo, hi in _merge(spans):
                lo, hi = round(lo, 6), round(hi, 6)
                ends = ((lo, at), (hi, at)) if axis == "x" else ((at, lo), (at, hi))
                sec = Section(net, layer, axis, *ends, width, None, round(hi - lo, 6))
                found.append(replace(sec, gap=_gap(sec, pieces)))
        out += sorted(found, key=lambda s: (s.start, s.end, s.layer))
    return out, notes


def cross_section(sec: Section, pieces: list[Piece], zs: tuple[Slab, ...], mask: MaskModel | None, mode: str,
                  dz0: float | None = None) -> CrossSection:
    """The cut perpendicular to `sec` at its middle, BOX_H substrate heights past its edges either side, through every
    piece it meets there: copper of `sec`'s net is the signal, any other conductor ground, each as thick as its layer.
    The dielectric layers span the cut. The mask (Decisions): `mode` "none", or no `mask`, leaves it out; "exact" fills
    the gaps between the outer conductors over their z-cell and lays a coat t_m thick on the copper and the gaps;
    "smeared" fills the same gaps and smears the coat over the first z-cell, `dz0` thick, as the FDTD model does. The
    box runs BOX_H substrate heights past the stack too, in air."""
    if mode not in MODES:
        raise ValueError(f"cross-section mode {mode!r} is not one of {MODES}")
    m = BOX_H * substrate_h(zs)
    line, k, c = _cut(sec, sec.width / 2 + m)
    lo, hi = round(c - sec.width / 2 - m, 6), round(c + sec.width / 2 + m, 6)
    conductors = [Rect(a, b, s.z0, s.z1, role="signal" if net == sec.net else "ground")
                  for s in zs if s.kind == "copper" for net, a, b in _strips(pieces, s.copper, line, k)]
    dielectrics = [Rect(lo, hi, s.z0, s.z1, s.eps_r) for s in zs if s.kind == "dielectric"]
    if mask is not None and mode != "none":
        t, eps = (mask.t_m, mask.eps_m) if mode == "exact" else (dz0, smeared_epsilon(mask.t_m, mask.eps_m, dz0))
        z0 = mask.z_coat0 if mask.side == "F" else round(mask.z_coat0 - t, 6)  # the coat runs away from the board
        dielectrics += [Rect(a, b, *mask.z_fill, mask.eps_m) for a, b in _spans(mask.gap_fill, line, k)]
        dielectrics += [Rect(a, b, z0, round(z0 + t, 6), eps) for a, b in _spans(mask.coat, line, k)]
    box = (lo, hi, round(zs[0].z0 - m, 6), round(zs[-1].z1 + m, 6))
    return CrossSection(tuple(conductors), tuple(dielectrics), box)
