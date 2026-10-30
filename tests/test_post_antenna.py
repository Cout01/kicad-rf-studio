# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.figure import Figure

from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.post.antenna import (ANTENNA_LIMITS, DELTA_COLUMNS, antenna_csv, antenna_png, bandwidth,
                                                compare_png, compare_s11, delta_lines, deltas, deltas_csv,
                                                dip_resonance, draw_antenna, draw_compare, eta_what_if_lines,
                                                far_field_lines, far_field_of, farfield_csv, resonance, s11_lines,
                                                shown_zin, zin)
from kicad_rf_studio.core.post.waves import band_grid
from test_project import antenna_dict

FAR = Path(__file__).parent / "fixtures" / "farfield"
F = np.linspace(1.84e9, 2.99e9, 2301)


def dip(f, at=2.44e9, width=0.1e9):  # a resonance at `at`, |S11| 0.05
    return 0.9 - 0.85 * np.exp(-((f - at) / width) ** 2)


def edges(level_db):  # the exact crossings of dip()
    g = (0.9 - 10 ** (level_db / 20)) / 0.85
    return 2.44e9 - 0.1e9 * math.sqrt(-math.log(g)), 2.44e9 + 0.1e9 * math.sqrt(-math.log(g))


def far_of():
    return far_field_of({g: FAR / f"{g}.h5" for g in ("sphere", "elevation", "azimuth")}, FAR / "waves.npz")


def test_resonance_and_bandwidth():  # design 5.6
    k, f_res = resonance(F, dip(F))
    assert f_res == pytest.approx(2.44e9, abs=1e5)
    for level in (-10.0, -6.0):
        assert bandwidth(F, dip(F), k, level) == pytest.approx(edges(level), abs=2e4)
    assert bandwidth(F, dip(F), k, -30.0) is None
    f = band_grid(antenna_dict())  # 2.875 MHz steps: a dip between two points is found within 0.01 % of f0
    for at in (2.44e9, 2.4401e9, 2.4428e9):
        assert resonance(f, dip(f, at))[1] == pytest.approx(at, abs=1e-4 * 2.44175e9)
    low = dip(F, 1.95e9, 0.3e9)  # its -10 dB region runs off the band's low end
    assert bandwidth(F, low, resonance(F, low)[0], -10.0)[0] is None
    assert shown_zin(complex(48.24, -3.06)) == "48.2 - j3.1" and zin(np.array([0.0]))[0] == 50.0


def test_the_s11_lines():  # design 5.6
    d = antenna_dict()
    f = band_grid(d)
    assert (f[0], f[-1]) == (1.84e9, 2.99e9) and {2.4e9, 2.44175e9, 2.4835e9} <= set(f)
    lines = s11_lines(d, f, dip(f))
    assert [c for c, _ in lines] == ["I_ANTENNA_RELATIVE", "I_ANTENNA_RESONANCE", "I_ANTENNA_POINT", "I_ANTENNA_POINT",
                                     "I_ANTENNA_POINT", "I_ANTENNA_BANDWIDTH", "I_ANTENNA_BANDWIDTH"]
    assert (lines[1][1]["f_mhz"], lines[1][1]["port"]) == ("2440.0", "U1.1")  # refined; Zin at the radio pin
    assert [p["marker"] for c, p in lines if c == "I_ANTENNA_POINT"] == ["f_lo", "f0", "f_hi"]
    assert lines[-2][1]["level_db"] == "-10" and lines[-1][1]["level_db"] == "-6"
    edge = s11_lines(d, f, dip(f, 1.0e9, 0.3e9))
    assert ("W_RESONANCE_EDGE", {"f_mhz": "1840.0"}) in edge and ("I_ANTENNA_NO_BANDWIDTH", {"level_db": "-10"}) in edge
    low = s11_lines(d, f, dip(f, 1.95e9, 0.3e9))
    assert [(p["level_db"], p["f_lo_mhz"]) for c, p in low if c == "W_BANDWIDTH_EDGE"][0] == ("-10", "1840.0")


