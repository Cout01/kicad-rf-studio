# SPDX-License-Identifier: GPL-3.0-or-later
import json
import shutil
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

import p3a
from kicad_rf_studio import pipeline, runs, worker
from kicad_rf_studio.core.post.farfield import efficiencies, eta_lines, port_powers, read_far_field

FAR = Path(__file__).parent / "fixtures" / "farfield"  # tools/make_farfield.py: a real 58 mm dipole, ended by ABORT
REF = json.loads((FAR / "reference.json").read_text(encoding="utf-8"))


def test_the_reader_reads_openems_0370s_far_field_layout():  # design 5.5; r3: the layout pinned by a real run
    s = read_far_field(FAR / "sphere.h5")
    assert np.allclose(s.f, REF["f_hz"], rtol=1e-6, atol=0)  # stored as float32
    assert np.allclose(s.theta, np.arange(0, 181, 5)) and np.allclose(s.phi, np.arange(0, 360, 5))  # degrees
    assert s.d.shape == (2, 37, 72)
    assert np.allclose(s.d_max, REF["sphere"]["d_max"], rtol=1e-12, atol=0)
    assert np.allclose(s.p_rad, REF["sphere"]["p_rad"], rtol=1e-12, atol=0)
    assert np.allclose(s.d.max(axis=(1, 2)), s.d_max, rtol=1e-6, atol=0)  # D = 4π·r²·P_rad(θ, φ)/Prad, openEMS's Dmax
    assert (s.d[:, [0, -1]] < 0.01 * s.d_max[:, None, None]).all()  # a z dipole's nulls on the z axis
    assert (s.d[:, 18].min(axis=1) > 0.99 * s.d_max).all()  # and its peak all round the θ = 90° ring


def test_the_cuts_are_the_three_principal_planes_at_f0():  # design 5.5: XZ and YZ as a θ sweep, XY as a φ sweep
    s, el, az = (read_far_field(FAR / f"{grid}.h5") for grid in ("sphere", "elevation", "azimuth"))
    assert np.allclose(el.f, s.f[:1], rtol=1e-6) and np.allclose(az.f, s.f[:1], rtol=1e-6)
    assert np.allclose(el.theta, np.arange(-180, 180)) and np.allclose(el.phi, [0, 90]) and el.d.shape == (1, 360, 2)
    assert np.allclose(az.theta, [90]) and np.allclose(az.phi, np.arange(360)) and az.d.shape == (1, 1, 360)
    assert np.allclose(el.p_rad, s.p_rad[:1], rtol=1e-9, atol=0)  # one surface integral, whatever the angles
    ring = az.d[0, 0]
    assert ring.min() > 0.99 * ring.max()  # round in XY
    assert np.allclose(el.d[0, [90, 270]], ring.max(), rtol=0.01) and (el.d[0, 180] < 0.01 * ring.max()).all()


def test_the_port_powers_are_openems_dft_over_the_whole_record():  # design 5.5: openEMS's convention, one window
    with np.load(FAR / "waves.npz") as w:
        p_acc, p_inc = port_powers(w["t_u"], w["u"][0], w["t_i"], w["i"][0], np.array(REF["f_hz"]))
    assert np.allclose(p_acc, REF["p_acc"], rtol=1e-12, atol=0) and np.allclose(p_inc, REF["p_inc"], rtol=1e-12, atol=0)


def test_a_half_wave_dipole_in_vacuum_radiates_what_its_port_accepts():  # design 5.5, 5.11
    s = read_far_field(FAR / "sphere.h5")
    with np.load(FAR / "waves.npz") as w:
        p_acc, p_inc = port_powers(w["t_u"], w["u"][0], w["t_i"], w["i"][0], s.f)
    e = efficiencies(s, p_acc, p_inc)
    assert np.allclose(e["eta_rad"], 1.0, atol=0.02) and np.allclose(e["eta_tot"], e["eta_rad"] * p_acc / p_inc)
    assert np.allclose(e["gain"], s.d_max * e["eta_rad"]) and np.allclose(e["realized_gain"], s.d_max * e["eta_tot"])
    assert eta_lines(s.f, e["eta_rad"]) == []


def test_eta_rad_above_1_02_is_flagged_at_its_worst_frequency():  # design 5.5
    f = np.array([2.45e9, 2.4e9, 2.5e9])
    assert eta_lines(f, np.array([1.0, 1.03, 1.025])) == [
        ("W_ETA_RAD", {"eta": "1.030", "f_mhz": "2400.0", "limit": "1.02"})]
    assert eta_lines(f, np.array([1.0, 1.02, 0.5])) == []
    assert eta_lines(f, np.array([np.nan, 1.5, 1.0])) == [
        ("W_ETA_RAD", {"eta": "nan", "f_mhz": "2450.0", "limit": "1.02"})]
    assert eta_lines(f, np.array([-np.inf, 1.5, 1.0])) == [
        ("W_ETA_RAD", {"eta": "-inf", "f_mhz": "2450.0", "limit": "1.02"})]


def test_a_far_field_file_in_another_layout_is_refused(tmp_path):  # r3: openEMS's legacy layout, or transposed
    legacy, transposed = tmp_path / "legacy.h5", tmp_path / "transposed.h5"
    for path in (legacy, transposed):
        shutil.copyfile(FAR / "elevation.h5", path)
    with h5py.File(legacy, "r+") as h5:  # openEMS's legacy layout: real and imaginary apart, stored (φ, θ)
        for name in ("E_theta", "E_phi"):
            fd = h5[f"/nf2ff/{name}/FD"]
            data = fd["f0"][()]
            del fd["f0"]
            fd["f0_real"], fd["f0_imag"] = data.real.T, data.imag.T
    with h5py.File(transposed, "r+") as h5:
        p = h5["/nf2ff/P_rad/FD/f0"][()]
        del h5["/nf2ff/P_rad/FD/f0"]
        h5["/nf2ff/P_rad/FD/f0"] = p.T
    for path in (legacy, transposed):
        with pytest.raises(ValueError, match="layout"):
            read_far_field(path)


def test_the_far_field_reader_loads_no_openems():  # Stage 1 3.1: only a worker imports it
    probe = "import sys, kicad_rf_studio.core.post.farfield; print(sorted({'openEMS', 'CSXCAD'} & set(sys.modules)))"
    assert subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True).stdout.strip() == "[]"


@pytest.mark.openems
def test_a_real_short_dipole_writes_its_dumps_and_its_far_field(tmp_path, monkeypatch):  # CI tier b; about 40 s
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    run = tmp_path / "run"
    runs.write_spec(run, p3a.dipole(p3a.SHORT_MM))
    job = runs.write_job(runs.job_dir(run, 1, "P1"), 1, "run", 2, 8e-9)  # past the pulse's end, 2·t0 = 5 ns
    runs.check_job(job, runs.run_jobs([job], 1, run, {})[job], "run", {})
    assert all((job / name).is_file() for name in worker.DUMPS)  # PML_8 and the box, under real openEMS
    s = read_far_field(pipeline.far_field(job)["sphere"])
    assert s.d.shape == (3, 37, 72) and np.isfinite(s.d).all() and (s.p_rad > 0).all()
