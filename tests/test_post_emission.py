# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io

import numpy as np
import pytest

from kicad_rf_studio.core.post.emission import (EMISSION_COLUMNS, R_M, emission_csv, emission_lines, emission_rows,
                                                floor_db, incident, null_floor, ring_lines, rings_csv)
from kicad_rf_studio.core.post.farfield import FarField, port_dft, port_powers, snapped

F = [1.83e9, 2.0e9, 2.745e9]
RINGS = [{"f_hz": 2.0e9, "q": 1000.0, "factor": 0.5}]  # truncates 1.9 to 2.1 GHz
PROJECT = {"f0_hz": 915e6, "band": {"f_lo_hz": 1.83e9, "f_max_hz": 3e9}}


def far(e_theta=3.0, p_rad=0.0099, f=F):
    theta, phi = np.arange(0, 181, 5.0), np.arange(0, 360, 5.0)
    shape = (len(f), theta.size, phi.size)
    et = np.zeros(shape, complex)
    et[:, 18, 0] = e_theta  # at θ 90°, φ 0°: 3 V/m at 1 m, 1 V/m at 3 m
    return FarField(np.array(f), theta, phi, np.full(len(f), p_rad), np.ones(len(f)), np.ones(shape), et,
                    np.zeros(shape, complex))


def waves(source=(2.0, 0.02), terms=((1.0, -0.02),)):
    """port_dft is 2·Δt·Σ x·e^(−j2πft): at Δt 0.5 s with one sample at t 0, U and I are those samples at every f."""
    t, ports = np.arange(4) * 0.5, [source, *terms]
    u, i = (np.array([[p[q], 0, 0, 0] for p in ports], float) for q in (0, 1))
    return t, u, t, i


def test_the_field_at_3_m_per_v_and_per_ma_and_the_closure():  # design 5.8; B4, B6, B8
    a, b, c = rows = emission_rows(far(), *waves(), RINGS, resistive=False, f0=915e6)
    # U 2, I 0.02: U_inc 1.5, P_acc 0.02, P_inc 3²/400 = 0.0225; the termination's ½·1·0.02 = 0.01
    assert (a["harmonic"], b["harmonic"], c["harmonic"]) == (2, None, 3)
    assert (a["e_3m"], a["e_v"], a["e_ma"]) == pytest.approx((1.0, 1 / 1.5, 0.05))
    assert (a["theta_deg"], a["phi_deg"]) == (90.0, 0.0)
    assert (a["p_inc"], a["p_acc"], a["p_term"]) == (pytest.approx(0.0225), pytest.approx(0.02), [pytest.approx(0.01)])
    assert a["eps"] == pytest.approx((0.02 - 0.0099 - 0.01) / 0.0225)
    assert a["eps_acc"] == pytest.approx((0.02 - 0.0099 - 0.01) / 0.02)  # report-only, on P_acc (AR-20)
    assert [r["closure"] for r in rows] == ["judged", "truncated", "judged"]
    assert [r["basis"] for r in rows] == ["closure-backed", "nf2ff-only", "closure-backed"]


def test_a_frequency_is_not_judged_with_little_power_taken_in_or_a_resistor_in_the_grid():  # design 5.8
    low = emission_rows(far(), *waves(source=(2.0, 1e-6)), [], resistive=False, f0=None)
    assert {r["closure"] for r in low} == {"p_acc_low"}
    rows = emission_rows(far(), *waves(), RINGS, resistive=True, f0=None)
    assert [r["closure"] for r in rows] == ["resistive", "truncated", "resistive"]


def test_incident_is_the_50_ohm_sources_forward_wave_on_port_powers_dft():  # design 5.8: P3-A's DFT
    t, u, _, i = waves()
    f = np.array(F)
    assert incident(t, u[0], t, i[0], f) == pytest.approx([1.5] * 3)
    U, I = port_dft(t, u[0], t, i[0], f)
    assert port_powers(t, u[0], t, i[0], f)[0] == pytest.approx(0.5 * (U * I.conj()).real)


def test_a_float32_frequency_snaps_to_its_listed_one_and_reads_as_its_harmonic():  # design 5.8
    stored = np.float32(2.745e9).item()
    assert stored != 2.745e9
    assert snapped(np.array([stored, 2.0e9 + 5000]), [2.745e9, 2.0e9]).tolist() == [2.745e9, 2.0e9 + 5000]
    rows = emission_rows(far(f=[1.83e9, 2.0e9, stored]), *waves(), [], resistive=False, f0=915e6)
    assert rows[2]["harmonic"] == 3


def test_the_csvs_hold_each_frequency_in_db_re_1_vm_per_v_and_per_ma_and_the_rings():  # design 5.8: units
    rows = emission_rows(far(), *waves(), RINGS, resistive=False, f0=915e6)
    table = list(csv.reader(io.StringIO(emission_csv(rows, ["P2"]).decode())))
    assert table[0] == [*EMISSION_COLUMNS, "p_term_P2_w", "eps", "closure", "p_rad_basis"] and len(table) == 4
    assert float(table[1][2]) == pytest.approx(20 * np.log10(1 / 1.5))
    assert float(table[1][3]) == pytest.approx(20 * np.log10(0.05))
    assert (table[1][1], table[2][1], table[2][-2]) == ("2", "", "truncated")
    assert rings_csv(RINGS).decode().splitlines() == ["f_hz,q,factor,truncating", "2000000000.0,1000.0,0.5,True"]


def test_the_lines_state_the_band_each_harmonic_the_closure_and_the_rings():  # design 5.7, 5.8
    rows = emission_rows(far(), *waves(), RINGS, resistive=False, f0=915e6)
    assert [c for c, _ in emission_lines(PROJECT, rows)] == [
        "I_EMISSION_BAND", "I_EMISSION_HARMONIC", "I_EMISSION_HARMONIC", "I_EMISSION_CLOSURE"]
    worse = emission_rows(far(p_rad=0.0), *waves(), [], resistive=False, f0=915e6)  # ε 0.444
    assert [c for c, _ in emission_lines(PROJECT, worse)][-1] == "W_EMISSION_CLOSURE"
    none = emission_rows(far(), *waves(), [], resistive=True, f0=915e6)
    assert "I_EMISSION_NOT_JUDGED" in [c for c, _ in emission_lines(PROJECT, none)]
    held = {"f_hz": 1.5e9, "q": None, "factor": 1.0}
    assert [c for c, _ in ring_lines([*RINGS, {"f_hz": 2.5e9, "q": 100.0, "factor": 0.005}, held], 31e-9)] == [
        "W_EMISSION_RING", "W_EMISSION_RING_HELD"]


def test_n_is_the_largest_vector_difference_over_the_sphere_per_v_at_3_m():  # design 5.10; f2
    u = np.full(3, 1.5)
    assert null_floor(far(3.0), far(3.0j), u, u) == pytest.approx([abs(3 - 3j) / R_M / 1.5] * 3)  # max|E| equal
    assert null_floor(far(3.0), far(3.3), u, u) == pytest.approx([0.3 / R_M / 1.5] * 3)
    with pytest.raises(ValueError):
        null_floor(far(), far(f=[1.83e9, 2.0e9, 2.8e9]), u, u)


def test_the_floor_is_r13s_form_rounded_up_to_0_05_db():  # design 5.10; R-13
    assert floor_db(np.array([10 ** (-47.28 / 20), 0.05, 0.0])).tolist() == [-37.7, -16.45, -np.inf]