def test_the_far_field_files_and_lines():  # design 5.5, 5.6
    far = far_of()
    lines = far_field_lines(far)
    assert [c for c, _ in lines] == ["I_ANTENNA_FAR_FIELD"] * 2  # the fixture's 2 frequencies, ascending
    assert lines[0][1]["f_mhz"] == "2400.0" and float(lines[0][1]["d_dbi"]) == pytest.approx(2.157, abs=0.05)
    bad = {**far, "eff": {**far["eff"], "eta_rad": far["eff"]["eta_rad"] * 1.05}}  # plan 1's W_ETA_RAD, printed here
    assert [c for c, _ in far_field_lines(bad)] == ["I_ANTENNA_FAR_FIELD"] * 2 + ["W_ETA_RAD"]
    rows = list(csv.reader(io.StringIO(farfield_csv(far).decode())))
    assert rows[0] == ["f_hz", "theta_deg", "phi_deg", "e_theta_re", "e_theta_im", "e_phi_re", "e_phi_im", "d_dbi",
                       "gain_dbi", "realized_gain_dbi"] and len(rows) == 1 + 2 * 37 * 72
    rows = list(csv.reader(io.StringIO(antenna_csv(far, np.array([0.1, 0.2])).decode())))
    assert rows[0] == ["f_hz", "s11_db", "s11_deg", "zin_re", "zin_im", "mismatch", "p_acc_w", "p_inc_w", "p_rad_w",
                       "eta_rad", "eta_tot", "d_max_dbi", "gain_dbi", "realized_gain_dbi"] and len(rows) == 3


def test_a_missing_far_field_file_is_named(tmp_path):  # design 5.5: a run folder moved or deleted
    with pytest.raises(KrsError) as e:
        far_field_of({g: FAR / f"{g}.h5" for g in ("sphere", "elevation", "azimuth")}, tmp_path / "waves.npz")
    assert (e.value.code, e.value.params) == ("E_RESULTS_WAVES", {"path": str(tmp_path / "waves.npz")})


def test_the_summary_png_holds_the_label_and_the_limits():  # design 5.6; anti-goal 1: no number without them
    d = antenna_dict()
    f = band_grid(d)
    for far in (far_of(), None):  # a part-port run has no far field: S11 and the Smith chart only
        fig = Figure()
        draw_antenna(fig, f, dip(f).astype(complex), d, far, "proj")
        assert fig.get_suptitle() == render("I_PLOT_ANTENNA_TITLE", name="proj") + "\n" + render("I_ANTENNA_RELATIVE")
        assert all(render(code) in fig.texts[-1].get_text() for code in ANTENNA_LIMITS)
        assert antenna_png(f, dip(f).astype(complex), d, far, "proj").startswith(b"\x89PNG")


def test_the_summary_png_carries_the_what_if_label():  # design 5.7: under Stage 1 7.6's label, as summary.png
    d = antenna_dict()
    f = band_grid(d)
    fig = Figure()
    draw_antenna(fig, f, dip(f).astype(complex), d, None, "proj", "label")
    assert fig.get_suptitle() == (render("I_PLOT_ANTENNA_TITLE", name="proj") + "\n" + render("I_ANTENNA_RELATIVE")
                                  + "\nlabel")


def test_verify_compares_s11_and_the_resonance_with_the_retune():  # design 5.7; RF 5: a shallow minimum is no dip
    f = band_grid(antenna_dict())
    a, b = dip(f, 2.4495e9).astype(complex), dip(f, 2.438e9).astype(complex)  # each resonance on a grid point
    k0 = int(np.flatnonzero(f == 2.44175e9)[0])
    assert compare_s11(a, b, f, k0) == {
        "ds11_f0": pytest.approx(abs(a[k0] - b[k0])), "ds11_max": pytest.approx(np.abs(a - b).max()),
        "f_res_hz": pytest.approx(2.4495e9, abs=1), "f_res_retune_hz": pytest.approx(2.438e9, abs=1),
        "shift": pytest.approx(11.5e6 / 2.438e9, rel=1e-6)}
    flat = (0.9 - 0.3 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)).astype(complex)  # lowest |S11| -4.4 dB
    assert dip_resonance(f, flat) is None and dip_resonance(f, dip(f, 1.0e9, 0.3e9)) is None  # shallow; band's edge
    cmp = compare_s11(a, flat, f, k0)
    assert (cmp["f_res_hz"], cmp["f_res_retune_hz"], cmp["shift"]) == (pytest.approx(2.4495e9, abs=1), None, None)


