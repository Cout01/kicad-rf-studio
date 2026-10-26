# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import numpy as np
import pytest

import p0
import p0a
from kicad_rf_studio import runs
from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.stoprule import KEPT
from test_p0 import in_process

C0 = 299792458.0


def test_the_triplet_returns_the_lines_own_z0_and_the_discrete_beta():  # D-24, A-1; r7 §2.4
    f = np.array([0.6e9, 0.915e9, 2.8e9])
    beta, z0, d = 2 * np.pi * f * math.sqrt(3.41) / C0, 49.0, 75e-6
    x_v, x_i = np.array([-d, 0.0, d])[:, None], np.array([-d / 2, d / 2])[:, None]
    a, b = 1.0, 0.3 * np.exp(0.7j)  # a forward and a backward wave: exact for any mix
    v = a * np.exp(-1j * beta * x_v) + b * np.exp(1j * beta * x_v)
    i = (a * np.exp(-1j * beta * x_i) - b * np.exp(1j * beta * x_i)) / z0
    z, bt = p0a.triplet(v, i, (d, d), d)
    assert np.allclose(z, z0, rtol=1e-12, atol=0) and np.allclose(bt, 2 / d * np.sin(beta * d / 2), rtol=1e-9, atol=0)
    oblique = p0a.eps_eff(bt / math.cos(math.radians(45)), f, 45.0)  # x-normal planes across a 45° line
    assert np.allclose(oblique, (bt.real * C0 / (2 * np.pi * f)) ** 2, rtol=1e-12, atol=0)


def test_line_constants_read_the_probe_files_back(tmp_path):  # D-24: the files, their own sample times, the DFT
    z0, eeff, d = 49.0, 3.41, 75e-6
    v, t = C0 / math.sqrt(eeff), np.arange(0, 5e-9, 1e-11)
    probes = []
    for name, kind, x in (("p_v0", 0, -d), ("p_v1", 0, 0.0), ("p_v2", 0, d), ("p_i0", 1, -d / 2), ("p_i1", 1, d / 2)):
        tt = t + (5e-12 if kind else 0.0)  # currents half a step later, as openEMS writes them
        value = np.exp(-((tt - x / v - 1e-9) / 0.15e-9) ** 2) / (z0 if kind else 1.0)  # a forward pulse
        rows = zip(tt.tolist(), value.tolist())  # Python floats: numpy 2's repr would write np.float64(...)
        (tmp_path / name).write_text("% t/s\tvalue\n" + "".join(f"{p!r}\t{q!r}\n" for p, q in rows), encoding="utf-8")
        probes.append({"name": name, "type": kind, "weight": 1, **({"norm_dir": 0} if kind else {}),
                       "start": [110.0 + x * 1e3, -100.0, 0.745], "stop": [110.0 + x * 1e3, -100.0, 0.035]})
    z, e = p0a.line_constants(tmp_path, probes, np.array([915e6]), None, 0.0)
    assert z[0] == pytest.approx(z0, rel=1e-6) and e[0] == pytest.approx(eeff, rel=1e-4)


def test_a_coupon_model_has_two_vertical_feeds_and_a_triplet_at_the_cut():  # D-13, D-24
    model, geom, pts, lint = p0a.coupon_model("coupon_gcpw", 2)
    x = np.array(model.spec["mesh"]["x"])
    p1, p2 = model.spec["ports"]
    assert [(q["name"], q["dir"], q["start"][2], q["stop"][2], q["part"]) for q in (p1, p2)] == [
        ("P1", "z", 0.035, 0.745, False), ("P2", "z", 0.035, 0.745, False)]
    assert abs(p1["start"][0] - 100.0) < 0.08 and abs(p2["start"][0] - 120.0) < 0.08
    assert p1["start"][1] == p2["start"][1] == pytest.approx(-100.0, abs=0.04)
    assert [p["label"] for p in pts] == ["s0"] and lint == 0
    v0, v1, v2, i0, i1 = model.spec["probes"]
    assert [q["type"] for q in (v0, v1, v2, i0, i1)] == [0, 0, 0, 1, 1] and (i0["norm_dir"], i1["norm_dir"]) == (0, 0)
    k = int(np.flatnonzero(x == v1["start"][0])[0])
    assert (v0["start"][0], v2["start"][0]) == (x[k - 1], x[k + 1]) and abs(x[k] - 110.0) <= np.diff(x).max()
    assert (i0["start"][0], i1["start"][0]) == ((x[k - 1] + x[k]) / 2, (x[k] + x[k + 1]) / 2)
    assert (v1["start"][2], v1["stop"][2]) == (0.745, 0.035)
    lo, hi = sorted((i0["start"][1], i0["stop"][1]))
    assert -100.3 - 0.0752 < lo < -100.3 and -99.7 < hi < -99.7 + 0.0752  # just outside the 0.6 mm strip
    assert i0["start"][2] < 0.745 and i0["stop"][2] > 0.78


