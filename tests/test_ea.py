# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import numpy as np
import pytest
from scipy.constants import physical_constants

import ea
import p0
from kicad_rf_studio.core.geometry.region import air_gap
from kicad_rf_studio.core.model.csx import EMISSION_NF2FF_MAX, NF2FF_MAX, PML_CELLS
from kicad_rf_studio.core.model.spec import emission_pulse


def test_the_dipole_is_p3as_12_mm_wire_with_the_emission_pulse_a_quarter_wave_of_1_ghz_off():  # 5.12 E-A (1)
    s = ea.dipole_spec()
    assert s["excitation"] == emission_pulse(1e9, 2.5e9) and s["excitation"]["t_max"] == 41e-9
    assert s["boundary"] == "pml_8" and [c["z"] for c in s["metal"]["curves"]] == [[0.5, 6.0], [-6.0, -0.5]]
    assert NF2FF_MAX < len(s["nf2ff"]["f_hz"]) <= EMISSION_NF2FF_MAX  # the emission cap runs
    assert s["mesh"]["z"][PML_CELLS] <= -6.0 - air_gap(1e9) and s["mesh"]["z"][-1 - PML_CELLS] >= 6.0 + air_gap(1e9)


def test_the_loop_is_four_one_cell_strips_and_a_one_cell_gap_port_on_the_mesh():  # 5.12 E-A (2)
    s = ea.loop_spec()
    assert s["copper"] == "sheet" and s["excitation"]["t_max"] == 69e-9 and s["excitation"]["emission"]
    assert len(s["metal"]["copper"]) == 5 and all(c["z"] == [0.0, 0.0] for c in s["metal"]["copper"])
    (p,) = s["ports"]
    assert (p["dir"], p["start"], p["stop"]) == ("x", [-0.05, -2.55, 0.0], [0.05, -2.45, 0.0])
    lines = {a: set(s["mesh"][a]) for a in "xyz"}
    assert all(n[0] in lines["x"] and n[1] in lines["y"] and n[2] in lines["z"] for n in p["nodes"])
    assert np.diff(sorted(v for v in lines["x"] if abs(v) <= 2.65)).max() <= 0.1 + 1e-9
    assert ea.loop_area_mm2(s) == pytest.approx(25.0)


def test_the_committed_criteria_are_the_design_s_closed_forms_and_never_regenerated():  # 5.12: frozen first
    crit = json.loads(ea.CRITERIA.read_text(encoding="utf-8"))
    assert crit == ea.criteria()
    eta, k = physical_constants["characteristic impedance of vacuum"][0], 2 * math.pi * 2.5e9 / 299792458
    assert crit["dipole"]["e_r_per_a"][-1] == pytest.approx(eta * math.tan(k * 0.012 / 4) / (2 * math.pi))
    assert crit["loop"]["e_per_ma"][1] == pytest.approx(1.3169e-14 * 1e18 * 25e-6 / 3 * 1e-3)  # 1.097e-4 (r3)
    assert crit["expected_blocks"] == {"dipole": [], "loop": ["E_PORT_SHORT"]}  # a closed loop is one PEC piece
    assert crit["dipole"]["eta_judged_expected"] == 0
    with pytest.raises(SystemExit, match="never regenerated"):
        ea.main(["--criteria"])


def measured(crit, de=0.0, di=0.0, eta=1.0, ratio=1e-2, dl=0.0, verdict="converged", blocked=((), ())):
    d, lo, r = crit["dipole"], crit["loop"], crit["r_m"]
    p_rad, d_max = np.full(len(d["f_hz"]), 1e-3), np.full(len(d["f_hz"]), 1.5)
    e_3m = np.sqrt(crit["eta_ohm"] * d_max * p_rad / (2 * np.pi)) / r * 10 ** (di / 20)
    dipole = {"verdict": verdict, "blocked": list(blocked[0]), "f_hz": d["f_hz"], "e_3m": e_3m.tolist(),
              "d_max": d_max.tolist(), "e_ma": (np.array(d["e_r_per_a"]) * 10 ** (de / 20) / (1e3 * r)).tolist(),
              "p_rad": p_rad.tolist(), "p_acc": (p_rad / eta).tolist(), "p_inc": (p_rad / eta / ratio).tolist()}
    loop = {"verdict": "converged", "blocked": list(blocked[1]), "f_hz": lo["f_hz"],
            "e_ma": (np.array(lo["e_per_ma"]) * 10 ** (dl / 20)).tolist()}
    return {"dipole": dipole, "loop": loop}


