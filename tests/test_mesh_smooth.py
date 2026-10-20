# SPDX-License-Identifier: GPL-3.0-or-later
import sys

import numpy as np

from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines


def test_keeps_input_lines_and_limits():
    out = smooth_mesh_lines(np.array([0.0, 0.1, 10.0]), max_res=1.0, ratio=1.3)
    assert {0.0, 0.1, 10.0} <= set(np.round(out, 9))
    steps = np.diff(out)
    assert steps.max() <= 1.0 + 1e-9 and (steps[1:] / steps[:-1]).max() <= 1.3 + 1e-6
    assert (steps[:-1] / steps[1:]).max() <= 1.3 + 1e-6


def test_default_ratio_is_1_3():  # upstream's default is 1.5; spec 5.4 grades at 1.3 or less
    steps = np.diff(smooth_mesh_lines(np.array([0.0, 0.1, 10.0]), max_res=1.0))
    assert max((steps[1:] / steps[:-1]).max(), (steps[:-1] / steps[1:]).max()) <= 1.3 + 1e-6


def test_stop_side_taper_grades():  # a Task-10-shaped axis; upstream's stop-side step (start_res) graded it at 5.2
    d = 0.075
    lines = np.r_[-20.0, -6.0, -5.6, np.round(-1.2 + d * np.arange(33), 9), 20.0]  # walls, via pair, strip filled at d
    out = smooth_mesh_lines(lines, max_res=2.36, ratio=1.3)
    assert set(np.round(lines, 9)) <= set(np.round(out, 9))
    steps = np.diff(out)
    assert steps.max() <= 2.36 + 1e-9
    assert max((steps[1:] / steps[:-1]).max(), (steps[:-1] / steps[1:]).max()) <= 1.3 + 1e-6


def test_no_csxcad_import():
    assert "CSXCAD" not in sys.modules