def test_every_coupon_is_fed_on_the_lines_nearest_its_track_ends():  # D-24: the twins too, at n = 2 and 3
    for name in p0a.COUPONS:
        ends = [p for t in p0a.coupon_project(name, 2)[0].tracks if t.net == "LINE" for p in (t.start, t.end)]
        free = sorted(e for e in ends if ends.count(e) == 1)  # an inner end is shared by two tracks
        for n in (2, 3):  # at n = 3 a cap's farthest vertex moved back by w/2 feeds the arc's P2 on the wrong y line
            model = p0a.coupon_model(name, n)[0]
            x, y = model.mesh.x, model.mesh.y
            assert [q["start"][:2] for q in model.spec["ports"]] == [
                [x[np.abs(x - u).argmin()], y[np.abs(y - v).argmin()]] for u, v in free], (name, n)


def test_the_twins_are_measured_at_their_midpoint_on_x_normal_planes():  # D-24
    assert p0a.points(build_geometry(*p0a.coupon_project("coupon_gcpw_45", 2)), "coupon_gcpw_45") == [
        {"label": "mid", "at": [107.071, -92.929], "normal": "x", "theta": 45.0, "section": None}]
    arc = p0a.points(build_geometry(*p0a.coupon_project("coupon_gcpw_arc", 2)), "coupon_gcpw_arc")
    assert [(p["label"], p["normal"], p["theta"]) for p in arc] == [("s0", "x", 0.0), ("s1", "y", 0.0),
                                                                    ("mid", "x", 45.0)]


def test_the_harness_builds_the_models_p0a_ran(tmp_path, monkeypatch):  # final review F6: --report on this code
    monkeypatch.setattr(p0, "cli", in_process)
    built = {name: spec_hash(p0a.coupon_model(name, 2)[0].spec) for name in p0a.COUPONS}
    built["coupon_gcpw_pads"] = p0a._pad(tmp_path)[0]  # new's project in tmp_path, as the harness makes it

    def ran(name):  # tests/fixtures/p0d: the spec_hash of the model each P0-A step ran (D-48)
        with np.load(p0.FIX / "p0d" / f"{name}.npz") as z:
            return str(z["spec_hash"])

    assert built == {name: ran(name) for name in built}


@pytest.mark.parametrize(("name", "z0_ref", "eeff_ref"), [
    ("coupon_ms", 49.0393, 3.3576), ("coupon_ms_masked", 48.3558, 3.4533),
    ("coupon_gcpw", 51.7855, 2.6516), ("coupon_gcpw_masked", 48.8051, 2.9853)])
def test_the_references_are_kicad_and_the_45h_2d_line(name, z0_ref, eeff_ref):  # D-25, A-2
    model, geom, pts, _ = p0a.coupon_model(name, 2)
    ref = p0a.references(geom, model.mesh, pts[0])
    assert (ref["z0_ref"], ref["eeff_ref"]) == (pytest.approx(z0_ref, abs=2e-3), pytest.approx(eeff_ref, abs=2e-4))
    if name == "coupon_gcpw_masked":
        assert ref["e_fit"] == pytest.approx(0.0378, abs=2e-4)  # R-P2-20: the row the gate blocks at n = 2


