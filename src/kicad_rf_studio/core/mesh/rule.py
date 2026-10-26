# SPDX-License-Identifier: GPL-3.0-or-later
"""The mesh rule (spec 5.4), in mm: the cell size d, the lines at protected copper edges, the lines of each axis, the
merge, and the grading that keeps neighbouring cells within RATIO of each other."""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right, insort
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping
from typing import TYPE_CHECKING

import numpy as np

from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines

if TYPE_CHECKING:
    from kicad_rf_studio.core.geometry.sections import Section
    from kicad_rf_studio.core.geometry.zstack import Slab

RATIO = 1.3  # the largest ratio of neighbouring cells
GROW = 1.25  # the ratio the rule grades at itself, under RATIO, so the 1e-6 mm grid cannot push a pair over it
GRID_TOL = 3e-6  # mm: rounding to the 1e-6 mm grid moves big − RATIO·small by up to 2.3e-6 mm
EPS = 1e-9  # mm: float noise in the distance of two lines on the 1e-6 mm grid; exactly a merge distance apart is apart
LEAD = 1 / 16  # ×d: the least lead of an edge's outside line over its inside line (the edge lint fails a tie)
SERVE = 7 / 16  # ×d: same-side edges within this of a cell's deepest edge keep its d/4 inside line (a pair joins here)
CUT_SERVE = 1 / 3  # ×d: SERVE for a cut edge's cell: from here the d/8 line splits the pair, which reads better
ALONE = 11 / 6  # ×d: where no edge of the other side is this near; there the gap step and collisions need d/8
FACE = 4  # ×d: a cut edge that faces the other side's metal across a gap this narrow (n·d at a section) wants d/8
THIN = 4.2  # ×d: a substrate under this deep keeps such an edge's d/4 line: much of its field goes down, as a strip's
SLOT_IN: float | None = None  # ×d: a slot edge's inside depth (design 2026-10-26 §5.1); None: d/4, the rule as built
SLOT_GATE = 0.0  # ×d: the slot depth holds where the substrate h is this deep or more; 0: everywhere
SLOT_SERVED = False  # True: also a served cell of several edges whose deepest is a slot edge; False: lone cells only
MAX_ROUNDS = 10_000  # _grade's guard; 3000 random axes (both passes of each) converged within 16 rounds

Edge = tuple[float, int]  # a protected copper edge: its position and the sign that points into its metal


def cell_size(sections: list[Section], fallback_width: float, n: int, lam_min: float,
              fallback_gap: float | None = None, h: float | None = None) -> float:
    """d: the narrowest width or gap of the measured nets over `n`, at most 0.9·λ_min/20. The sections give the widths
    and gaps of the straight runs; `fallback_width`, the narrowest track of the measured nets, always counts too, so a
    net with no straight run (all 45° or arcs) still gets a width and a narrower bend is not missed, and so does
    `fallback_gap`, the narrowest gap of the tracks no section measures (Geometry.track_gap). `h`, the substrate under
    the measured nets, is a microstrip's gap to its plane (R-P2-23): the fringing field at a strip's edge spreads over
    about h, which an edge cell wider than h cannot resolve (coupon_ms 3 mm wide at d = w/2: fit2d −5.37 %). A size of
    0 is no feature to resolve (copper that touches, a dielectric with no thickness: the checks report both), so d is
    never 0, which ran build_mesh into a MemoryError after about 60 s."""
    sizes = [fallback_width, *(s.width for s in sections), *(s.gap for s in sections), fallback_gap, h]
    return min(min((v for v in sizes if v is not None and v > 0), default=math.inf) / n, 0.9 * lam_min / 20)


def edge_lines(edge: float, inside: int, d: float) -> tuple[float, float]:
    """The lines at a protected copper edge, solid or sheet (R-P2-18), (inner, outer): d/4 into the metal and 3d/4 out
    of it. `inside` (−1 or +1) points from the edge into the metal."""
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
        while k < len(pins) and pins[k][0] == r and pins[k][1] - run[-1] < tol - EPS:
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
    fixed = [(s.z0 + s.z1) / 2 for s in cu] + [(f + v) / 2 for f, v in zip(faces, outside) if v in lines]
    return _grade(_smooth(lines, coarse, dz / 3, fixed), fixed, coarse, lines)


