# SPDX-License-Identifier: GPL-3.0-or-later
import os
import subprocess

import pytest

from kicad_rf_studio import runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render
from test_cli_cost import fail


def test_choose_takes_the_best_aggregate_and_fewer_jobs_on_a_tie():
    assert runs.choose({1: 50.0, 2: 100.0, 4: 200.0, 8: 400.0}, {2: 600.0, 4: 560.0}, 8) == (4, 2, 600.0)
    assert runs.choose({8: 400.0}, {2: 400.0, 4: 400.0}, 8) == (8, 1, 400.0)


@pytest.mark.parametrize(("cpus", "single", "parallel"), [
    (8, {"1": 50.0, "2": 100.0, "4": 200.0, "8": 400.0}, {"2": 400.0, "4": 400.0}),
    (2, {"1": 50.0, "2": 100.0}, {"2": 100.0})])  # never a parallel job at 0 threads
def test_calibrate_measures_and_stores_this_machine(fake, monkeypatch, capsys, cpus, single, parallel):  # C-35
    monkeypatch.setattr(os, "cpu_count", lambda: cpus)  # the fake reports 50 MC/s per thread
    entry = runs.calibrate({})
    assert (entry["threads"], entry["pool"], entry["aggregate_mcs"]) == (cpus, 1, 50.0 * cpus)
    assert (entry["single"], entry["parallel"]) == (single, parallel)
    assert runs.load_settings()["machines"][runs.machine_key()] == entry
    assert capsys.readouterr().out.splitlines() == [render("I_CALIBRATING"),
                                                    render("I_CALIBRATED", threads=cpus, pool=1, speed=f"{50 * cpus}")]


def test_a_stored_calibration_is_used_without_running(calibrated, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", fail)  # tests/test_cli_cost.py
    assert runs.ensure_calibrated(runs.load_settings())["threads"] == 2


def test_sizing_caps_the_pool_by_ram(monkeypatch):  # C-25
    monkeypatch.setattr(os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 1000.0)
    assert runs.sizing({"threads": 2, "pool": 4}, 2_000_000) == (2, 2)


@pytest.mark.openems
def test_calibrate_with_openems(tmp_path, monkeypatch):  # tier b, about 20–30 s
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    entry = runs.calibrate(runs.load_settings())
    assert entry["aggregate_mcs"] > 0 and 1 <= entry["threads"] <= os.cpu_count() and entry["pool"] >= 1


# --- beyond the brief's tests ------------------------------------------------------------------


def test_the_command_checks_openems_first_and_keeps_the_other_settings(fake, monkeypatch, capsys):  # C-31
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    monkeypatch.setattr(runs, "check_openems", lambda: [("W_OPENEMS_UNTESTED", {"openems": "0.38.0", "command": "c"})])
    runs.save_settings({"openems_dir": "x"})
    assert main(["calibrate"]) == 0
    assert capsys.readouterr().out.splitlines()[:2] == [render("W_OPENEMS_UNTESTED", openems="0.38.0", command="c"),
                                                        render("I_CALIBRATING")]
    assert runs.load_settings()["openems_dir"] == "x" and runs.machine_key() in runs.load_settings()["machines"]
