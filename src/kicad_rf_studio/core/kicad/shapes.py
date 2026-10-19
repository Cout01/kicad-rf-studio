# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry read from KiCad's S-expressions, in mm with y up: points, arcs, circles, graphics and pad outlines."""
import math

from shapely import unary_union
from shapely.affinity import affine_transform
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.kicad.sexpr import atom, child, num

XY = tuple[float, float]
GRAPHICS = ("gr_poly", "gr_rect", "gr_circle", "gr_line", "gr_arc")  # also the kinds of a custom pad's primitives
_CORNERS = {"top_left": (-1, 1), "top_right": (1, 1), "bottom_right": (1, -1), "bottom_left": (-1, -1)}  # y up


def _chord_angle(r: float, max_err: float) -> float:
    """The widest angle a chord of a circle of radius r may span while its middle stays within
    max_err of the circle. A circle smaller than that is one chord (the clamp)."""
    return 2 * math.acos(max(-1.0, 1 - max_err / r))


def arc_points(start: XY, mid: XY, end: XY, max_err: float = 0.001) -> list[XY]:
    """The circular arc through three points, as a polyline from `start` to `end` that passes `mid`
    and keeps every chord within `max_err` of the arc. Collinear points give [start, end]."""
    # the sums below are taken around `start`, so far from the origin they lose no precision
    bx, by = mid[0] - start[0], mid[1] - start[1]
    cx, cy = end[0] - start[0], end[1] - start[1]
    d = 2 * (bx * cy - by * cx)  # positive when start, mid, end turn counter-clockwise
    if d == 0:
        return [start, end]
    b2, c2 = bx * bx + by * by, cx * cx + cy * cy
    ux, uy = (cy * b2 - by * c2) / d, (bx * c2 - cx * b2) / d  # the centre, relative to start
    r = math.hypot(ux, uy)
    a0, a1 = math.atan2(-uy, -ux), math.atan2(cy - uy, cx - ux)
    sweep = (a1 - a0) % math.tau if d > 0 else -((a0 - a1) % math.tau)
    step = _chord_angle(r, max_err)
    n = max(1, math.ceil(abs(sweep) / step)) if step else 1  # step is 0 for a near-straight arc
    x0, y0 = start[0] + ux, start[1] + uy
    angles = (a0 + sweep * k / n for k in range(1, n))
    return [start, *((x0 + r * math.cos(a), y0 + r * math.sin(a)) for a in angles), end]


def circle(center: XY, radius: float, max_err: float = 0.001) -> Polygon:
    """A polygon inscribed in the circle, with the middle of every edge within `max_err` of it.
    No radius gives an empty polygon."""
    if radius <= 0:
        return Polygon()
    n = max(3, math.ceil(math.tau / _chord_angle(radius, max_err)))
    return Polygon([(center[0] + radius * math.cos(math.tau * k / n), center[1] + radius * math.sin(math.tau * k / n))
                    for k in range(n)])


def pt(x, y) -> XY:
    """A KiCad point as ours: the y axis points down in KiCad. `0.0 - y` keeps a zero from becoming -0.0."""
    return float(x), 0.0 - float(y)


def xy(node: list, head: str) -> XY:
    c = child(node, head)
    return pt(c[1], c[2])


def points(pts: list) -> list[XY]:
    """The vertices of a `(pts ...)` list. KiCad writes an arc of a polygon as `(arc (start) (mid) (end))`,
    which stands in for all the vertices on it."""
    out: list[XY] = []
    for p in pts[1:]:
        if p[0] == "xy":
            out.append(pt(p[1], p[2]))
        elif p[0] == "arc":
            out += arc_points(xy(p, "start"), xy(p, "mid"), xy(p, "end"))
    return out


def valid_polygons(geom: BaseGeometry) -> list[Polygon]:
    """The non-empty polygons of `geom`. An invalid one is rebuilt with buffer(0): KiCad writes a fill with
    a hole as one outline that runs into the hole and back along a zero-width slit, which buffer(0) turns
    into an outline with a hole. (A polygon that truly crosses itself, a bow-tie, keeps one lobe.)"""
    if not geom.is_valid:
        geom = geom.buffer(0)
    return [g for g in getattr(geom, "geoms", [geom]) if not g.is_empty]


def graphic_shape(node: list) -> LineString | Polygon:
    """The centre line of a line or arc, or the outline of a rectangle, circle or polygon, in the node's own
    coordinates. The node is a board graphic (gr_*), a footprint graphic (fp_*) or a custom pad's primitive."""
    kind = node[0][3:]  # "line" for both gr_line and fp_line
    if kind == "line":
        return LineString([xy(node, "start"), xy(node, "end")])
    if kind == "arc":
        return LineString(arc_points(xy(node, "start"), xy(node, "mid"), xy(node, "end")))
    if kind == "rect":
        (x0, y0), (x1, y1) = xy(node, "start"), xy(node, "end")
        return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    if kind == "circle":
        c = xy(node, "center")
        return circle(c, math.dist(c, xy(node, "end")))
    return Polygon(points(child(node, "pts")))  # poly


def stroke_path(shape: LineString | Polygon) -> LineString:
    """The line a graphic's stroke follows."""
    return shape.exterior if isinstance(shape, Polygon) else shape


