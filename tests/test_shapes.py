# SPDX-License-Identifier: GPL-3.0-or-later
import math

import pytest
from shapely.geometry import LineString, Point

from kicad_rf_studio.core.kicad.shapes import arc_points, circle

MAX_ERR = 0.001


def on_circle(center, degrees, r):
    a = math.radians(degrees)
    return (center[0] + r * math.cos(a), center[1] + r * math.sin(a))


def sagitta(pts, center):
    """How far the middle of the widest chord of the polyline lies inside the circle."""
    return max(math.dist(p, center) - math.dist(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), center)
               for p, q in zip(pts, pts[1:]))


def test_arc_points_run_from_start_to_end_along_the_arc():
    center, r = (100.0, -80.0), 5.0
    start, mid, end = (on_circle(center, a, r) for a in (10, 50, 100))
    pts = arc_points(start, mid, end)
    assert pts[0] == start and pts[-1] == end  # the ends are the given points, not recomputed ones
    assert all(math.dist(p, center) == pytest.approx(r, abs=1e-9) for p in pts)
    angles = [math.degrees(math.atan2(y - center[1], x - center[0])) for x, y in pts]
    assert angles == sorted(angles) and angles[0] == pytest.approx(10) and angles[-1] == pytest.approx(100)
    # the segment count is the least that keeps every chord within max_err of the arc
    assert len(pts) - 1 == math.ceil(math.radians(90) / (2 * math.acos(1 - MAX_ERR / r)))
    assert sagitta(pts, center) <= MAX_ERR


@pytest.mark.parametrize("mid_deg, end_deg, sweep_deg", [
    (90, 180, 180),    # counter-clockwise, half a circle
    (-90, 180, 180),   # clockwise through the bottom, half a circle
    (135, 270, 270),   # counter-clockwise, more than half
    (-135, 90, 270),   # clockwise, more than half
])
def test_arc_points_follow_the_side_the_mid_point_is_on(mid_deg, end_deg, sweep_deg):
    start, mid, end = (on_circle((0, 0), a, 1.0) for a in (0, mid_deg, end_deg))
    pts = arc_points(start, mid, end)
    assert LineString(pts).length == pytest.approx(math.radians(sweep_deg), rel=1e-3)
    assert LineString(pts).distance(Point(mid)) <= MAX_ERR


def test_collinear_points_are_a_straight_line():
    assert arc_points((0, 0), (1, 0), (2, 0)) == [(0, 0), (2, 0)]


def test_arc_smaller_than_max_err_does_not_break_the_segment_count():
    start, mid, end = (0.0, 0.0), (0.0002, 0.0002), (0.0004, 0.0)  # radius 0.2 um
    pts = arc_points(start, mid, end)
    assert pts[0] == start and pts[-1] == end


def test_circle_is_a_polygon_within_max_err_of_the_circle():
    center, r = (3.0, -2.0), 0.5
    poly = circle(center, r)
    pts = list(poly.exterior.coords)[:-1]
    assert poly.is_valid and len(pts) == math.ceil(math.pi / math.acos(1 - MAX_ERR / r))
    assert all(math.dist(p, center) == pytest.approx(r, abs=1e-12) for p in pts)
    assert sagitta(pts + pts[:1], center) <= MAX_ERR


def test_circle_without_radius_is_empty_and_a_dot_is_still_a_polygon():
    assert circle((0, 0), 0).is_empty
    dot = circle((0, 0), 0.0001)
    assert dot.is_valid and not dot.is_empty
