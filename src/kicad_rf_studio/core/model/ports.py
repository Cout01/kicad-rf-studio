# SPDX-License-Identifier: GPL-3.0-or-later
"""The ports of the model (spec 5.6, 5.7): the two ends of each port on the board, and its box on the mesh lines."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import shapely
from shapely.geometry import Point, box

from kicad_rf_studio.core.geometry.copper import SIMPLIFY
from kicad_rf_studio.core.kicad.tracer import signal_layer, unknown_pad
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import CURVE_PORT, GRID, PORT
from kicad_rf_studio.core.project import parts

if TYPE_CHECKING:
    from collections.abc import Collection

    from shapely.geometry import Polygon
    from shapely.geometry.base import BaseGeometry

    from kicad_rf_studio.core.geometry.copper import Piece
    from kicad_rf_studio.core.geometry.zstack import Slab
    from kicad_rf_studio.core.kicad.board import Board, Pad
    from kicad_rf_studio.core.kicad.shapes import XY
    from kicad_rf_studio.core.kicad.tracer import Classes
    from kicad_rf_studio.core.mesh import Mesh


@dataclass(frozen=True)
class End:
    """A port's two ends in the board's frame (y up): the copper of its signal and of its reference, on the copper
    layer `layer`. `name` is the port's name, or the part's ref; `role` is "external" for a port of project.json's
    `ports`, else the part's role (port, curve_port or grid). `centers`, a part's only, are the centres of its
    reference and signal pads, where its CurvePort ends. `ref_layer`, an SI end's only (Stage 4 design 5.5): the
    copper layer of the plane under its pad, which makes its port vertical; None keeps the port on `layer`."""
    name: str
    signal: BaseGeometry
    reference: BaseGeometry
    layer: str
    role: str
    centers: tuple[XY, XY] | None = None
    ref_layer: str | None = None


def _pad(board: Board, name: str, uuid: str = "", layer: str | None = None) -> Pad:
    """The pad with copper whose uuid is `uuid`, else the first pad called `name` with copper on `layer`, else the
    first called `name` with copper on any layer. Raises E_UNKNOWN_PAD when there is none."""
    # ponytail: a reference by pad name alone takes the first pad of that name
    named = [p for p in board.pads(name) if p.layers]
    pads = [p for p in board.all_pads() if uuid and p.uuid == uuid and p.layers]
    pads += [p for p in named if layer in p.layers] + named
    if not pads:
        raise unknown_pad(board, name)
    return pads[0]


def _beyond(pad: Pad, at: Point) -> Polygon:
    """The box over `pad`'s span across the direction from its centre to `at`, and over its length along that
    direction beyond `at`."""
    # ponytail: the direction is taken along its larger axis; a point off a corner of the pad can leave no copper in
    # the box, and place then refuses the port (E_PORT_SPANS)
    b, d = pad.polygon.bounds, (at.x - pad.center[0], at.y - pad.center[1])
    k = 0 if abs(d[0]) >= abs(d[1]) else 1
    lo, hi = sorted(((at.x, at.y)[k], (at.x, at.y)[k] + math.copysign(b[k + 2] - b[k], d[k])))
    return box(lo, b[1], hi, b[3]) if k == 0 else box(b[0], lo, b[2], hi)


def _reference(board: Board, pieces: list[Piece], name: str, sig: Pad, layer: str, ref: dict) -> BaseGeometry:
    """The reference copper of port `name`, whose signal pad `sig` is on `layer`: the pad that `ref` ({"pad", "uuid"})
    names, or the piece of copper at its point ({"point", "layer"}, in KiCad's frame) cut to the box beyond the point
    (`_beyond`). The nearest piece counts when it lies within SIMPLIFY of the point: the pieces are simplified, and
    the point lies on the raw copper. Raises E_UNKNOWN_PAD, E_REFERENCE_LAYER (C-14: no vertical ports) and
    E_REFERENCE_POINT."""
    if "pad" in ref:
        pad = _pad(board, ref["pad"], ref["uuid"], layer)
        if layer not in pad.layers:
            raise KrsError("E_REFERENCE_LAYER", name=name, signal_layer=layer, reference_layer=pad.layers[0])
        return pad.polygon
    if ref["layer"] != layer:
        raise KrsError("E_REFERENCE_LAYER", name=name, signal_layer=layer, reference_layer=ref["layer"])
    x, y = ref["point"]
    at = Point(x, -y)  # project.json has y down, the board y up
    near = min((pc.polygon for pc in pieces if pc.layer == layer), key=at.distance, default=None)
    if near is None or near.distance(at) > SIMPLIFY:
        raise KrsError("E_REFERENCE_POINT", name=name, point=f"({x:.3f}, {y:.3f})", layer=layer)
    return near.intersection(_beyond(sig, at))


def ends(board: Board, project: dict, pieces: list[Piece]) -> list[End]:
    """The ports of `project` (project.json) in job order: its external ports in order, then the parts whose role is
    port, curve_port or grid in parts()' order (series, shunt and others; an SI project's, every line's). A port's pads
    are found by uuid, else by name (`_pad`); a part's signal is its first pad and its reference its second, on the
    signal pad's layer (`signal_layer`). A port whose reference is {"plane": layer}, an SI end's vertical port (Stage 4
    design 5.5), has its pad as its signal and its reference, and that layer as its ref_layer. Raises KrsError:
    E_NO_PORTS, E_NO_REFERENCE, E_UNKNOWN_PAD, E_REFERENCE_LAYER, E_REFERENCE_POINT, and E_ROTATED_PART for a
    curve_port while allow_curve_port is false (C-12, C-37)."""
    if not project["ports"]:
        raise KrsError("E_NO_PORTS")
    out = []
    for port in project["ports"]:
        if (ref := port["reference"]) is None:
            raise KrsError("E_NO_REFERENCE", signal=port["signal"])
        name, layer = port["name"], port["layer"]
        sig = _pad(board, port["signal"], port["signal_uuid"], layer)
        if "plane" in ref:
            out.append(End(name, sig.polygon, sig.polygon, layer, "external", ref_layer=ref["plane"]))
        else:
            out.append(End(name, sig.polygon, _reference(board, pieces, name, sig, layer, ref), layer, "external"))
    for part in parts(project).values():
        if part["role"] == CURVE_PORT and not project["allow_curve_port"]:
            raise KrsError("E_ROTATED_PART", ref=part["ref"])
        if part["role"] in (PORT, CURVE_PORT, GRID):
            sig = _pad(board, part["pads"][0])
            layer = signal_layer(board, sig)
            ref = {"pad": part["pads"][1], "uuid": ""}
            out.append(End(part["ref"], sig.polygon, _reference(board, pieces, part["ref"], sig, layer, ref), layer,
                           part["role"], (_pad(board, ref["pad"], "", layer).center, sig.center)))
    return out


def nominal_boxes(ends: list[End]) -> tuple[Polygon, ...]:
    """The convex hull of each end's signal and reference, for Protected.boxes: they widen the protected extent, so
    the mesh is at its finest across every port."""
    return tuple(e.signal.union(e.reference).convex_hull for e in ends)


def plane_under(pad: BaseGeometry, layer: str, zs: tuple[Slab, ...], pieces: list[Piece],
                nets: Collection[str]) -> str | None:
    """The copper layer of the plane a vertical port on `pad`, on copper layer `layer`, takes as its reference (Stage 4
    design 5.5): the nearest layer toward the board's middle (down from the top half, up from the bottom half, and on
    past the middle) on which the copper of one net of `nets` (the ground and power nets), its pieces' union, covers
    the pad, the 10 µm simplification allowed. None when a layer before it has any copper over the pad's footprint, or
    when no layer qualifies: no copper, an antipad or a split under the pad, or another net's copper on the way. The
    union, since the copper pipeline's hole cut splits a plane along any antipad's x into abutting pieces."""
    # ponytail: any copper over the pad's footprint on a layer on the way refuses the port, though the sheet crosses
    # only the pad's centre line; a narrower check if real pads need it
    cu = [c.copper for c in zs if c.copper]  # bottom up
    i = cu.index(layer)
    for name in cu[i - 1::-1] if i >= len(cu) / 2 else cu[i + 1:]:
        here = [pc for pc in pieces if pc.layer == name]
        if any(shapely.union_all([pc.polygon for pc in here if pc.net == net]).buffer(SIMPLIFY).covers(pad)
               for net in nets):
            return name
        if any(pc.polygon.intersection(pad).area > 0 for pc in here):  # copper over the pad, not beside it
            return None
    return None


def _apart_axis(s: tuple, r: tuple) -> int | None:
    """The in-plane axis (0 for x, 1 for y) along which the bounds `s` and `r` are apart while their spans across it
    overlap; None when they are apart on both axes or neither."""
    apart = [s[k + 2] <= r[k] or r[k + 2] <= s[k] for k in (0, 1)]  # their spans along k do not overlap
    return None if apart[0] == apart[1] else apart.index(True)


def clear_between(sig: BaseGeometry, ref: BaseGeometry, pieces: list[Piece], layer: str,
                  nets: Collection[str]) -> bool:
    """Whether a horizontal port's box between `sig` and `ref` (place's: along _apart_axis, across their spans'
    overlap) holds no copper of `layer` but of `nets`, an SI end's test (Stage 4 design 5.5): a pad between them, an
    unconnected one too, would leave the box no copper-free run (E_PORT_BOX). False when _apart_axis is None. A piece
    blocks when its intersection with the box has an area."""
    s, r = sig.bounds, ref.bounds
    p = _apart_axis(s, r)
    if p is None:
        return False
    t = 1 - p
    lo, hi = (s[p + 2], r[p]) if s[p + 2] <= r[p] else (r[p + 2], s[p])  # along p: between their facing sides
    a, b = max(s[t], r[t]), min(s[t + 2], r[t + 2])  # across: the spans' overlap
    gap = box(lo, a, hi, b) if p == 0 else box(a, lo, b, hi)
    return not any(pc.polygon.intersection(gap).area > 0 for pc in pieces if pc.layer == layer and pc.net not in nets)


def si_reference(board: Board, classes: Classes, pieces: list[Piece], zs: tuple[Slab, ...], name: str, signal: str,
                 ref: dict | None, reach: float) -> dict:
    """An SI end's reference as project.json keeps it (Stage 4 design 5.5): `ref`, v1's choice (a pad or a point),
    when its copper (_reference, for port `name`) lies within `reach` mm of pad `signal` and clear_between holds for
    them with the signal's and the ground nets; else {"plane": layer}, plane_under the pad with the ground and power
    nets; E_SI_NO_REFERENCE {pad, layer, reach_mm (:g)} when neither. The distance is checked first, on the pad's or
    the point's raw copper, so a far point never meets _reference's E_REFERENCE_POINT."""
    # ponytail: v1's first choice only; a blocked ground pad does not fall back to the next one (choose_reference's
    # rank), and a pair's two ends on one footprint may take different kinds
    sig = _pad(board, signal)
    layer = signal_layer(board, sig)
    if ref is not None:
        raw = (Point(ref["point"][0], -ref["point"][1]) if "point" in ref  # project.json has y down, the board y up
               else _pad(board, ref["pad"], ref["uuid"], layer).polygon)
        if sig.polygon.distance(raw) <= reach:
            copper = _reference(board, pieces, name, sig, layer, ref)
            if clear_between(sig.polygon, copper, pieces, layer, {sig.net, *classes.gnd}):
                return ref
    if plane := plane_under(sig.polygon, layer, zs, pieces, classes.gnd | classes.power):
        return {"plane": plane}
    raise KrsError("E_SI_NO_REFERENCE", pad=signal, layer=layer, reach_mm=f"{reach:g}")


def vertical(end: End, mesh: Mesh, zs: tuple[Slab, ...]) -> dict:
    """The vertical lumped port of `end`, an SI end over a plane (Stage 4 design 5.5): a sheet in z from the plane's
    face (end.ref_layer's slab) to the pad's (end.layer's), starting at the plane, the reference, so that openEMS's u
    is V_pad − V_plane. Across, the sheet runs along the longer side of the pad's copper shrunk by SIMPLIFY (x on a
    tie), on the lines inside that copper. It sits at the line across within the copper's bounds nearest their middle,
    a tie to the lower. Its `nodes` are the plane's cap, the pad's cap, then the plane's and the pad's far faces (the
    witnesses), the lumped port's order, all at the sheet's middle line (a tie to the lower). E_PORT_PLANE when
    end.ref_layer is the pad's own layer or no copper layer of `zs`; E_PORT_VERTICAL_BOX when no line lies inside the
    pad either way."""
    # ponytail: a sheet across the pad's centre line; a box over the whole pad would need its corners inside a rounded
    # pad's copper
    slabs = {c.copper: c for c in zs if c.copper}
    if end.ref_layer == end.layer or end.ref_layer not in slabs:
        raise KrsError("E_PORT_PLANE", name=end.name, layer=end.ref_layer, signal_layer=end.layer)
    pad, plane = slabs[end.layer], slabs[end.ref_layer]
    below = plane.z0 < pad.z0
    face, far = ((plane.z1, pad.z0), (plane.z0, pad.z1)) if below else ((plane.z0, pad.z1), (plane.z1, pad.z0))
    cu = end.signal.buffer(-SIMPLIFY)  # the solids are simplified
    b = cu.bounds
    p = int(b[3] - b[1] > b[2] - b[0])  # along the longer side, x on a tie; t = 1 - p across it
    t = 1 - p
    along, across = (mesh.x, mesh.y)[p], (mesh.x, mesh.y)[t]
    width = across[(across > b[t]) & (across < b[t + 2])]
    if not width.size:
        raise KrsError("E_PORT_VERTICAL_BOX", name=end.name)
    tc = min(width, key=lambda v: abs(v - (b[t] + b[t + 2]) / 2))  # a tie: the lower
    run = along[shapely.contains_xy(cu, *((along, tc) if p == 0 else (tc, along)))]  # the lines inside the copper
    if not run.size:
        raise KrsError("E_PORT_VERTICAL_BOX", name=end.name)
    mid = min(run, key=lambda v: abs(v - (run[0] + run[-1]) / 2))  # a tie: the lower

    def at(u: float, z: float) -> list[float]:
        """The point `u` along p, at tc across and at `z`, as [x, y, z]."""
        xy = (u, tc) if p == 0 else (tc, u)
        return [float(xy[0]), float(xy[1]), float(z)]

    return {"name": end.name, "kind": "lumped", "dir": "z", "start": at(run[0], face[0]), "stop": at(run[-1], face[1]),
            "nodes": [at(mid, z) for z in (*face, *far)], "part": end.role != "external"}


def place(end: End, mesh: Mesh, zs: tuple[Slab, ...], pieces: list[Piece]) -> dict:
    """The port of `end` on the lines of `mesh` (spec 5.6): a CurvePort for a curve_port, else a lumped port; `pieces`
    are the board's copper (geom.pieces), and those on `end.layer` are the metal the box keeps out of. The lumped port's
    box runs along the in-plane axis p on which the signal and the reference are apart while their spans (bounds) across
    it overlap, and in z over the copper slab of `end.layer`; it starts at the reference end, so that openEMS's u is
    V_signal − V_reference. openEMS keeps PEC on every edge whose midpoint lies in metal but the box's own edges along
    p, so the box holds no copper (D-45): walking from the reference's facing line to the signal's, its caps are the
    last line before, and the first line after, the first run of lines on which no node across and no midpoint between
    two of those lines lies in that metal; across, it takes the lines inside the spans' overlap, less an outer line
    whose edge outward, at a line between the caps, has its midpoint in metal; and each cap must touch, at those lines
    or midway between them, the piece of metal that holds its witness and no other. Its `nodes` are the reference cap,
    the signal cap, then the reference and signal witnesses, at the copper's top face on one line across of the box, tc:
    the one nearest the middle of the overlap's lines (a tie to the lower; chosen again among the box's lines when the
    cut took it) at which each pad keeps a line along, inside its bounds, whose point lies inside its copper shrunk by
    SIMPLIFY (D-11: the copper solids are simplified by up to SIMPLIFY). A pad's facing line is its kept line nearest
    the other pad, its witness its kept line farthest from it; a cap node may lie in air, on the box's PEC end.
    The CurvePort (C-37) runs from the reference pad's centre to the signal pad's, each on the nearest x and y lines, at
    the copper's top face; its `nodes` are those two ends. openEMS puts its one-edge port at their middle, joined to
    both by PEC curves, and orders them along its axis itself: its u is V_signal − V_reference only when the
    reference lies lower along it.
    The axis p is _apart_axis's, which an SI end's clear_between shares, so the two never disagree.
    An end with a `ref_layer`, an SI end over a plane (Stage 4 design 5.5), takes the vertical port (`vertical`, with
    its own refusals).
    Every coordinate is a line of `mesh` and every value JSON-native: lists of Python floats. Raises E_PORT_SPANS, and
    E_PORT_BOX when no line across qualifies, copper fills every line between the facing lines, or a cap touches no
    piece of metal or another than its witness's."""
    if end.ref_layer is not None:
        return vertical(end, mesh, zs)
    slab = next(c for c in zs if c.copper == end.layer)
    if end.role == CURVE_PORT:
        z = float(slab.z1)  # ponytail: the top face for any layer; P0-B tests F.Cu only
        start, stop = ([float(mesh.x[np.abs(mesh.x - x).argmin()]), float(mesh.y[np.abs(mesh.y - y).argmin()]), z]
                       for x, y in end.centers)
        return {"name": end.name, "kind": "curve", "dir": None, "start": start, "stop": stop, "nodes": [start, stop],
                "part": True}
    # ponytail: one walk along p and one cut across; a box they leave with a cap off its own copper (a side finger on an
    # outer line's node, a cap whose copper lay only on a cut line, a gap with no mesh line) is refused, not walked
    # again; model_spec's 0R hulls come later and are not counted
    s, r = end.signal.bounds, end.reference.bounds
    p = _apart_axis(s, r)  # along the box; t = 1 - p across it
    if p is None:
        raise KrsError("E_PORT_SPANS", name=end.name)
    t = 1 - p
    along, across = (mesh.x, mesh.y)[p], (mesh.x, mesh.y)[t]

    def inside(lines: np.ndarray, a: float, b: float) -> np.ndarray:
        return lines[(lines > a) & (lines < b)]

    def at(u: float, v: float, z: float) -> list[float]:
        """The point `u` along p, `v` across it and at `z`, as [x, y, z]."""
        xy = (u, v) if p == 0 else (v, u)
        return [float(xy[0]), float(xy[1]), float(z)]

    def kept(lines: np.ndarray, copper: BaseGeometry, v: float) -> np.ndarray:
        """The `lines` along p whose point at `v` across lies inside `copper`."""
        return lines[[copper.contains(Point(at(u, v, 0)[:2])) for u in lines]]

    s_in, r_in = inside(along, s[p], s[p + 2]), inside(along, r[p], r[p + 2])
    width = inside(across, max(s[t], r[t]), min(s[t + 2], r[t + 2]))
    if not (s_in.size and r_in.size and width.size):
        raise KrsError("E_PORT_BOX", name=end.name)
    sig_cu, ref_cu = end.signal.buffer(-SIMPLIFY), end.reference.buffer(-SIMPLIFY)  # the solids are simplified
    metal = shapely.union_all([pc.polygon for pc in pieces if pc.layer == end.layer])

    def witness_line(width: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        """tc and the lines each pad keeps there; E_PORT_BOX when no line of `width` qualifies."""
        for tc in sorted(width, key=lambda v: abs(v - (width.min() + width.max()) / 2)):  # stable: a tie, the lower
            s_at, r_at = kept(s_in, sig_cu, tc), kept(r_in, ref_cu, tc)
            if s_at.size and r_at.size:
                return tc, s_at, r_at
        raise KrsError("E_PORT_BOX", name=end.name)

    def busy(u: float, vs, cu: BaseGeometry = metal) -> bool:
        """Whether the point at `u` along p and any of `vs` across lies in `cu`, its edge included."""
        return any(cu.covers(Point(at(u, v, 0)[:2])) for v in vs)

    tc, s_at, r_at = witness_line(width)
    forward = s[p + 2] <= r[p]  # the reference lies past the signal along p
    ref, sig = (r_at.min(), s_at.max()) if forward else (r_at.max(), s_at.min())  # the pads' facing lines
    run = along[(along >= min(ref, sig)) & (along <= max(ref, sig))]
    run = run[::-1] if forward else run  # from the reference's facing line to the signal's
    if run.size > 2:
        free = np.array([not busy(u, np.r_[width, (width[1:] + width[:-1]) / 2]) for u in run])
        free[0] = free[-1] = False  # the facing lines lie in their pads
        if not free.any():
            raise KrsError("E_PORT_BOX", name=end.name)
        i = int(free.argmax())  # the first free line
        j = i + int((~free[i:]).argmax())  # the first line in copper after it
        ref, sig, inner = run[i - 1], run[j], run[i:j]
        below, above = across[across < width.min()], across[across > width.max()]
        cut = [below.size and any(busy(u, [(width.min() + below.max()) / 2]) for u in inner),
               above.size and any(busy(u, [(width.max() + above.min()) / 2]) for u in inner)]
        width = width[int(cut[0]):width.size - int(cut[1])]
        if tc not in width:
            tc, s_at, r_at = witness_line(width)
    sig_far, ref_far = (s_at.min(), r_at.max()) if forward else (s_at.max(), r_at.min())
    parts = getattr(metal, "geoms", [metal])  # the layer's copper, one polygon per connected piece
    span = np.r_[width, (width[1:] + width[:-1]) / 2]  # a cap's nodes and its edges across, inside the box
    for cap, far in ((ref, ref_far), (sig, sig_far)):  # each cap touches its witness's piece of copper, and no other
        if [busy(cap, span, g) for g in parts] != [g.covers(Point(at(far, tc, 0)[:2])) for g in parts]:
            raise KrsError("E_PORT_BOX", name=end.name)
    return {"name": end.name, "kind": "lumped", "dir": "xy"[p],
            "start": at(ref, width.min(), slab.z0), "stop": at(sig, width.max(), slab.z1),
            "nodes": [at(ref, tc, slab.z1), at(sig, tc, slab.z1), at(ref_far, tc, slab.z1), at(sig_far, tc, slab.z1)],
            "part": end.role != "external"}