def xy_lines(edges: list[Edge], extent: tuple[float, float], walls: tuple[float, float], free: Iterable[float],
             d: float, coarse: float, prefer: Collection[Edge] = (), force: Collection[Edge] = (),
             h: float = math.inf) -> tuple[np.ndarray, np.ndarray]:
    """The lines of one in-plane axis from wall to wall, and the rule's own lines among them: the walls, the edge
    lines, the protected extent's ends and its fill.
    - Every protected copper edge, (position, inside sign), gets its lines from _patterns (`prefer`, `force` and `h`,
      the substrate under the measured nets: there).
    - The `extent` (lo, hi; empty when lo > hi) is filled at d or finer, graded from its smallest cells. Its ends are
      lines but in an edge's cell (between the pinned lines around it), where one would sit on the edge or nearer it
      than its inside line, and the lint's one re-mesh could not move it (verifier).
    - A `free` coordinate (unprotected copper, a rod, the lid) at d or more from the extent and in no edge's cell gets
      a line where it lies at least the local graded cell, min(coarse, d + (1 − 1/GROW)·its distance to the extent),
      from every other line: a vertex line nearer than that would only make the grading refine back towards d.
    - smooth_mesh_lines grades the rest up to `coarse`, and _grade holds every pair of neighbouring cells within RATIO
      but where the larger holds an edge, which its pattern fixes. Only these lines (and the fill) are re-placed.
    - The slot depth (plan 6) holds on an axis only where its lines pass the edge lint and the d/3 merge outright;
      elsewhere, as where its grading does not converge, the axis keeps the lines of the rule as built."""
    if SLOT_IN is not None:  # ponytail: one failing check reverts the whole axis; per cell, if boards lose the depth so
        try:
            out = _axis(edges, extent, walls, free, d, coarse, prefer, force, h, True)
            if not _faults(out[0], edges, d):
                return out
        except RuntimeError:  # _grade's guard
            pass
    return _axis(edges, extent, walls, free, d, coarse, prefer, force, h, False)


def lint_hits(lines: np.ndarray, edges: Iterable[Edge], d: float) -> list[tuple[float, str]]:
    """The protected copper `edges` of one axis that fail the edge lint of spec 5.5 on its `lines`, each with its
    reason: a line on it ("on_edge"), its nearest inside line nearer than d/8 ("inside_too_close"), or its first
    outside line no farther than that inside line ("outside_closer"): a tie ties the outer line to the metal under
    openEMS's inclusive rule (T7). The distances go to 1e-9 mm, so that a tie on the 1e-6 mm grid compares equal
    (float noise put either line ahead)."""
    hits = []
    for e, inside in edges:
        off = np.round((lines - e) * inside, 9)  # > 0 inside the metal
        near_in, near_out = off[off > 0].min(initial=np.inf), -off[off < 0].max(initial=-np.inf)
        reason = ("on_edge" if (off == 0).any() else "inside_too_close" if near_in < d / 8
                  else "outside_closer" if near_out <= near_in else None)
        if reason:
            hits.append((e, reason))
    return hits


def _faults(lines: np.ndarray, edges: list[Edge], d: float) -> bool:
    """Whether an axis's `lines` fail the axes harness's own checks: the edge lint of its `edges`, or a cell under the
    d/3 merge. No RATIO check: _grade returns only lines that pass it with the edges held."""
    return bool(lint_hits(lines, edges, d)) or bool(np.diff(lines).min() < d / 3 - GRID_TOL)


