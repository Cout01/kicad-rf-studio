# SPDX-License-Identifier: GPL-3.0-or-later
"""The mesh rule (spec 5.4), in mm: the cell size d, the lines at protected copper edges, the lines of each axis, the
merge, and the grading that keeps neighbouring cells within RATIO of each other."""
from __future__ import annotations

import math
from bisect import bisect_left, insort
from collections.abc import Collection, Iterable, Mapping
from typing import TYPE_CHECKING

import numpy as np

from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines

if TYPE_CHECKING:
    from kicad_rf_studio.core.geometry.sections import Section
    from kicad_rf_studio.core.geometry.zstack import Slab

RATIO = 1.3  # the largest ratio of neighbouring cells
GROW = 1.25  # the ratio the rule grades at itself, under RATIO, so the 1e-6 mm grid cannot push a pair over it
GRID_TOL = 3e-6  # mm: rounding to the 1e-6 mm grid moves big − RATIO·small by up to 2.3e-6 mm
SHARE = 2 / 3  # same-side edges closer than SHARE·d share one pattern
MAX_ROUNDS = 10_000  # _grade's guard; random adversarial axes converge within a few hundred rounds


def cell_size(sections: list[Section], fallback_width: float, n: int, lam_min: float) -> float:
    """d: the narrowest width or gap of the measured nets over `n`, at most 0.9·λ_min/20. The sections give the widths
    and gaps of the straight runs; `fallback_width`, the narrowest track of the measured nets, always counts too, so a
    net with no straight run (all 45° or arcs) still gets a width and a narrower bend is not missed."""
    sizes = [fallback_width, *(s.width for s in sections), *(s.gap for s in sections if s.gap is not None)]
    return min(min(sizes) / n, 0.9 * lam_min / 20)


def edge_lines(edge: float, inside: int, d: float) -> tuple[float, float]:
    """The lines at a solid-copper edge, (inner, outer): d/4 into the metal and 3d/4 out of it. `inside` (−1 or +1)
    points from the edge into the metal."""
    return edge + inside * d / 4, edge - inside * 3 * d / 4


def dz0(t_m: float, d: float, h: float) -> float:
    """The first z-cell outside each copper face, max(t_m, min(d/3, h/4)): the mask, t_m thick, fits in it."""
    return max(t_m, min(d / 3, h / 4))


def merge(lines: Iterable[float], pinned: Mapping[float, float] | Collection[float], tol: float) -> np.ndarray:
    """`lines`, sorted, none closer than `tol` to another. `pinned` maps each pinned line to the distance from its own
    copper edge (a plain collection: all equal); of pinned lines closer than `tol`, the one whose edge is nearer stays
    (Decisions), and equally near ones meet at their mean, which keeps both edges' lines best. The other lines are then
    kept, in order, where they lie at least `tol` from every kept line, so a pinned line never yields to them."""
    rank = pinned if isinstance(pinned, Mapping) else dict.fromkeys(pinned, 0.0)
    lines = set(lines)
    pins = sorted((rank[v], v) for v in lines if v in rank)
    kept: list[float] = []
    k = 0
    while k < len(pins):
        r, v = pins[k]
        run = [v]
        k += 1
        while k < len(pins) and pins[k][0] == r and pins[k][1] - run[-1] < tol:
            run.append(pins[k][1])
            k += 1
        _add(kept, [round(sum(run) / len(run), 6)], tol)
    return np.array(_add(kept, sorted(lines - set(rank)), tol))


