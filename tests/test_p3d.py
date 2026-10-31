# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

import p0
import p3
import p3d
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.project import load_project
from test_p3 import gates  # noqa: F401 (the fixture)


@pytest.fixture(autouse=True)
def first_values(monkeypatch):  # the gates' own VALUES and REFINE, set on their branches, never reach a test
    monkeypatch.setattr(p3d, "VALUES", None)
    monkeypatch.setattr(p3d, "REFINE", None)


def p(df_rel=0.0, deta=0.0, dd=0.0, depth=(-12.5, -12.5), dbw=0.1, ds11=0.004):  # a pair's deltas, f0 2441.75 MHz
    return {"f0_hz": 2.44175e9, "df_rel": df_rel, "deta_tot_db": [deta] * 3, "deta_rad_db": [deta] * 3,
            "dgain_db": dd, "dd_db": dd, "dbw_mhz": dbw, "ds11_max": ds11, "depth_db": depth}


def test_the_thresholds_are_three_times_the_noise_never_below_the_defaults():  # ruling 10; BW_LIMIT's rule
    assert p3d.thresholds({"f_rel": 0.0004, "db": 0.03, "bw_rel": 0.0005}) == {"shift_rel": 0.003, "db": 0.2,
                                                                                 "bw_rel": None}
    t = p3d.thresholds({"f_rel": 0.0013, "db": 0.09, "bw_rel": 0.0005})
    assert (t["shift_rel"], t["db"]) == (pytest.approx(0.004), pytest.approx(0.3))  # 0.0039 and 0.27, rounded up
    assert p3d.thresholds({"f_rel": 0.001, "db": 0.2 / 3, "bw_rel": 0.0})["shift_rel"] == 0.003  # at the defaults
    assert p3d.thresholds({"f_rel": 0.0004, "db": 0.03, "bw_rel": 0.0011})["bw_rel"] == pytest.approx(0.0035)


def test_the_p3d_rules():  # design 5.11 P3-D; RF 3
    pairs = {"repeat": p(), "shift": p(0.0001, 0.01), "dxp": p(0.002, -0.1), "dxm": p(-0.0015, 0.05)}
    d = p3d.decide_d(pairs)
    assert d["verdict"]["value"] == "pass" and (d["noise"]["f_rel"], d["noise"]["db"], d["noise"]["ds11"]) == (
        0.002, 0.1, 0.004)
    assert (d["shift_rel"], d["db"], d["bw_rel"]) == (pytest.approx(0.006), pytest.approx(0.3), None)  # a pass widens
    assert d["odd_even"]["f_rel"] == (pytest.approx(0.00175), pytest.approx(0.00025)) and d["position_bound"] is True
    assert d["screen"]["kept"] is True  # every dip 6.5 dB under -6 dB, its depth noise 0
    assert p3d.decide_d({**pairs, "dxm": p(-0.00201)})["verdict"]["fails"] == ["dxm"]
    assert p3d.decide_d({**pairs, "dxp": p(deta=0.101)})["verdict"]["fails"] == ["dxp"]
    unconditioned = p3d.decide_d({**pairs, "shift": p(depth=(-12.5, -5.9))})
    assert unconditioned["verdict"] == {"value": "fail", "fails": ["shift"]} and unconditioned["shift_rel"] is None
    assert p3d.decide_d({**pairs, "repeat": None})["verdict"]["value"] == "incomplete"


def test_the_p3e_rule():  # design 5.11 P3-E
    e = p3d.decide_e(p(-0.0031), 0.003, 0.2)
    assert (e["resolved"], e["sign"], e["pass"], e["ratio"]) == (True, "as expected", True, pytest.approx(1.0333, abs=1e-4))
    assert p3d.decide_e(p(-0.003), 0.003, 0.2)["pass"] is False  # resolved means larger, strictly (deltas' rule)
    assert p3d.decide_e(p(0.01), 0.003, 0.2)["sign"] == "opposite"  # soft: reported, still a pass
    assert p3d.decide_e(p(-0.01, depth=(-12.5, -5.0)), 0.003, 0.2)["pass"] is False  # the pour lifted the dip


def test_p3d_runs_retunes_copies_and_verifies(gates, monkeypatch):  # design 5.11 P3-D; r3 Q1
    monkeypatch.setenv("KRS_FAKE", "network")  # as pi_run: the pi's 4 jobs on the known network
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # the fake's operator dump is empty
    p0.save(gates / "p3c" / "p3c.json", {"decisions": {"edits_2g4": {}}})
    assert p3d.main(["--out", str(gates), "--steps", "ifa2g4_pi"]) == 0
    assert all((gates / "steps" / f"p3-{s}.json").is_file()
               for s in ("d-ifa2g4_pi-run", "d-ifa2g4_pi-verify", "d-ifa2g4_pi-rep-verify"))
    base, rep = (p3.project_path(gates, n) for n in ("d-ifa2g4_pi", "d-ifa2g4_pi-rep"))
    assert load_project(rep)["verify"]["values"] == {"L1": "0R", "C2": "0.13pF", "C3": "1pF"}
    assert load_project(rep)["results"] == load_project(base)["results"]
    pr = p3d.pair(base, rep)  # one run, one verify model, one fake: the same S11
    assert pr["depth_db"][0] == pr["depth_db"][1] and pr["df_rel"] in (None, 0.0)
    v = p3.measure(gates, "d-ifa2g4_pi", "verify")
    assert (v["pool"], v["cal_mcs"]) == (1, 200.0) and v["cells"] > 0  # verify's one job: a row of the refit
    monkeypatch.setattr(p3d, "VALUES", ["L1=0R", "C2=0.1pF", "C3=1pF"])  # a re-searched set (Task 11 Step 2)
    assert p3d.main(["--out", str(gates), "--steps", "ifa2g4_pi"]) == 0  # every verify reruns: its key holds them
    assert load_project(rep)["verify"]["values"]["C2"] == "0.1pF" == load_project(base)["verify"]["values"]["C2"]
    monkeypatch.setattr(p3d, "REFINE", 3)  # P3-E's fallback: the next n, under its own names
    pj = p3d.configure(gates, "ifa2g4_pi")
    assert pj.parent.name == "r-ifa2g4_pi" and (load_project(pj)["mesh"]["n"],
                                                load_project(pj)["gates"]["fit2d_limit"]) == (3, 0.05)