def _axis(edges: list[Edge], extent: tuple[float, float], walls: tuple[float, float], free: Iterable[float], d: float,
          coarse: float, prefer: Collection[Edge], force: Collection[Edge], h: float,
          slot: bool) -> tuple[np.ndarray, np.ndarray]:
    """xy_lines' lines and the rule's own lines among them, with _patterns' slot role on (`slot`) or off."""
    pins = _patterns(edges, d, prefer, force, h, slot) | dict.fromkeys(walls, 0.0)
    lo, hi = (round(v, 6) for v in extent)
    at = np.array(sorted(pins))
    cells = set(np.searchsorted(at, [e for e, _ in edges]).tolist())

    def clear(v: float) -> bool:  # in no edge's cell
        i = int(np.searchsorted(at, v))
        return i not in cells or at[i] == v

    base = merge([*pins, *(v for v in ([lo, hi] if lo <= hi else []) if clear(v))], pins, d / 3)
    kept = list(base)
    for v in sorted({round(v, 6) for v in free if walls[0] < v < walls[1]}, key=lambda v: max(lo - v, v - hi)):
        far = max(lo - v, v - hi)
        if far >= d and clear(v):
            _add(kept, [v], min(coarse, d + (1 - 1 / GROW) * far))
    hard = np.array(kept)
    mid = (hard[1:] + hard[:-1]) / 2
    held = [e for e, _ in edges]
    lines = _grade(hard, [*held, *mid[(mid < lo) | (mid > hi)]], d, hard)  # the fill: the cells outside the extent wait
    lines = _grade(_smooth(lines, coarse, d / 3, held), held, lambda m: np.where((m >= lo) & (m <= hi), d, coarse),
                   hard)
    return lines, np.union1d(base, lines[(lines >= lo) & (lines <= hi)])