def z_lines(zs: tuple[Slab, ...], d: float, t_m: float, h: float, z_walls: tuple[float, float],
            extra: Iterable[float] = (), *, coarse: float) -> np.ndarray:
    """The z lines from wall to wall: both faces of every copper slab, so one cell spans each copper thickness, a line
    dz0 outside each of those faces and the `extra` lines; copper faces and walls never move, and the others are kept
    where they lie dz0/3 or more from every kept line. smooth_mesh_lines grades the rest up to `coarse`, and _grade
    holds every pair of neighbouring cells within RATIO but where the larger is a copper or dz0 cell, which the rule
    fixes."""
    dz = dz0(t_m, d, h)
    cu = [s for s in zs if s.kind == "copper"]
    faces = [s.z0 for s in cu] + [s.z1 for s in cu]
    outside = [round(f + side * dz, 6) for f, side in zip(faces, [-1] * len(cu) + [1] * len(cu))]
    lines = np.array(_add(sorted({*z_walls, *faces}), [*outside, *(round(v, 6) for v in extra)], dz / 3))
    lines = _smooth(lines, coarse, dz / 3)
    fixed = [(s.z0 + s.z1) / 2 for s in cu] + [(f + v) / 2 for f, v in zip(faces, outside) if v in lines]
    return _grade(lines, fixed, coarse)


def xy_lines(edges: list[tuple[float, int]], extent: tuple[float, float], walls: tuple[float, float],
             free: Iterable[float], d: float, coarse: float) -> tuple[np.ndarray, np.ndarray]:
    """The lines of one in-plane axis from wall to wall, and the rule's own lines among them, which never move: the
    walls, the edge lines, the protected extent's ends and its fill.
    - Every protected copper edge, (position, inside sign), gets edge_lines. Same-side edges closer than SHARE·d share
      one pair, d/4 inside the deepest and 3d/4 outside the farthest: two pairs there put one edge's outside line nearer
      than its inside one. Colliding lines merge (merge).
    - The `extent` (lo, hi; empty when lo > hi) is filled at d or finer, graded from its smallest cells.
    - A `free` coordinate (unprotected copper, a rod, the lid) at d or more from the extent gets a line where it lies
      at least the local graded cell, min(coarse, d + (1 − 1/GROW)·its distance to the extent), from every other line:
      a vertex line nearer than that would only make the grading refine back towards d.
    - smooth_mesh_lines grades the rest up to `coarse`, and _grade holds every pair of neighbouring cells within RATIO
      but where the larger holds an edge, which its pattern fixes."""
    pins = _patterns(edges, d) | dict.fromkeys(walls, 0.0)
    lo, hi = (round(v, 6) for v in extent)
    base = merge([*pins, *([lo, hi] if lo <= hi else [])], pins, d / 3)
    kept = list(base)
    for v in sorted({round(v, 6) for v in free if walls[0] < v < walls[1]}, key=lambda v: max(lo - v, v - hi)):
        far = max(lo - v, v - hi)
        if far >= d:
            _add(kept, [v], min(coarse, d + (1 - 1 / GROW) * far))
    lines = np.array(kept)
    mid = (lines[1:] + lines[:-1]) / 2
    held = [e for e, _ in edges]
    lines = _grade(lines, [*held, *mid[(mid < lo) | (mid > hi)]], d)  # the fill: the cells outside the extent wait
    rule = np.union1d(base, lines[(lines >= lo) & (lines <= hi)])
    return _grade(_smooth(lines, coarse, d / 3), held, coarse), rule


def _patterns(edges: list[tuple[float, int]], d: float) -> dict[float, float]:
    """The pinned lines of `edges`, each with the distance from its own edge (merge's rank)."""
    pins: dict[float, float] = {}
    for side in (-1, 1):
        run: list[float] = []
        for e in [*sorted(e for e, s in edges if s == side), math.inf]:
            if run and e - run[-1] >= SHARE * d:
                deep, far = (run[0], run[-1]) if side < 0 else (run[-1], run[0])
                for v, rank in ((edge_lines(deep, side, d)[0], d / 4), (edge_lines(far, side, d)[1], 3 * d / 4)):
                    v = round(v, 6)
                    pins[v] = min(pins.get(v, rank), rank)
                run = []
            run.append(e)
    return pins


def _add(kept: list[float], lines: Iterable[float], tol: float) -> list[float]:
    """`kept`, sorted, with each of `lines` added where it lies at least `tol` from every kept line."""
    for v in lines:
        i = bisect_left(kept, v)
        if (i == 0 or v - kept[i - 1] >= tol) and (i == len(kept) or kept[i] - v >= tol):
            insort(kept, v)
    return kept


