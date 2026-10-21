# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import sys

import pytest

from kicad_rf_studio.core.kicad import load_board

MINI = ('(kicad_pcb (version {version}) (generator "test") (general (thickness 0.8)) '
        '(layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user) (39 "F.Mask" user)) '
        '(setup {stackup} (pad_to_mask_clearance {clearance})) (net 0 "") {body})')


@pytest.fixture
def mini_board_file(tmp_path):
    def make(body="", version=20241229, clearance=0, stackup=""):
        p = tmp_path / "mini.kicad_pcb"
        p.write_text(MINI.format(version=version, clearance=clearance, stackup=stackup, body=body), encoding="utf-8")
        return p
    return make


@pytest.fixture
def mini_board(mini_board_file):
    return lambda body="", **kw: load_board(mini_board_file(body, **kw))


def pytest_collection_modifyitems(config, items):
    """@pytest.mark.openems tests run only where the worker's own interpreter imports openEMS (CI tier b)."""
    marked = [item for item in items if "openems" in item.keywords]
    if marked and subprocess.run([sys.executable, "-I", "-c", "import openEMS"], capture_output=True).returncode:
        for item in marked:
            item.add_marker(pytest.mark.skip(reason="openEMS does not import in this Python"))