def _patterns(edges: Iterable[Edge], d: float, prefer: Collection[Edge] = (), force: Collection[Edge] = (),
              h: float = math.inf, slot: bool = True) -> dict[float, float]:
    """The pinned lines of protected copper `edges`, each with its rank (merge's: the distance from its nearest own
    edge), none closer than d/3 to another. Each edge gets an inside line, the nearest into its metal, and an outside
    line, placed so that it passes the edge lint of spec 5.5 (no line on it, the inside line d/8 or more in, the
    outside line farther than the inside one, here by LEAD·d); alone, these are edge_lines, d/4 in and 3d/4 out.
    - Same-side edges, deepest first, share one cell while no line fits between them with these margins (two edges
      under 7d/16 apart) and they span d at most. A cell within SERVE·d, and ALONE·d from the other side's edges, keeps
      its deepest edge's d/4 inside line, and 3d/4 out of it, or further so that the farthest edge leads (verifier:
      pads 20 µm wider than coupon_ms's strip put its inside line d/8 deep at d = 0.675: fit2d −6.85 %, −1.58 %
      without them). Where it holds an edge of `prefer` (a cut edge, which fit2d measures), the cut edge's pattern
      wins (R-P2-24): the cell is served only when its deepest edge is a cut edge, within CUT_SERVE·d (from d/3 on
      the d/8 line splits the pair: 150 µm end pads at d = h/2 read −0.36 %, served −3.16 %), and, where the substrate
      `h` is THIN·d deep or more, no edge of the other side faces it across a gap within FACE·d: a coplanar edge reads
      best with the shallow line, a microstrip edge, facing open space, with d/4 (recheck (i): pads with the pour
      following them read +5.11 % served at h/d = 9.5), and so does one that faces metal over a substrate a few cells
      deep, whose field goes down too (verifiers: a pour 0.7 mm off coupon_ms's strip read −5.63 % at h/d = 2); several
      cut edges get the pattern centred between the deepest and the farthest (a wider segment of the strip: +4.49 %
      with the deepest's). In other shared cells the inside line is d/8 inside the deepest, as the gap step and
      collisions with the other side's lines need (d/4 failed the lint on 59 of 6000 random axes), and the outside
      line 3d/4 outside the farthest, or further out so that this edge's outside line leads (verifier: a shared pair
      failed the lint once the edges spanned d/2 or more). Between two cells one line serves
      both: the outer edge's own inside line, else the inner edge's own outside line, else the middle of where a line
      fits; or as shallow as allowed when the outer edge's cell will grow. Edges 4d/3 apart or more keep their own
      lines. Past the span cap no line may fit (a staircase of close steps over d): the outer edge then keeps its own
      inside line and the cell's far edge fails the lint, which a finer preset fixes, rather than cells many d wide
      that pass it. Same-side edges with an edge of the other side between them are not a staircase but the far sides
      of a strip and of what faces it: they neither join nor share a line (verifier (A): a 0.4d strip 0.02d from the
      metal it faces failed the lint).
    - With SLOT_IN set and `slot` (plan 6), a slot edge, one that the other side's metal faces across a gap within
      FACE·d, has its inside line SLOT_IN·d deep (at least d/8 + GRID_TOL) where `h` ≥ SLOT_GATE·d. It applies in a
      cell of its own or, with SLOT_SERVED, in any served cell it is the deepest edge of. Its outside line stays 3d/4
      out.
    - Facing edges across a gap (metal below one, above the next) whose outside lines cross, or come within d/3,
      share one line in the gap, or none where the gap is too narrow for one: then each edge's outside line is the
      other's inside line. Two outside lines 3d/4 out put one of them inside the other edge's cell (copper gaps of
      0.6d to d failed the lint). Only outside lines move: a line that is also another edge's inside line stays
      that edge's (verifier (A): it jumped to the facing edge's inside line, 0.88d from its edge).
    - Lines closer than d/3 become the first of these that keeps every edge of the collision passing the lint: the
      one whose edge is nearer (Decisions), of equally near ones those of `prefer` (the edges at a measured section's
      cut, which fit2d reads) first; their mean; the others, nearer edges first. With none, the mean, else the nearest
      (verifier: the mean moved coupon_gcpw_pads' GND inside lines along the whole line where keeping them passed).
    - An edge of `force` (the lint's one re-mesh) gets edge_lines, and no other line stays in its cell or within d/3
      of it, so that the re-mesh changes something."""
    own: dict[Edge, list[float]] = {}  # each edge's [inside line, outside line]
    lead, deep = LEAD * d, d / 8 + GRID_TOL  # an outside line's least lead over the inside one; an inside line's depth

    def window(top: float, low: float, nxt: float) -> tuple[float, float]:
        """Where a line between a cell (`top`, its lowest edge `low`) and the next edge `nxt` may go, in u."""
        return nxt + deep, min(2 * low - top - lead, top - d / 3)

    def joins(top: float, low: float, nxt: float) -> bool:
        lo_w, hi_w = window(top, low, nxt)
        return lo_w > hi_w

    def near(opp: list[float], u: float, v: float) -> bool:
        """No edge of the other side (`opp`, in u, sorted) lies between u and v: they are a staircase."""
        return bisect_left(opp, u) == bisect_left(opp, v)

    def facing(opp: list[float], u: float) -> bool:
        """An edge of the other side (`opp`, in u, sorted) lies within FACE·d outside u: its metal faces u's."""
        return bisect_left(opp, u - FACE * d) < bisect_left(opp, u)

    for side in (-1, 1):
        us = sorted((side * e for e, s in edges if s == side), reverse=True)  # u grows into the metal: deepest first
        opp = sorted(side * e for e, s in edges if s != side)
        top, k = None, 0
        while k < len(us):
            j, served, slotted = k + 1, False, False
            if top is None:  # a cell of its own: d/4 in, also for the same-side edges within reach where it is alone
                top, served = us[k] + d / 4, True
                reach = (CUT_SERVE if (side * us[k], side) in prefer else SERVE) * d
                while j < len(us) and us[k] - us[j] <= reach and near(opp, us[j - 1], us[j]):
                    j += 1
                cut = [(side * u, side) in prefer for u in us[k:j]]
                faces = h >= THIN * d and facing(opp, us[k])
                if j < len(us) and near(opp, us[j - 1], us[j]) and joins(top, us[j - 1], us[j]) or j > k + 1 and (
                        bisect_left(opp, us[k] - ALONE * d) < bisect_right(opp, us[k] + ALONE * d)
                        or any(cut) and (not cut[0] or faces)):
                    top, served, j = us[k] + deep, False, k + 1  # else d/8 in, as shallow as the lint allows
                elif slot and SLOT_IN is not None and h >= SLOT_GATE * d and facing(opp, us[k]) and (
                        SLOT_SERVED or j == k + 1):
                    top, slotted = us[k] + max(SLOT_IN * d, deep), True  # a slot edge's own depth (plan 6)
                elif sum(cut) > 1:  # several cut edges: their pattern, centred between the deepest and the farthest
                    top = max(top - (us[k] - us[k + max(i for i, c in enumerate(cut) if c)]) / 2, us[k] + deep)
            cell, k = us[k:j], j
            while k < len(us) and cell[0] - us[k] <= d and near(opp, cell[-1], us[k]) and joins(top, cell[-1], us[k]):
                cell.append(us[k])  # no line fits before us[k], and the cell spans d at most
                k += 1
            low = cell[-1]
            bottom, shared = min(cell[0] - 3 * d / 4 if slotted else top - d if served else low - 3 * d / 4,
                                 2 * low - top - lead), None
            if k < len(us) and near(opp, low, us[k]) and bottom - (us[k] + d / 4) < d / 3:  # share one line with the
                lo_w, hi_w = window(top, low, us[k])  # next cell, whose own inside line is near; empty past the cap
                shallow = k + 1 < len(us) and near(opp, us[k], us[k + 1]) and joins(us[k] + d / 4, us[k], us[k + 1])
                bottom = shared = next((v for v in ((lo_w,) if shallow else (us[k] + d / 4, low - 3 * d / 4))
                                        if lo_w <= v <= hi_w), (lo_w + hi_w) / 2 if lo_w <= hi_w else us[k] + d / 4)
            for u in cell:
                own[side * u, side] = [round(side * top, 6), round(side * bottom, 6)]
            top = shared
    order = sorted(own)
    for a, b in zip(order, order[1:]):  # facing edges across a gap: metal below a, above b
        oa, ob = own[a][1], own[b][1]
        if a[1] < 0 < b[1] and ob - oa < d / 3 and all(e[0] <= a[0] for e in own if own[e][1] == oa) \
                and all(e[0] >= b[0] for e in own if own[e][1] == ob):  # (not past the other edge: a run beyond it)
            lo_w, hi_w = 2 * a[0] - own[a][0] + lead, 2 * b[0] - own[b][0] - lead
            m = next((v for v in (oa, ob) if lo_w <= v <= hi_w), round((lo_w + hi_w) / 2, 6))
            new = {oa: m, ob: m} if lo_w <= hi_w else {oa: own[b][0], ob: own[a][0]}
            for e in own:  # outside lines only: oa may also be the next same-side cell's inside line
                own[e][1] = new.get(own[e][1], own[e][1])
    users: dict[float, list[Edge]] = defaultdict(list)
    for e, pair in own.items():
        for v in pair:
            users[v].append(e)

    def rank(v: float) -> float:
        return min(abs(v - e) for e, _ in users[v])

    def passes(e: Edge, pair: list[float]) -> bool:  # the lint for an edge whose inside and outside lines are `pair`
        inside, outside = ((v - e[0]) * e[1] for v in pair)  # (on the grid, a line placed `deep` in is d/8 or more in)
        return d / 8 <= inside < -outside - GRID_TOL

    prefer, lines, pins, k = set(prefer), sorted(users), {}, 0
    while k < len(lines):
        run = [lines[k]]
        k += 1
        while k < len(lines) and lines[k] - run[-1] < d / 3 - EPS:
            run.append(lines[k])
            k += 1
        r = min(map(rank, run))
        best = sorted((v for v in run if rank(v) <= r + GRID_TOL), key=lambda v: (not prefer.intersection(users[v]), v))
        mean = [round(sum(best) / len(best), 6)] * (len(best) > 1)
        hit = {e for v in run for e in users[v]}
        keep = next((x for x in best + mean + sorted(set(run) - set(best), key=rank)
                     if all(passes(e, [x if w in run else w for w in own[e]]) for e in hit)), (mean or best)[0])
        for e in hit:
            own[e] = [keep if w in run else w for w in own[e]]
        pins[keep] = r
    for e, side in force:
        inner, outer = (round(v, 6) for v in edge_lines(e, side, d))
        pins = {v: r for v, r in pins.items() if not min(inner, outer) - d / 3 < v < max(inner, outer) + d / 3}
        pins |= {inner: d / 4, outer: 3 * d / 4}
    return pins


