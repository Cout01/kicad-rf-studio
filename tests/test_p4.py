# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import subprocess
import sys

import pytest
from scipy.constants import c as C0

import p0
import p4
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.post.si import Reading, read
from kicad_rf_studio.core.project import load_project
from test_p0 import in_process
from test_p4_fixtures import LINES
from test_post_si import F, SE, line_s


@pytest.fixture
def gates(p0_out, monkeypatch):
    """p0_out entered as <GATES>: the CLI in this process on the network fake, no other process seen, and the gates'
    own checkpoint constants kept out."""
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    for key, value in (("N", 2), ("RULE", "l40"), ("DIELECTRIC", "lossless"), ("EDITS", {}), ("BENDS_N3", "pending")):
        monkeypatch.setattr(p4, key, value)
    return p4.enter(p0_out)


def test_a_run_step_runs_the_product_once_and_measures_it(gates, monkeypatch):  # G-1; design 5.11
    name, pj = p4.project(gates, "p4b_ms90")
    assert name == "p4b_ms90-n2-l40" and load_project(pj)["mesh"]["n"] == 2
    record = p4.run_step(gates, name)
    assert record["step"] == "p4-p4b_ms90-n2-l40-run" and record["result"]["exit"] == 0
    monkeypatch.setattr(p0, "cli_run", lambda *a: pytest.fail("a recorded step ran again"))
    assert p4.run_step(gates, name) == record
    m = p4.measure(gates, name)
    monkeypatch.setattr(runs, "SI_SPEED", 0.9)  # a refit after the run (0c94475's): the run's own figures still hold
    monkeypatch.setattr(runs, "DEBYE_WEIGHT", 50.0)
    assert p4.measure(gates, name)["worst_s"] == m["worst_s"]  # ruling G-2: the I_COST_TIME the run printed
    assert (m["pool"], m["cal_mcs"], m["speeds_mcs"], m["debye_cells"]) == (2, 200.0, [100.0] * 4, 0)
    assert isinstance(m["reading"], Reading) and m["reading_error"] is None and m["valid"] is True
    events = [json.loads(x) for x in (p0.run_path(m["run_dir"]) / "events.jsonl").read_text("utf-8").splitlines()]
    cost = {e["code"]: e["params"] for e in events if e["kind"] == "cost"}
    assert cost["I_COST_TIME"]["time"] == pipeline.duration(m["worst_s"])  # cost's SI formula, SI_SPEED applied
    assert not {"reading", "project"} & set(p4.plain(m)) and json.dumps(p4.plain(m))


def test_the_settings_follow_the_checkpoint_constants(gates, monkeypatch):  # G-1: decisions in tools constants
    base = load_project(p4.base(gates, "p4b_ms90"))
    cell = base["mesh"]["max_cell_mm"]
    assert cell == LINES["p4b_ms90"][3]  # the gates' λ/40, recorded once, where new writes the d fill (Task 16)
    assert p4.settings(base) == {"mesh.n": 2, "mesh.max_cell_mm": cell, "dielectric": "lossless"}
    monkeypatch.setattr(p4, "N", 3)
    monkeypatch.setattr(p4, "RULE", "l80")
    assert p4.settings(base) == {"mesh.n": 3, "mesh.max_cell_mm": round(cell / 2, 6), "dielectric": "lossless"}
    assert p4.settings(base, rule="dfill", dielectric="debye")["mesh.max_cell_mm"] is None
    usb = load_project(p4.base(gates, "usb2_hs"))  # no LINES cell: P4-D's and P4-F's board, run at the d fill only
    assert p4.settings(usb, rule="dfill")["mesh.max_cell_mm"] is None
    for rule in ("l40", "l80"):  # never the d fill under a λ rule's name
        with pytest.raises(ValueError, match=f"rule {rule} needs a recorded λ/40 cell"):
            p4.settings(usb, rule=rule)
    assert p4.name("si_line100", dielectric="debye", tag="v") == "si_line100-n3-l80-debye-v"
    monkeypatch.setattr(p4, "EDITS", {"p4b_sl90": {"gates.fit2d_limit": 0.05}})
    assert load_project(p4.project(gates, "p4b_sl90")[1])["gates"]["fit2d_limit"] == 0.05


def test_an_interrupted_step_leaves_no_record_and_runs_again(gates, monkeypatch):  # G-3; Review Focus 1
    name, pj = p4.project(gates, "p4c_step35")
    real = p0.cli_run

    def reaped(*a):  # the shell reaped mid-run: cli_run raises, so p0.step stores nothing
        raise RuntimeError("reaped")

    monkeypatch.setattr(p0, "cli_run", reaped)
    with pytest.raises(RuntimeError):
        p4.run_step(gates, name)
    assert not (gates / "steps" / f"p4-{name}-run.json").exists() and p4.measure(gates, name) is None
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()  # the dead run's project lock, its pid gone: runs.project_lock reclaims it (W_STALE_LOCK)
    lock = pj.with_name("project.json.lock")
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    monkeypatch.setattr(p0, "cli_run", real)
    assert p4.run_step(gates, name)["result"]["exit"] == 0 and not lock.exists()


def test_a_gate_is_never_assembled_from_two_product_codes(gates):  # G-1: one code across all runs
    for sid, code in (("p4-a-n2-l40-run", "x"), ("p4-b-n2-l40-run", "y")):
        p0.save(gates / "steps" / f"{sid}.json", {"step": sid, "code": code})
    with pytest.raises(SystemExit):
        p4.records(gates, ["p4-a-n2-l40-run", "p4-b-n2-l40-run"])


def test_a_plateau_needs_a_window_of_one_rise_time():  # plan 3's Review Focus 2: no level, never a number
    r = read(line_s([(50.0, 3.2, 10.0), (75.0, 3.2, 36.0), (50.0, 3.2, 10.0)], F), F, SE, 3.2)
    t_r = r.rise[0]
    mid = p4.plateau(r, 2 * 10e-3 * math.sqrt(3.2) / C0 + t_r, 2 * 46e-3 * math.sqrt(3.2) / C0 - t_r)
    assert mid == pytest.approx(75.0, abs=0.05)  # 74.99 over 180 ps
    assert p4.plateau(r, 1e-9, 1e-9 + 0.99 * t_r) is None
    assert p4.plateau(r, 1.5e-9 - t_r / 2, 1.5e-9 + t_r / 2) is not None  # one rise time, to rounding


def test_the_rows_and_the_si_speed_refit(gates):  # K-1: the refit's rows from the gates' own runs
    for board in ("p4c_step35", "si_line100"):
        p4.run_step(gates, p4.project(gates, board)[0])
    rows = p4.rows(gates)
    assert [r["step"] for r in rows] == ["p4-p4c_step35-n2-l40-run", "p4-si_line100-n2-l40-run"]
    assert {(r["node_mcs"], r["cal_mcs"], r["debye_cells"]) for r in rows} == {(100.0, 200.0, 0)}
    assert p4.refit(rows) == {"si_speed": 0.5, "range": [0.5, 0.5], "by_pool": {2: 0.5}, "rows": 2}
