# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import numpy as np
import pytest

import p0
import p0a
from kicad_rf_studio import runs
from kicad_rf_studio.core.geometry import build_geometry
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