def covered(node: list, shape: LineString | Polygon, filled: bool) -> list[Polygon]:
    """What a graphic covers: its stroke, `width` wide with round ends, and its inside when it is filled.
    KiCad draws the stroke of a filled shape as well, so a filled shape grows by half its width. A graphic
    writes its width as `(stroke (width w))`, a pad primitive as `(width w)`."""
    width = num(child(node, "stroke") or node, "width", 1, 0.0)
    if isinstance(shape, Polygon) and filled:
        return valid_polygons(shape.buffer(width / 2) if width else shape)
    return valid_polygons(stroke_path(shape).buffer(width / 2))


def turn(p: XY, deg: float, at: XY = (0.0, 0.0)) -> XY:
    """`p` turned `deg` degrees counter-clockwise about the origin, then moved by `at`."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return at[0] + p[0] * c - p[1] * s, at[1] + p[0] * s + p[1] * c


def place(geom: BaseGeometry, at: XY, deg: float) -> BaseGeometry:
    """`geom` turned and moved as `turn` does a point: how a footprint's or a pad's own frame lands on the board."""
    c, s = turn((1.0, 0.0), deg)
    return affine_transform(geom, [c, -s, s, c, at[0], at[1]])


def _rect(w: float, h: float, r: float, c: float = 0.0, cut=(), max_err: float = 0.001) -> Polygon:
    """A w x h rectangle about (0, 0) whose corners are rounded to radius r, except the corners named in `cut`,
    which lose a triangle c along each side and keep no rounding, as in pcbnew. The outline is convex, so it
    is the convex hull of the corners' parts. r = min(w, h)/2 is an oval, and a circle when w = h."""
    pts: list[XY] = []
    for name, (sx, sy) in _CORNERS.items():
        x, y = sx * w / 2, sy * h / 2
        if name in cut:
            pts += [(x - sx * c, y), (x, y - sy * c)]
        elif r > 0:  # a quarter circle; a buffered point has vertices on the axes, where the sides touch it
            quad_segs = math.ceil(math.pi / 2 / _chord_angle(r, max_err))
            pts += Point(x - sx * r, y - sy * r).buffer(r, quad_segs=quad_segs).exterior.coords
        else:
            pts.append((x, y))
    return MultiPoint(pts).convex_hull


def _outline(pad: list) -> BaseGeometry:
    """A pad's copper outline in its own frame: (0, 0) at its centre, y up, before its angle is applied.
    KiCad's y points down here too, so every corner and primitive is flipped like a board point."""
    shape, w, h = str(pad[3]), num(pad, "size", 1, 0.0), num(pad, "size", 2, 0.0)
    if shape == "circle":
        return _rect(w, w, w / 2)
    if shape == "oval":
        return _rect(w, h, min(w, h) / 2)
    if shape == "trapezoid":
        dx, dy = num(pad, "rect_delta", 1, 0.0) / 2, num(pad, "rect_delta", 2, 0.0) / 2
        return Polygon([pt(-w / 2 - dy, h / 2 + dx), pt(w / 2 + dy, h / 2 - dx),
                        pt(w / 2 - dy, -h / 2 + dx), pt(-w / 2 + dy, -h / 2 - dx)])
    if shape == "custom":
        anchor = _rect(w, h, 0) if atom(child(pad, "options") or [], "anchor") == "rect" else _rect(w, w, w / 2)
        parts = [anchor]
        for p in (child(pad, "primitives") or [])[1:]:
            if p[0] in GRAPHICS:  # a Bezier (gr_curve) is not read; gr_vector and gr_bbox are markers, not copper
                filled = p[0] == "gr_poly" or atom(p, "fill") == "yes"  # a polygon primitive is always filled
                parts += covered(p, graphic_shape(p), filled)
        return unary_union(parts)
    # rect and roundrect, either with chamfered corners; the ratios default as in KiCad
    r = num(pad, "roundrect_rratio", 1, 0.25) * min(w, h) if shape == "roundrect" else 0.0
    cut = (child(pad, "chamfer") or [])[1:]
    return _rect(w, h, r, num(pad, "chamfer_ratio", 1, 0.2) * min(w, h), cut)


def pad_shape(pad: list, fp_at: XY, fp_angle: float) -> tuple[XY, Polygon, list[tuple[str, dict]]]:
    """Where pcbnew puts a pad's copper, its ShapePos, and the copper's outline there, in board mm with y up,
    plus the warnings the pad raises. `fp_at` and `fp_angle` place its footprint.

    The file gives the pad's position in its footprint's frame, and its angle with the footprint's angle
    already included. ShapePos is that position on the board plus the drill offset turned by the pad's angle.
    A bottom-side footprint is stored mirrored already, so it needs nothing more. A per-layer padstack is
    read as its main (front) shape. A custom pad whose primitives do not touch is a MultiPolygon. The warnings
    name the pad by its number alone, as the footprint's reference is not known here."""
    angle = num(pad, "at", 3, 0.0)
    center = turn(xy(pad, "at"), fp_angle, fp_at)
    drill = child(pad, "drill") or []
    if child(drill, "offset"):
        center = turn(xy(drill, "offset"), angle, center)
    mode = atom(child(pad, "padstack") or [], "mode")
    warnings = [] if mode in (None, "normal") else [("W_PADSTACK", {"pad": str(pad[1])})]
    return center, place(_outline(pad), center, angle), warnings