def _add(kept: list[float], lines: Iterable[float], tol: float) -> list[float]:
    """`kept`, sorted, with each of `lines` added where it lies at least `tol` from every kept line."""
    for v in lines:
        i = bisect_left(kept, v)
        if (i == 0 or v - kept[i - 1] >= tol - EPS) and (i == len(kept) or kept[i] - v >= tol - EPS):
            insort(kept, v)
    return kept


def _smooth(lines: np.ndarray, coarse: float, tol: float, held: Iterable[float] = ()) -> np.ndarray:
    """`lines` and smooth_mesh_lines' grading of their gaps above `coarse`, on the 1e-6 mm grid; of its new lines,
    those within `tol` of a given one, or in a cell that holds a `held` point (a cell the rule fixes, which at the λ
    cap can be wider than `coarse`: R-P2-22), are dropped."""
    new = np.setdiff1d(np.round(smooth_mesh_lines(lines, coarse, RATIO), 6), lines)
    i = np.clip(np.searchsorted(lines, new), 1, len(lines) - 1)
    keep = (np.minimum(new - lines[i - 1], lines[i] - new) >= tol) & ~np.isin(i, np.searchsorted(lines, list(held)))
    return np.union1d(lines, new[keep])


def _grade(lines: np.ndarray, fixed: Iterable[float], cap: float | Callable[[np.ndarray], np.ndarray],
           hard: Iterable[float] | None = None) -> np.ndarray:
    """`lines` re-filled until no cell is above its `cap` (a number, or a function of the middle of the run of the cell,
    below) and every pair of neighbouring cells is within RATIO, but where the larger cell holds a `fixed` point: those
    cells are never split. The `hard` lines (all of `lines` when None, and always both ends) stay; an offending cell has
    the whole run between the hard lines around it re-filled by _pieces, matched to the cells beyond them. Splitting
    one cell at a
    time cannot grade a jump over several cells: its pieces within RATIO of a small neighbour leave its large one
    over RATIO, which then splits in turn, down the axis (verifier: cells of 0.002d to 0.1d, or no end at all).
    smooth_mesh_lines cannot hold the ratio either: it never splits a gap at or below its max_res and fills each larger
    one alone (T9 fix ruling). Each round re-fills the runs beside the smallest neighbours first, never two
    neighbouring runs, and puts the lines on the 1e-6 mm grid."""
    lines = np.asarray(lines, float)
    hard = lines if hard is None else np.union1d(np.fromiter(hard, float), lines[[0, -1]])
    fixed = np.sort(np.fromiter(fixed, float))
    caps = cap if callable(cap) else (lambda m: np.full(np.shape(m), float(cap)))
    for _ in range(MAX_ROUNDS):
        c = np.diff(lines)
        run = np.searchsorted(hard, (lines[1:] + lines[:-1]) / 2) - 1  # the run between hard lines that holds each cell
        cap_k = caps((hard[run] + hard[run + 1]) / 2)  # one cap a run is judged and filled by, or it never settles
        held = np.zeros(len(c), bool)
        i = np.searchsorted(lines, fixed) - 1
        held[i[(i >= 0) & (i < len(c))]] = True
        nb = np.minimum(np.r_[np.inf, c[:-1]], np.r_[c[1:], np.inf])
        bad = np.flatnonzero(~held & ((c > cap_k + GRID_TOL) | (c > RATIO * nb + GRID_TOL)))
        if not len(bad):
            return lines
        done: set[int] = set()
        keep, new = np.ones(len(lines), bool), []
        for k in bad[np.argsort(nb[bad], kind="stable")]:
            if done.isdisjoint((run[k] - 1, run[k], run[k] + 1)):
                done.add(run[k])
                f, last = np.searchsorted(run, run[k]), np.searchsorted(run, run[k], side="right") - 1
                lo, hi = hard[run[k]], hard[run[k] + 1]
                keep[f + 1:last + 1] = False
                p = _pieces(hi - lo, c[f - 1] if f else math.inf, c[last + 1] if last + 1 < len(c) else math.inf,
                            float(cap_k[k]), bool(f and held[f - 1]), bool(last + 1 < len(c) and held[last + 1]))
                new.append(lo + np.cumsum(p)[:-1])
        lines = np.unique(np.round(np.concatenate([lines[keep], *new]), 6))
    raise RuntimeError("the mesh grading did not converge")


