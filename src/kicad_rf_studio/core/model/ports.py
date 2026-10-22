# SPDX-License-Identifier: GPL-3.0-or-later
"""The ports of the model (spec 5.6, 5.7): the two ends of each port on the board, and its box on the mesh lines."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from shapely.geometry import Point, box

from kicad_rf_studio.core.geometry.copper import SIMPLIFY
from kicad_rf_studio.core.kicad.tracer import signal_layer, unknown_pad
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import CURVE_PORT, GRID, PORT

if TYPE_CHECKING:
    from shapely.geometry import Polygon
    from shapely.geometry.base import BaseGeometry

    from kicad_rf_studio.core.geometry.copper import Piece
    from kicad_rf_studio.core.geometry.zstack import Slab
    from kicad_rf_studio.core.kicad.board import Board, Pad
    from kicad_rf_studio.core.kicad.shapes import XY
    from kicad_rf_studio.core.mesh import Mesh


@dataclass(frozen=True)
class End:
    """A port's two ends in the board's frame (y up): the copper of its signal and of its reference, on the copper
    layer `layer`. `name` is the port's name, or the part's ref; `role` is "external" for a port of project.json's
    `ports`, else the part's role (port, curve_port or grid). `centers`, a part's only, are the centres of its
    reference and signal pads, where its CurvePort ends."""
    name: str
    signal: BaseGeometry
    reference: BaseGeometry
    layer: str
    role: str
    centers: tuple[XY, XY] | None = None


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
    port, curve_port or grid, series, shunt and others in order. A port's pads are found by uuid, else by name
    (`_pad`); a part's signal is its first pad and its reference its second, on the signal pad's layer
    (`signal_layer`). Raises KrsError: E_NO_PORTS, E_NO_REFERENCE, E_UNKNOWN_PAD, E_REFERENCE_LAYER,
    E_REFERENCE_POINT, and E_ROTATED_PART for a curve_port while allow_curve_port is false (C-12, C-37)."""
    if not project["ports"]:
        raise KrsError("E_NO_PORTS")
    out = []
    for port in project["ports"]:
        if port["reference"] is None:
            raise KrsError("E_NO_REFERENCE", signal=port["signal"])
        name, layer = port["name"], port["layer"]
        sig = _pad(board, port["signal"], port["signal_uuid"], layer)
        out.append(End(name, sig.polygon, _reference(board, pieces, name, sig, layer, port["reference"]), layer,
                       "external"))
    for part in (*project["chain"]["series"], *project["chain"]["shunt"], *project["others"]):
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


def place(end: End, mesh: Mesh, zs: tuple[Slab, ...]) -> dict:
    """The port of `end` on the lines of `mesh` (spec 5.6): a CurvePort for a curve_port, else a lumped port.
    The lumped port's box runs along the in-plane axis on which the signal and the reference are apart while their
    spans across it overlap: from the reference's line nearest the signal to the signal's line nearest the reference,
    across over the lines inside that overlap, and in z over the copper slab of `end.layer`. It starts at the reference
    end, so that openEMS's u is V_signal − V_reference. Its `nodes` are the reference cap, the signal cap, then the
    reference and signal witnesses (the line of each pad farthest from the other), on the line across nearest the
    box's middle, at the copper's top face.
    The CurvePort (C-37) runs from the reference pad's centre to the signal pad's, each on the nearest x and y lines, at
    the copper's top face; its `nodes` are those two ends. openEMS puts its one-edge port at their middle, joined to
    both by PEC curves, and orders them along its axis itself: its u is V_signal − V_reference only when the
    reference lies lower along it.
    Every coordinate is a line of `mesh` and every value JSON-native: lists of Python floats. Raises E_PORT_SPANS and
    E_PORT_BOX."""
    slab = next(c for c in zs if c.copper == end.layer)
    if end.role == CURVE_PORT:
        z = float(slab.z1)  # ponytail: the top face for any layer; P0-B tests F.Cu only
        start, stop = ([float(mesh.x[np.abs(mesh.x - x).argmin()]), float(mesh.y[np.abs(mesh.y - y).argmin()]), z]
                       for x, y in end.centers)
        return {"name": end.name, "kind": "curve", "dir": None, "start": start, "stop": stop, "nodes": [start, stop],
                "part": True}
    # ponytail: pads are taken as their bounding boxes; a round pad's corner can leave a cap edge in air, which the PEC
    # check tolerates
    s, r = end.signal.bounds, end.reference.bounds
    apart = [s[k + 2] <= r[k] or r[k + 2] <= s[k] for k in (0, 1)]  # their spans along k do not overlap
    if apart[0] == apart[1]:
        raise KrsError("E_PORT_SPANS", name=end.name)
    p = apart.index(True)  # along the box; t = 1 - p across it
    t = 1 - p
    along, across = (mesh.x, mesh.y)[p], (mesh.x, mesh.y)[t]

    def inside(lines: np.ndarray, a: float, b: float) -> np.ndarray:
        return lines[(lines > a) & (lines < b)]

    s_in, r_in = inside(along, s[p], s[p + 2]), inside(along, r[p], r[p + 2])
    width = inside(across, max(s[t], r[t]), min(s[t + 2], r[t + 2]))
    if not (s_in.size and r_in.size and width.size):
        raise KrsError("E_PORT_BOX", name=end.name)
    forward = s[p + 2] <= r[p]  # the reference lies past the signal along p
    sig, sig_far = (s_in.max(), s_in.min()) if forward else (s_in.min(), s_in.max())
    ref, ref_far = (r_in.min(), r_in.max()) if forward else (r_in.max(), r_in.min())
    lo, hi = width.min(), width.max()
    tc = width[np.argmin(np.abs(width - (lo + hi) / 2))]

    def at(u: float, v: float, z: float) -> list[float]:
        """The point `u` along p, `v` across it and at `z`, as [x, y, z]."""
        xy = (u, v) if p == 0 else (v, u)
        return [float(xy[0]), float(xy[1]), float(z)]

    return {"name": end.name, "kind": "lumped", "dir": "xy"[p],
            "start": at(ref, lo, slab.z0), "stop": at(sig, hi, slab.z1),
            "nodes": [at(ref, tc, slab.z1), at(sig, tc, slab.z1), at(ref_far, tc, slab.z1), at(sig_far, tc, slab.z1)],
            "part": end.role != "external"}
