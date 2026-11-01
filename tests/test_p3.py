# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
import sys

import numpy as np
import pytest

import p0
import p3
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.model.spec import cell_split
from kicad_rf_studio.core.project import load_project
from test_p0 import in_process

F = np.linspace(2.3e9, 2.5e9, 201)


@pytest.fixture
def gates(p0_out, monkeypatch):
    """p0_out entered as <GATES>, the CLI in this process (the fake worker), no other process seen."""
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    return p3.enter(p0_out)


def test_a_run_step_runs_the_product_once_and_measures_it(gates, monkeypatch):  # design 5.11; r4 1
    pj = p3.variant(gates, "ifa2g4-solid-n2", "ifa2g4", {})
    assert pj == gates / "projects" / "ifa2g4-solid-n2" / "project.json" and load_project(pj)["band"]["f_lo_hz"] == 2.4e9
    record = p3.run_step(gates, "ifa2g4-solid-n2")
    assert record["step"] == "p3-ifa2g4-solid-n2-run" and record["result"]["exit"] == 0
    monkeypatch.setattr(p0, "cli_run", lambda *a: pytest.fail("a recorded step ran again"))
    assert p3.run_step(gates, "ifa2g4-solid-n2") == record
    m = p3.measure(gates, "ifa2g4-solid-n2")
    spec = json.loads((p0.run_path(m["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert m["split"] == list(cell_split(spec)) and m["pool"] == 1 and m["speeds_mcs"] == [100.0]  # the fake's
    assert m["jobs"][0]["verdict"] == "converged" and m["cal_mcs"] == 200.0  # calibrated: single {"2": 200.0}
    assert m["f_res_hz"] == pytest.approx(2506.4e6, abs=0.1e6) and m["depth_db"] == pytest.approx(-33.0, abs=0.1)
    assert m["conditioned"] is True and len(m["eta_rad"]) == len(m["far_f_hz"]) == 2  # the fake's sphere fixture
    assert m["band"] == [2.4e9, 2.4835e9]
    project, board, geom, _ = pipeline.load(pj)  # the product's own lines, from the same run
    setup = json.loads((p0.run_path(m["run_dir"]) / "job-0-setup" / "setup.json").read_text(encoding="utf-8"))
    notes = dict(pipeline.cost_notes(pipeline.build_model(project, board, geom), project, setup, 2, 1, 200.0))
    assert notes["I_COST_PREDICTED"]["time"] == pipeline.duration(m["predicted_s"])
    assert notes["I_COST_TIME"]["time"] == pipeline.duration(m["worst_s"])


def test_an_interrupted_step_leaves_no_record_and_runs_again(gates, monkeypatch):  # RF 1
    pj = p3.variant(gates, "ifa2g4-solid-n2", "ifa2g4", {})
    real = p0.cli_run

    def killed(*a):  # a reboot or taskkill mid-run: cli_run raises, so p0.step stores nothing
        raise RuntimeError("killed")

    monkeypatch.setattr(p0, "cli_run", killed)
    with pytest.raises(RuntimeError):
        p3.run_step(gates, "ifa2g4-solid-n2")
    assert not (gates / "steps" / "p3-ifa2g4-solid-n2-run.json").exists() and p3.measure(gates, "ifa2g4-solid-n2") is None
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()  # the killed run's project lock, its pid gone: runs.project_lock reclaims it (W_STALE_LOCK)
    lock = pj.with_name("project.json.lock")
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    monkeypatch.setattr(p0, "cli_run", real)
    assert p3.run_step(gates, "ifa2g4-solid-n2")["result"]["exit"] == 0 and not lock.exists()


def test_a_variant_keeps_its_own_results_and_an_edit_reruns_it(gates):  # design 5.11; r4 1
    p3.variant(gates, "n", "ifa2g4", {})
    p3.variant(gates, "s", "ifa2g4", {"preset": "strict"})
    normal, strict = p3.run_step(gates, "n"), p3.run_step(gates, "s")
    assert normal["key"].split("|")[0] == strict["key"].split("|")[0] and normal["key"] != strict["key"]
    assert load_project(p3.project_path(gates, "s"))["mesh"]["n"] == 2  # the preset alone: new --preset's n 3 trap
    p3.variant(gates, "n", "ifa2g4", {"t_max_s": 31e-9})  # T_max is in the model
    assert p3.measure(gates, "n")["f_res_hz"] is None  # stale results measure as none (antenna_result)
    assert p3.run_step(gates, "n")["key"] != normal["key"]  # and the step runs again
    assert p3.measure(gates, "n")["f_res_hz"] is not None


def test_a_free_step_runs_to_its_free_length(gates):  # design 5.11 P3-C; ruling 4
    p3.variant(gates, "ifa2g4-solid-n2", "ifa2g4", {})
    record = p3.free_step(gates, "ifa2g4-solid-n2", 33e-9)
    result = record["result"]
    assert record["step"] == "p3-ifa2g4-solid-n2-free" and result["t_max"] == 33e-9 and result["finite"]
    assert result["growth_db"] == 0.0 and result["run_dir"].startswith("p3-ifa2g4-solid-n2-free-")
    assert p3.measure(gates, "ifa2g4-solid-n2", "free")["t_max"] == 33e-9


def test_the_gates_folder_is_never_the_data_folder_nor_p0s(tmp_path, monkeypatch):  # ruling 7
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data" / "kicad-rf-studio")
    for out in (tmp_path / "data" / "kicad-rf-studio" / "gates", tmp_path / "kicad-rf-studio-p0-x"):
        with pytest.raises(SystemExit):
            p3.enter(out)
        assert not out.exists()


def test_a_gate_is_never_assembled_from_two_product_codes(gates):  # RF 2; p0.records
    for sid, code in (("p3-a-run", "x"), ("p3-b-run", "y")):
        p0.save(gates / "steps" / f"{sid}.json", {"step": sid, "code": code})
    assert [r["step"] for r in p3.records(gates, ["p3-a-run", "p3-c-run"])] == ["p3-a-run"]  # a step not run is left out
    with pytest.raises(SystemExit):
        p3.records(gates, ["p3-a-run", "p3-b-run"])


def test_a_blocked_run_is_recorded_and_measures_as_none(gates):  # p0.cli_run stores exits 2 to 4
    p3.variant(gates, "blocked", "ifa2g4", {"gates.fit2d_limit": 0.001})  # fit2d reads 0.99 % at n 2: exit 3
    assert p3.run_step(gates, "blocked")["result"]["exit"] == 3
    m = p3.measure(gates, "blocked")
    assert (m["jobs"], m["split"], m["predicted_s"], m["worst_s"], m["f_res_hz"]) == ([], None, None, None, None)


def meas(f_res, depth=-12.0, d=2.57, eta=0.81):  # a measure's shape: a dip of `depth` dB at f_res, a parabola in dB
    s11 = 10 ** ((depth + 8 * ((F - f_res) / 50e6) ** 2) / 20) + 0j
    return {"f_hz": F, "s11": s11, "band": [2.4e9, 2.4835e9], "d_dbi": d, "far_f_hz": [2.44175e9], "eta_rad": [eta]}


def test_a_pair_is_judged_by_its_resonance_and_explained_by_its_s11():  # ruling 1; RF 3
    p = p3.pair(meas(2.4e9), meas(2.43e9, d=2.77, eta=0.81 * 10 ** -0.01), 0.01, -6.0)
    assert p["f_res"] == pytest.approx([2.4e9, 2.43e9]) and p["f_rel"] == pytest.approx(0.0125)
    assert (p["conditioned"], p["pass"], p["explained"]) == (True, False, False)
    assert p["d_db"] == pytest.approx(0.2) and p["eta_db"] == pytest.approx(0.1) and p["ds11_shift"] > 0
    edge = p3.pair(meas(2.4e9), meas(2.52e9), 0.01, -6.0)  # its lowest |S11| at the grid's end: no dip
    assert edge["conditioned"] is False and edge["f_res"][1] == 2.5e9


def test_an_unconditioned_miss_is_explained_within_its_shift_equivalent():  # ruling 1, amended at commit
    x, turn = (F - 2.4e9) / 100e6, np.exp(-2j * np.pi * F * 1.7e-9)  # the first run's phase slope

    def broad(tilt_db):  # a broad -5.9 dB minimum at 2.4 GHz, tilted per 100 MHz
        return {**meas(2.4e9), "s11": 10 ** ((-5.9 + 0.5 * x ** 2 + tilt_db * x) / 20) * turn}

    near = p3.pair(broad(0.0), broad(-0.6), 0.01, -6.0)  # the argmins 60 MHz apart, the curves about 0.03 apart
    assert (near["conditioned"], near["pass"], near["explained"]) == (False, False, True)
    assert near["ds11"] < 0.05 < 0.1 < near["ds11_shift"] < 0.2  # a 1 % shift moves S11 by about 0.14 here
    far = p3.pair(broad(0.0), broad(-5.0), 0.01, -6.0)  # about 0.20 apart in band: more than a 1 % shift
    assert far["explained"] is False and far["ds11"] > far["ds11_shift"]


def detuned(x=0.0):  # S(f·(1 + x)) of a detuned board on F: its |S11| falling to the grid's top end, no dip, its
    g = F * (1 + x)  # phase turning with f
    return 10 ** ((-0.3 - 1.0 * (g - 2.3e9) / 0.2e9) / 20) * np.exp(-2j * np.pi * g * 0.4e-9)


def test_a_pair_with_no_resonance_in_its_grid_is_judged_by_its_fitted_shift():  # the controller's ruling at CP3
    a = {**meas(2.4e9), "s11": detuned()}
    b = {**a, "s11": detuned(-0.00865)}  # a's response shifted: S_b(f) = S_a(f·(1 − 0.865 %))
    p = p3.pair(a, b, 0.005, -6.0)
    assert p["f_res"] == [2.5e9, 2.5e9] and p["fit"]["clean"] is True
    assert p["fit"]["shift"] == pytest.approx(-0.00865, abs=2e-5)
    assert p["f_rel"] == pytest.approx(0.00865 / (1 - 0.00865), abs=3e-5) and p["pass"] is False
    assert p3.pair(a, b, 0.01, -6.0)["pass"] is True
    ripple = 0.003 * np.cos(2 * np.pi * F / 7e6) * ((F >= 2.4e9) & (F <= 2.4835e9))  # in band, and no shift
    vacuous = p3.pair(a, {**a, "s11": detuned() + ripple}, 0.005, -6.0)  # both minima still at the grid's last point
    assert (vacuous["fit"]["clean"], vacuous["f_rel"], vacuous["pass"]) == (False, 0.0, True)
    dips = p3.pair(meas(2.4e9), meas(2.43e9), 0.01, -6.0)  # both minima inside the grid: the argmins, as before
    assert dips["fit"] is None and dips["f_rel"] == abs(dips["f_res"][1] - dips["f_res"][0]) / dips["f_res"][0]
    assert dips["f_rel"] == pytest.approx(0.0125)
    assert (dips["conditioned"], dips["pass"], dips["explained"]) == (True, False, False)


def test_the_fit_finds_the_shift_on_either_side():  # the controller's ruling at CP3
    a = {**meas(2.4e9), "s11": detuned()}
    shift, residual = p3.fit_shift(a, {**a, "s11": detuned(0.004)})  # b's resonance a's / 1.004
    assert type(shift) is type(residual) is float
    assert shift == pytest.approx(0.004, abs=2e-5) and residual < 1e-4
    p = p3.pair(a, {**a, "s11": detuned(0.004)}, 0.005, -6.0)
    assert p["fit"]["clean"] is True and p["f_rel"] == pytest.approx(0.004 / 1.004, abs=3e-5) and p["pass"] is True


def test_the_refit_recovers_the_small_speed_by_level_and_judges_w_on_its_pair():  # design 5.9; ruling 6
    def row(pool, f, small, w=6.38, cal=580.0):
        return {"pool": pool, "f_pml": f, "cal_mcs": cal, "node_mcs": small * cal / (1 + (w - 1) * f)}
    rows = [row(1, f, 0.42) for f in (0.0, 0.31, 0.38, 0.44)] + [row(4, 0.434, 0.58, cal=205.6)]
    out = p3.refit(rows, 6.38, like=(rows[0], rows[3]))
    assert out["small"] == {1: pytest.approx(0.42), 4: pytest.approx(0.58)}
    assert (out["w_fit"], out["w_line"]) == (pytest.approx(6.38), pytest.approx(6.38)) and out["moved"] is False
    assert out["w"] == 6.38
    moved = [row(1, f, 0.42, w=9.0) for f in (0.0, 0.31, 0.44)]
    out = p3.refit(moved, 6.38, like=(moved[0], moved[2]))
    assert out["moved"] and out["w"] == pytest.approx(9.0) and out["small"][1] == pytest.approx(0.42)


def test_the_rows_are_each_recorded_run_and_verify_once(gates):  # free runs and hand runs left out
    p3.variant(gates, "a", "ifa2g4", {})
    p3.run_step(gates, "a")
    p3.free_step(gates, "a", 30e-9)
    (row,) = p3.rows(gates)
    m = p3.measure(gates, "a")
    assert row == {"step": "p3-a-run", "pool": 1, "cells": m["cells"], "f_pml": m["split"][2] / m["cells"],
                   "node_mcs": 100.0, "cal_mcs": 200.0}


def test_the_refit_record_fits_the_unloaded_records_and_the_extra_rows_at_pml_weight(gates, tmp_path):  # ruling 6
    p3.variant(gates, "a", "ifa2g4", {})
    record = p3.run_step(gates, "a")
    p0.save(gates / "steps" / "p3-b-run.json", {**record, "step": "p3-b-run", "loaded": True})  # another process seen
    (row,) = p3.rows(gates)
    k = 100.0 * (1 + (runs.PML_WEIGHT - 1) * row["f_pml"]) / 200.0  # the fake's 100 MC/s, the calibration's 200
    mur = {"step": "a MUR run", "pool": 1, "cells": None, "f_pml": 0.0, "node_mcs": 200.0 * k, "cal_mcs": 200.0}
    data = p3.refit_record(gates, ("a MUR run", "p3-a-run"), [mur], tmp_path / "refit")
    assert data == json.loads((tmp_path / "refit.json").read_text(encoding="utf-8"))
    assert (data["rows"], data["like"]) == ([row, mur], ["a MUR run", "p3-a-run"])
    before = {"PML_WEIGHT": runs.PML_WEIGHT, "SMALL_SPEED": runs.SMALL_SPEED}
    assert data["before"] == json.loads(json.dumps(before))  # a level's int key as JSON's string
    result = data["result"]  # the pair at w: w kept, both rows at one k
    assert (result["w_fit"], result["w_line"]) == (pytest.approx(runs.PML_WEIGHT), pytest.approx(runs.PML_WEIGHT))
    assert (result["w"], result["moved"], result["small"]) == (runs.PML_WEIGHT, False, {"1": float(f"{k:.3g}")})
    md = (tmp_path / "refit.md").read_text(encoding="utf-8")
    assert "| step | pool | cells | f_pml | node_mcs | cal_mcs | k |" in md and "| a MUR run | 1 | – | 0 |" in md
    assert f"| p3-a-run | 1 | {row['cells']} |" in md and "| moved | False |" in md