def _pieces(g: float, a: float, b: float, cap: float, held_a: bool = False, held_b: bool = False) -> list[float]:
    """The sizes, in order, that fill a run `g` long between neighbour cells `a` and `b` (math.inf: none): two fronts
    grow by GROW from the neighbours' sizes (at most `cap`) until they meet, then fit the run: down, their largest
    pieces cut to one level, so the end pieces keep the neighbours' sizes (verifier (B): scaled down whole, the fill
    beside a d/3 cell fell to 0.27d, under spec 5.4's d/3 merge); or scaled up without the last piece, the innermost
    of the front that grew last. Every piece is at most `cap` and each end piece at most RATIO times its neighbour; of
    the two, the one whose end pieces are also no less than 1/RATIO of their neighbours wins, then the one scaled least.
    A held neighbour (a cell the rule fixes, exempt as the larger of a pair) sets no such floor, nor can one that no
    piece reaches. A run too short for both floors (1.3 to 1.54 times its neighbours) gets the fit down, and _grade
    then re-fills the neighbour's run to match."""
    left, right, nl, nr, total, last_left = [], [], min(a, cap), min(b, cap), 0.0, True
    while total < g - GRID_TOL:
        last_left = nl <= nr
        if last_left:
            left.append(nl)
            total, nl = total + nl, min(nl * GROW, cap)
        else:
            right.append(nr)
            total, nr = total + nr, min(nr * GROW, cap)
    runs = [left + right[::-1]]
    if len(runs[0]) > 1:
        runs.append(left[:-1] + right[::-1] if last_left else left + right[-2::-1])
    fits = [(g / sum(r), [p * g / sum(r) for p in r]) for r in runs]
    if sum(runs[0]) > g:  # the level that the pieces above it, cut to it, leave the run's length
        s, i = sorted(runs[0]), len(runs[0]) - 1
        while i and (g - sum(s[:i])) / (len(s) - i) < s[i - 1]:
            i -= 1
        fits[0] = (fits[0][0], [min(p, (g - sum(s[:i])) / (len(s) - i)) for p in runs[0]])

    def under(p: list[float]) -> bool:  # exactly: the 1e-6 mm grid then moves a piece by at most 1e-6, within GRID_TOL
        return max(p) <= cap + 1e-9 and p[0] <= RATIO * a + 1e-9 and p[-1] <= RATIO * b + 1e-9

    def over(p: list[float]) -> bool:
        return (held_a or p[0] >= a / RATIO - GRID_TOL) and (held_b or p[-1] >= b / RATIO - GRID_TOL)

    return min([f for f in fits if under(f[1])] or fits[:1], key=lambda f: (not over(f[1]), abs(math.log(f[0]))))[1]