def test_the_what_if_total_efficiency_takes_eta_rad_from_the_far_field():  # design 5.7
    far = {"sphere": SimpleNamespace(f=np.array([2.45e9, 2.4e9])), "eff": {"eta_rad": np.array([0.8, 0.9])}}
    assert eta_what_if_lines(far, np.array([0.99, 0.75])) == [
        ("I_ANTENNA_ETA_WHAT_IF", {"f_mhz": "2400.0", "eta_tot_pct": "67.5", "eta_rad_pct": "90.0",
                                   "delivered_pct": "75.0"}),
        ("I_ANTENNA_ETA_WHAT_IF", {"f_mhz": "2450.0", "eta_tot_pct": "79.2", "eta_rad_pct": "80.0",
                                   "delivered_pct": "99.0"})]


def far(eta, gain):  # far_field_of's shape for the deltas: f0, f_lo and f_hi recorded, in that order
    return {"sphere": SimpleNamespace(f=np.array([2.44175e9, 2.4e9, 2.4835e9])),
            "eff": {"eta_tot": np.array(eta), "gain": np.array(gain)}}


def up(db):  # 0.5 raised by db
    return 0.5 * 10 ** (db / 10)


def pair(f):  # a resonance 11.5 MHz up with a wider dip, η_tot +0.1, +0.3 and 0 dB at f_lo, f0 and f_hi, gain -0.25 dB
    return ((dip(f, 2.438e9), far([0.5, 0.5, 0.5], [1.5, 1.0, 1.0])),
            (dip(f, 2.4495e9, 0.12e9), far([up(0.3), up(0.1), 0.5], [1.5 * 10 ** -0.025, 1.0, 1.0])))


def test_the_deltas_and_whether_each_is_resolved():  # design 5.8
    d = antenna_dict()
    f = band_grid(d)
    rows = deltas(d, f, *pair(f))
    assert [(r["quantity"], r["marker"], r["unit"], r["delta_unit"], r["resolved"]) for r in rows] == [
        ("resonance", "", "MHz", "MHz", True), ("bandwidth_10db", "", "MHz", "MHz", True),
        ("eta_tot", "f_lo", "%", "dB", False), ("eta_tot", "f0", "%", "dB", True),
        ("eta_tot", "f_hi", "%", "dB", False), ("peak_gain", "f0", "dBi", "dB", True)]
    assert (rows[0]["base"], rows[0]["variant"], rows[0]["delta"]) == pytest.approx((2438.0, 2449.5, 11.5), abs=1e-6)
    assert rows[0]["threshold"] == pytest.approx(7.32525) and rows[2]["threshold"] == 0.2  # 0.3 % of f0; 0.2 dB
    assert rows[1]["delta"] == pytest.approx(24.52, abs=0.05)  # 122.63 to 147.14 MHz, interpolated in dB
    assert (rows[3]["f_hz"], rows[3]["base"], rows[3]["delta"]) == pytest.approx((2.44175e9, 50.0, 0.3))
    assert rows[5]["delta"] == pytest.approx(-0.25) and rows[5]["base"] == pytest.approx(10 * np.log10(1.5))


