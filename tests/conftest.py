# SPDX-License-Identifier: GPL-3.0-or-later
import os

# pt-BR design 4: before conftest's imports, which load core.messages (it binds its language at import), and inherited
# by every process a test starts; KRS_TEST_LANGUAGE=pt_BR runs tests/test_gui.py in pt-BR (design 7.3)
os.environ["LANGUAGE"] = os.environ.get("KRS_TEST_LANGUAGE") or "en"

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from fake_cli import patches
from kicad_rf_studio import runs
from kicad_rf_studio.core.kicad import load_board

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # before any QApplication: Qt tests open no window

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
    fast and the version check passes: fake_cli.patches, which a detached tests/fake_cli.py applies too. Returns the
    data folder."""
    for name, value in patches(tmp_path / "data").items():
        monkeypatch.setattr(runs, name, value)
    return tmp_path / "data"


@pytest.fixture
def calibrated(fake):
    """A stored calibration of this machine: 2 jobs of 2 threads, 400 MC/s in all. Returns the data folder."""
    runs.save_settings({"machines": {runs.machine_key(): {
        "threads": 2, "pool": 2, "aggregate_mcs": 400.0, "single": {"2": 200.0}, "parallel": {"2": 400.0},
        "at": "2026-10-21T00:00:00"}}})
    return fake


@pytest.fixture
def p0_out(tmp_path, monkeypatch, calibrated):
    """A P0 folder named with a space and an accent, with the fake worker and this machine's calibration in the
    data folder p0.enter makes inside it (D-7). Returns the folder; p0.enter stays the real one."""
    out = tmp_path / "p0 ação"
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")  # restored after the test; p0.enter sets both
    monkeypatch.setattr(runs, "data_dir", lambda: out / "data" / "kicad-rf-studio")
    runs.save_settings(json.loads((calibrated / "settings.json").read_text(encoding="utf-8")))
    return out


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


@pytest.fixture(autouse=True)
def no_kicad(tmp_path, monkeypatch):
    """No test reaches a real KiCad (Stage 2 design 3): KiCad's documents and settings folders are under tmp_path, and
    its API socket is one no KiCad listens on, since kipy's default would be the KiCad the owner has open. A test that
    needs other values sets them."""
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path / "documents"))
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("KICAD_API_SOCKET", f"ipc://{tmp_path / 'no-kicad.sock'}")
    monkeypatch.delenv("KICAD_API_TOKEN", raising=False)


@pytest.fixture
def kicad(tmp_path):
    """Fake KiCad API servers (tests/fake_kicad.py), each at its own ipc address under tmp_path, with lpf915 open
    unless another board is given; closed at teardown."""
    from fake_kicad import FakeKiCad  # here: kipy and pynng load only in the tests that use it
    made = []

    def make(board=Path(__file__).with_name("fixtures") / "lpf915.kicad_pcb", **kw):
        made.append(FakeKiCad(f"ipc://{tmp_path / f'api{len(made)}.sock'}", board, **kw))
        return made[-1]

    yield make
    for server in made:
        server.close()


@pytest.fixture(scope="session")
def qapp():
    """The session's one QApplication, on the offscreen platform set above."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def pytest_collection_modifyitems(config, items):
    """@pytest.mark.openems tests run only where the worker's own interpreter imports openEMS (CI tier b)."""
    marked = [item for item in items if "openems" in item.keywords]
    if marked and subprocess.run([sys.executable, "-I", "-c", "import openEMS"], capture_output=True).returncode:
        for item in marked:
            item.add_marker(pytest.mark.skip(reason="openEMS does not import in this Python"))