def test_e_a_passes_inside_its_tolerances_and_names_each_miss():  # design 5.12 E-A's Pass column
    crit = ea.criteria()
    d = ea.decide(measured(crit, de=0.45, di=0.04, eta=1.019, dl=-0.45), crit)
    assert (d["verdict"], d["eta_judged"]) == ("pass", len(crit["dipole"]["f_hz"]))
    for kw, fail in (({"de": 0.55}, "dipole_e"), ({"di": 0.06}, "dipole_identity"), ({"eta": 1.03}, "dipole_eta"),
                     ({"dl": -0.55}, "loop_e")):
        assert (lambda d: (d["verdict"], d["fails"]))(ea.decide(measured(crit, **kw), crit)) == ("fail", [fail])
    d = ea.decide(measured(crit, eta=1.5, ratio=1e-4), crit)
    assert (d["verdict"], d["eta_judged"]) == ("pass", 0)  # η judged only at P_acc/P_inc ≥ 1e-3, and the count says so


def test_a_case_not_kept_missing_or_blocked_by_an_unexpected_gate_is_incomplete():  # Task 14's third branch
    crit = ea.criteria()
    assert ea.decide(measured(crit, blocked=((), ("E_PORT_SHORT",))), crit)["verdict"] == "pass"  # pre-registered
    for m in (measured(crit, verdict="diverged"), measured(crit, blocked=((), ("E_PORT_OPEN",))),
              measured(crit, blocked=(("E_PORT_SHORT",), ())), {**measured(crit), "loop": None}):
        assert ea.decide(m, crit)["verdict"] == "incomplete"


def test_the_e_a_steps_run_through_the_harness_with_the_fake_worker(p0_out, monkeypatch, capsys):  # ruling 10
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    # openEMS's dt sits near the Courant step, while the fake's fixed 1e-13 s trips E_DT_FLOOR on both models (0.8 ×
    # 9.6e-13 s on the dipole's 0.5 mm cells, 0.8 × 1.9e-13 s on the loop's 0.1 mm ones); --cost's exit reads the gate
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps({"dt": 9e-13}))
    assert ea.main(["--out", str(p0_out), "--cost"]) == 0
    cost = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert set(cost) == {"dipole", "loop"}
    assert all({"cells", "pml", "dt", "to_t_max_s", "blocked"} <= set(c) for c in cost.values())
    monkeypatch.delenv("KRS_FAKE_SETUP")  # the runs below keep the fake's own dt, which its records are written at
    assert ea.main(["--out", str(p0_out)]) == 0
    for case in ea.CASES:  # emission_rows ran on each one-port job, no termination (Task 6's review)
        res = json.loads((p0_out / "steps" / f"ea-{case}-a1.json").read_text(encoding="utf-8"))["result"]
        assert res["verdict"] in ("converged", "flat", "t_max") and res["f_hz"] and res["e_ma"] and res["p_inc"]
    result = json.loads((p0_out / "ea" / "ea-a1.json").read_text(encoding="utf-8"))
    assert set(result) == {"gate", "versions", "tools", "criteria", "runs", "decision", "calibration", "machine"}
    assert result["criteria"]["file"] == "tests/fixtures/ea/criteria.json"
    assert result["decision"]["verdict"] in ("pass", "fail", "incomplete")  # the fake's far field is P3-A's 58 mm
    step = json.loads((p0_out / "steps" / "ea-dipole-a1.json").read_text(encoding="utf-8"))
    assert f"+{p0.tools_id()}@" in step["key"]  # a tools change runs the step again
    assert (p0_out / "ea" / "ea-a1.md").read_text(encoding="utf-8").startswith("## EA-1")