def _smooth(lines: np.ndarray, coarse: float, tol: float) -> np.ndarray:
    """`lines` and smooth_mesh_lines' grading of their gaps above `coarse`, on the 1e-6 mm grid; of its new lines,
    those within `tol` of a given one are dropped."""
    new = np.setdiff1d(np.round(smooth_mesh_lines(lines, coarse, RATIO), 6), lines)
    i = np.clip(np.searchsorted(lines, new), 1, len(lines) - 1)
    return np.union1d(lines, new[np.minimum(new - lines[i - 1], lines[i] - new) >= tol])


def _grade(lines: np.ndarray, fixed: Iterable[float], cap: float) -> np.ndarray:
    """`lines` with lines added until no cell is above `cap` and every pair of neighbouring cells is within RATIO, but
    where the larger cell holds a `fixed` point: those cells are never split. smooth_mesh_lines cannot do this, since it
    never splits a gap at or below its max_res and fills each larger one alone, so a jump is refined on both sides
    where needed (T9 fix ruling). Each round splits the cells beside the smallest neighbours first with _pieces, never
    two neighbouring cells, and puts the lines on the 1e-6 mm grid."""
    lines = np.asarray(lines, float)
    fixed = np.sort(np.fromiter(fixed, float))
    for _ in range(MAX_ROUNDS):
        c = np.diff(lines)
        held = np.zeros(len(c), bool)
        i = np.searchsorted(lines, fixed) - 1
        held[i[(i >= 0) & (i < len(c))]] = True
        nb = np.minimum(np.r_[np.inf, c[:-1]], np.r_[c[1:], np.inf])
        split = np.flatnonzero(~held & ((c > cap + GRID_TOL) | (c > RATIO * nb + GRID_TOL)))
        if not len(split):
            return lines
        done: set[int] = set()
        new = []
        for k in split[np.argsort(nb[split], kind="stable")]:
            if k - 1 not in done and k + 1 not in done:
                done.add(k)
                a, b = (c[k - 1] if k else math.inf), (c[k + 1] if k + 1 < len(c) else math.inf)
                new.append(lines[k] + np.cumsum(_pieces(c[k], a, b, cap))[:-1])
        lines = np.unique(np.round(np.concatenate([lines, *new]), 6))
    raise RuntimeError("the mesh grading did not converge")


def _pieces(g: float, a: float, b: float, cap: float) -> list[float]:
    """The sizes, in order, that fill a cell `g` long between neighbour cells `a` and `b` (math.inf: none): each at most
    `cap`, neighbours within GROW, the piece beside the smaller neighbour within RATIO of it and, where the cell allows,
    the other end piece too, in as few pieces as that takes. Two fronts grow by GROW from the neighbours' sizes and are
    scaled to fit, or two pieces do. A cell 1.30 to 1.385 times its smaller neighbour fits neither way and is halved: its
    neighbour, then over 1.44 times the halves, splits within RATIO of them, where a best-effort split would leave it in
    the same window and the two would split each other without end."""
    if a > b:
        return _pieces(g, b, a, cap)[::-1]
    fits = []
    left, right, nl, nr, total = [], [], min(a, cap), min(b, cap), 0.0
    while total < g * RATIO:
        if nl <= nr:
            left.append(nl)
            total, nl = total + nl, min(nl * GROW, cap)
        else:
            right.append(nr)
            total, nr = total + nr, min(nr * GROW, cap)
        if len(left) + len(right) > 1 and max(*left, *right) * g / total <= cap + GRID_TOL:
            fits.append([p * g / total for p in left + right[::-1]])
    x = min(max(min(a, cap), g / (1 + GROW)), g * GROW / (1 + GROW))
    if g - x <= cap + GRID_TOL:
        fits.append([x, g - x])
    good = [p for p in fits if _within(p[0], a)]
    return min(good, key=lambda p: (not _within(p[-1], b), len(p))) if good else [g / 2, g / 2]


def _within(p: float, n: float) -> bool:
    """Whether a piece `p` long is within RATIO of a neighbour cell `n` long (math.inf: none)."""
    return n == math.inf or n / RATIO - GRID_TOL <= p <= n * RATIO + GRID_TOL
