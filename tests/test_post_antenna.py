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
from kicad_rf_studio.core.post.antenna import (ANTENNA_LIMITS, antenna_csv, antenna_png, bandwidth, compare_s11,
                                                dip_resonance, draw_antenna, eta_what_if_lines, far_field_lines,
                                                far_field_of, farfield_csv, resonance, s11_lines, shown_zin, zin)
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