@pytest.mark.openems
def test_the_triplet_reads_the_microstrip_coupon_in_real_openems(tmp_path, monkeypatch):  # D-24, A-1; about 1 min
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    runs.save_settings({"machines": {runs.machine_key(): {"threads": 4, "pool": 1, "aggregate_mcs": 400.0}}})
    model, geom, pts, _ = p0a.coupon_model("coupon_ms", 2)
    run = p0.run_model(model, "normal", "e1", [1], t_max=6e-9)
    (job,) = run["jobs"]
    z0, eeff = p0a.line_constants(p0.run_path(run["run_dir"]) / job["job"], model.spec["probes"],
                                  np.array([p0a.F0]), job["t_cut"], 0.0)
    assert job["verdict"] in KEPT  # r7 measured 49.117 Ω and 3.4099 at 6 ns
    assert z0[0].real == pytest.approx(49.117, abs=0.5) and eeff[0] == pytest.approx(3.410, abs=0.03)


def test_the_p0a_rules():  # D-26, D-27, D-29, D-30; RF 2
    def r(e_fit, dz0, deeff=0.0, delta=0.2, verdict="converged", dt=1.0):
        return {"coupon": "coupon_gcpw", "n": 2, "point": "s0", "section": 0, "e_fit_pct": e_fit, "dz0_pct": dz0,
                "deeff_pct": deeff, "delta_pp": delta, "verdict": verdict, "lint": None, "dt_ratio": dt,
                "pass": abs(dz0) <= 5 and abs(deeff) <= 3}

    def twin(d2, d3, name="coupon_gcpw_45"):
        return [{"twin": name, "n": 2, "dz0_pct": d2}, {"twin": name, "n": 3, "dz0_pct": d3}]

    mid = {"coupon": "coupon_gcpw_45", "n": 2, "point": "mid", "section": None, "theta": 45.0, "verdict": "converged",
           "lint": None, "dt_ratio": 1.0, "pass": None}  # PF-19: a converged midpoint feeds only the twins
    m = {"rows": [r(2.55, 1.0, dt=0.95), r(3.78, 0.5), r(-3.5, 6.0), mid], "pairs": [{"pass": True}],
         "twins": twin(3.0, 2.0) + twin(2.5, 1.5, "coupon_gcpw_arc"), "pad": {"pass": True, "dt_ratio": 0.92},
         "stray": {"dt_ratio": 0.45, "trips": True}}
    d = p0a.decide(m)  # the −3.5 % row lies outside |e_fit| ≤ 3: the gate filters on the magnitude
    assert (d["fit2d"]["branch"], d["fit2d"]["i_at_3"], d["twins"]["branch"]) == ("keep", True, "advice")
    assert d["verdict"] == {"value": "pass", "fails": []}
    assert d["dt_floor"] == {"rule": "D-30", "min_ratio": 0.92, "stray_ratio": 0.45, "stray_trips": True}
    assert p0a.decide({**m, "rows": [r(2.9, 5.6), r(2.4, 1.0)]})["fit2d"] == {
        "rule": "D-29", "i_at_3": False, "limit_pct": 2.5, "max_delta_pp": 0.2, "ii": True, "branch": "lower"}
    assert p0a.decide({**m, "rows": [r(2.55, 1.0, deeff=3.2)]})["fit2d"]["branch"] == "lower"  # εeff counts in (i)
    assert p0a.decide({**m, "rows": [r(2.5, 1.0, delta=1.3)]})["fit2d"]["branch"] == "keep-state"
    low = p0a.decide({**m, "rows": [r(2.5, 1.0), r(0.3, 6.0)]})  # a row fit2d cannot explain: the floor holds
    assert (low["fit2d"]["branch"], low["fit2d"]["limit_pct"], low["verdict"]["value"]) == ("unpredicted", 3.0, "fail")
    flat = p0a.decide({**m, "rows": [r(2.5, 1.0), r(2.0, 9.0, verdict="t_max")]})  # left out, and named
    assert (flat["fit2d"]["branch"], flat["verdict"]["value"], len(flat["verdict"]["fails"])) == ("keep", "fail", 1)
    lint = {"coupon": "coupon_dense", "n": 3, "lint": "E_EDGE_LINT", "pass": False}
    assert p0a.decide({**m, "rows": [r(2.5, 1.0), lint]})["verdict"]["value"] == "fail"
    assert p0a.decide({**m, "twins": twin(-6.0, 4.0)})["twins"]["branch"] == "refuse"
    assert p0a.decide({**m, "twins": twin(3.0, 4.0) + twin(2.5, 1.5, "coupon_gcpw_arc")})["twins"]["branch"] == "keep"


