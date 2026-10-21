# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import sys
import time
from pathlib import Path

import pytest

from kicad_rf_studio import runs
from kicad_rf_studio.core.kicad import load_board

FAKE = Path(__file__).parent / "fake_worker.py"
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


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """Workers are tests/fake_worker.py (KRS_FAKE* pick its behaviour), the data folder is under tmp_path, polls are
    fast and the version check passes. Returns the data folder."""
    monkeypatch.setattr(runs, "WORKER", ("-I", "-u", str(FAKE)))
    monkeypatch.setattr(runs, "POLL_S", 0.02)
    monkeypatch.setattr(runs, "ABORT_WAIT_S", 5.0)
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(runs, "check_openems", lambda: [])
    return tmp_path / "data"


@pytest.fixture
def calibrated(fake):
    """A stored calibration of this machine: 2 jobs of 2 threads, 400 MC/s in all. Returns the data folder."""
    runs.save_settings({"machines": {runs.machine_key(): {
        "threads": 2, "pool": 2, "aggregate_mcs": 400.0, "single": {"2": 200.0}, "parallel": {"2": 400.0},
        "at": "2026-10-21T00:00:00"}}})
    return fake


@pytest.fixture
def ctrl_c_on_third_poll(monkeypatch):
    """subprocess.Popen records each process it starts, and the third time.sleep raises KeyboardInterrupt. Returns
    the list of started processes."""
    started, real_popen, real_sleep, calls = [], subprocess.Popen, time.sleep, []

    def popen(*a, **kw):
        started.append(real_popen(*a, **kw))
        return started[-1]

    def sleep(s):
        calls.append(s)
        if len(calls) == 3:
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(time, "sleep", sleep)
    return started


def pytest_collection_modifyitems(config, items):
    """@pytest.mark.openems tests run only where the worker's own interpreter imports openEMS (CI tier b)."""
    marked = [item for item in items if "openems" in item.keywords]
    if marked and subprocess.run([sys.executable, "-I", "-c", "import openEMS"], capture_output=True).returncode:
        for item in marked:
            item.add_marker(pytest.mark.skip(reason="openEMS does not import in this Python"))
