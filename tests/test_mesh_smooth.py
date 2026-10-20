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


def test_no_csxcad_import():
    assert "CSXCAD" not in sys.modules