def test_the_p0a_steps_run_through_the_harness_and_the_product(p0_out, monkeypatch):  # D-9, D-28, D-30
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-coupon_ms-n2,p0a-pad"]) == 0
    coupon, pad = (rec["result"] for rec in p0.records(p0_out, ["p0a-coupon_ms-n2", "p0a-pad"]))
    assert [j["verdict"] for j in coupon["jobs"]] == ["converged"] and coupon["blocked"] == []
    assert pad["exit"] == {"new": 0, "cost": 0, "run": 0}
    summary = p0.summary(p0.records(p0_out, ["p0a-pad"])[0])
    assert [j["verdict"] for j in summary["jobs"]] == ["converged"] * 2 and summary["warnings"] == ["W_LOSS_BUDGET"]
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps({"dt": 5e-14}))  # under 0.8 × coupon_gcpw's 6.7e-14 s
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-stray"]) == 0
    stray = p0.records(p0_out, ["p0a-stray"])[0]["result"]
    assert [code for code, _ in stray["blocked"]] == ["E_DT_FLOOR"] and stray["jobs"] == []


def test_rows_read_each_points_probes_at_f0_against_its_references(p0_out, monkeypatch):  # D-24, D-25, D-29
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-coupon_gcpw_arc-n2"]) == 0
    record = p0.records(p0_out, ["p0a-coupon_gcpw_arc-n2"])[0]
    model, geom, pts, _ = p0a.coupon_model("coupon_gcpw_arc", 2)
    job, t = p0.run_path(record["result"]["run_dir"]) / record["result"]["jobs"][0]["job"], np.arange(0, 6e-9, 1e-11)
    for pt in pts:  # the fake writes no probe file: a forward pulse of 50 Ω and εeff 2.7, 1/cos θ along the normal
        v, axis = C0 / math.sqrt(2.7) * math.cos(math.radians(pt["theta"])), "xy".index(pt["normal"])
        group = [q for q in model.spec["probes"] if q["name"].startswith(pt["label"] + "_")]
        for q in group:
            tt, x = t + (5e-12 if q["type"] else 0.0), (q["start"][axis] - group[0]["start"][axis]) * 1e-3
            value = np.exp(-((tt - x / v - 1e-9) / 0.15e-9) ** 2) / (50.0 if q["type"] else 1.0)
            (job / q["name"]).write_text("% t/s\tvalue\n" + "".join(
                f"{a!r}\t{b!r}\n" for a, b in zip(tt.tolist(), value.tolist())), encoding="utf-8")
    rows = p0a.rows(record, "coupon_gcpw_arc", 2)
    assert [(row["point"], row["section"], row["verdict"]) for row in rows] == [
        ("s0", 0, "converged"), ("s1", 1, "converged"), ("mid", None, "converged")]
    for row, pt in zip(rows, pts):
        assert (row["z0"], row["eeff"]) == (pytest.approx(50.0, rel=1e-6), pytest.approx(2.7, rel=1e-4))
        if pt["section"] is not None:
            ref = p0a.references(geom, model.mesh, pt)
            assert (row["dz0_pct"], row["delta_pp"], row["pass"]) == (
                pytest.approx(100 * (50.0 / ref["z0_ref"] - 1), rel=1e-5),
                pytest.approx(100 * (50.0 / ref["z0_2d"] - 1 - ref["e_fit"]), rel=1e-4), True)
    assert (rows[2]["dz0_pct"], rows[2]["delta_pp"], rows[2]["pass"]) == (None, None, None)  # a midpoint
    with pytest.raises(SystemExit):  # another model than the step ran
        p0a.rows({**record, "key": "other@" + record["code"]}, "coupon_gcpw_arc", 2)
    assert p0a.rows({"result": {"lint": ["E_EDGE_LINT", {}]}}, "coupon_dense", 3) == [
        {"coupon": "coupon_dense", "n": 3, "lint": "E_EDGE_LINT", "pass": False}]