def test_far_field_deltas_need_both_far_fields():  # design 5.8; RF 5
    d = antenna_dict()
    f = band_grid(d)
    rows = deltas(d, f, (dip(f, 2.438e9), far([0.5] * 3, [1.0] * 3)), (dip(f, 2.435125e9), None))
    assert [r["quantity"] for r in rows] == ["resonance", "bandwidth_10db"]
    assert rows[0]["delta"] == pytest.approx(-2.875, abs=1e-6) and rows[0]["resolved"] is False  # 0.12 % of f0
    shallow = 0.9 - 0.5 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)  # lowest |S11| -8 dB: no -10 dB bandwidth
    bw = deltas(d, f, (dip(f, 2.438e9), None), (shallow, None))[1]
    assert bw["base"] == pytest.approx(122.63, abs=0.05) and (bw["variant"], bw["delta"], bw["resolved"]) == (
        None, None, None)
    flat = 0.9 - 0.3 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)  # lowest |S11| -4.4 dB: no resonance to judge
    res = deltas(d, f, (dip(f, 2.438e9), None), (flat, None))[0]
    assert (res["base"], res["variant"], res["delta"], res["resolved"]) == (pytest.approx(2438.0), None, None, None)


def test_the_delta_lines_and_csv():  # design 5.8
    d = antenna_dict()
    f = band_grid(d)
    rows = deltas(d, f, *pair(f))
    lines = delta_lines(d, rows)
    assert [code for code, _ in lines] == ["I_COMPARE_RESONANCE", "I_COMPARE_BANDWIDTH", "I_COMPARE_ETA",
                                           "I_COMPARE_ETA", "I_COMPARE_ETA", "I_COMPARE_GAIN", "I_COMPARE_THRESHOLDS"]
    assert lines[0][1] == {"base_mhz": "2438.0", "variant_mhz": "2449.5", "shift_mhz": "+11.5", "shift_pct": "+0.47",
                           "verdict": "T_RESOLVED"}
    assert lines[3][1] == {"marker": "f0", "f_mhz": "2441.8", "base_pct": "50.0", "variant_pct": "53.6",
                           "delta_db": "+0.30", "verdict": "T_RESOLVED"}
    assert lines[-1][1] == {"shift_pct": "0.3", "db": "0.2"}
    shallow = 0.9 - 0.5 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)
    flat = 0.9 - 0.3 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)
    assert [code for code, _ in delta_lines(d, deltas(d, f, (dip(f, 2.438e9), None), (shallow, None)))] == [
        "I_COMPARE_RESONANCE", "I_COMPARE_NO_BANDWIDTH", "I_COMPARE_NO_FAR_FIELD", "I_COMPARE_THRESHOLDS"]
    assert [code for code, _ in delta_lines(d, deltas(d, f, (dip(f, 2.438e9), None), (flat, None)))][0] == (
        "I_RESONANCE_NOT_COMPARED")
    table = list(csv.reader(io.StringIO(deltas_csv(rows).decode())))
    assert table[0] == list(DELTA_COLUMNS) and len(table) == 7 and table[1][-1] == "True"


def test_the_compare_png_overlays_both_with_the_label_and_the_limits():  # design 5.8; anti-goal 1
    d = antenna_dict()
    f = band_grid(d)
    for far_field in (far_of(), None):
        fig = Figure()
        draw_compare(fig, f, [("a", dip(f).astype(complex), far_field),
                              ("b", dip(f, 2.45e9).astype(complex), far_field)], d)
        assert fig.get_suptitle() == render("I_PLOT_COMPARE_TITLE", base="a", variant="b") + "\n" + render(
            "I_ANTENNA_RELATIVE")
        assert all(render(code) in fig.texts[-1].get_text() for code in ANTENNA_LIMITS)
        assert len(fig.axes) == (6 if far_field else 2)  # S11, Smith; η and the three cuts where both have a far field
        assert [line.get_label() for line in fig.axes[0].lines if not line.get_label().startswith("_")] == ["a", "b"]
    assert compare_png(f, [("a", dip(f).astype(complex), None), ("b", dip(f).astype(complex), None)], d).startswith(
        b"\x89PNG")
