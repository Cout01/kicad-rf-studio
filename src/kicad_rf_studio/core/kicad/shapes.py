# SPDX-License-Identifier: GPL-3.0-or-later
"""Arcs and circles as polylines and polygons, in mm."""
import math

from shapely.geometry import Polygon

XY = tuple[float, float]


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
