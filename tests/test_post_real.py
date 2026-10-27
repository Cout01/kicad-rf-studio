# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio import runs
from kicad_rf_studio.core.model.spec import verify_spec
from kicad_rf_studio.core.post.checks import recip_err, sigma_max
from kicad_rf_studio.core.post.waves import grid, kappa_eq, s_matrix
from kicad_rf_studio.worker import ERR, LOG
from test_model_spec import DT, VPARTS, VPORTS
from test_readers import DUMPS
from test_worker import write_job

REAL = Path(__file__).parent / "fixtures" / "microstrip"
F, _ = grid(915e6, 3, 1.1)


def make_waves():
    """tools/make_waves.py's functions, loaded by the openems tests only (main does not run)."""
    return runpy.run_path(str(Path(__file__).parents[1] / "tools" / "make_waves.py"))


def real_records(folder=REAL):
    return [tuple(np.load(folder / f"job-{k}.npz")[x] for x in ("t_u", "u", "t_i", "i")) for k in (1, 2)]


def run_worker(job):
    with open(job / LOG, "wb") as out, open(job / ERR, "wb") as err:
        return subprocess.run([sys.executable, "-I", "-u", "-m", "kicad_rf_studio.worker", "job.json"], cwd=job,
                              stdout=out, stderr=err, env={**os.environ, "OPENBLAS_NUM_THREADS": "1"}).returncode


def test_the_reduction_on_real_openems_waves():  # C-41, spec 9.1 tier (a); r6 §11
    meta = json.loads((REAL / "meta.json").read_text(encoding="utf-8"))
    rec = real_records()
    S, A, _ = s_matrix(rec, F)
    assert meta["band"] == pytest.approx([457.5e6, 3.0195e9]) and meta["c_box"] == pytest.approx(2.3796e-14, rel=1e-3)
    assert np.abs((rec[0][2] - rec[0][0]) / meta["dt"] - 0.5).max() <= 1e-5  # currents half a timestep late
    assert recip_err(S).max() <= 1e-5 and sigma_max(S).max() <= 1.0 and kappa_eq(A).max() <= 1.05
    assert np.degrees(np.angle(S[71, 1, 0])) == pytest.approx(-21.12, abs=3.0)
    assert S[0, 1, 0].real > 0  # X-6: the lumped ports' sign, a thru reads positive near f1
    assert np.abs(s_matrix([(t, u, t, i) for t, u, _, i in rec], F)[0] - S).max() > 1e-4  # the half step counts
    shortcut = (S @ A) / np.diagonal(A, axis1=1, axis2=2)[:, None, :]  # b/a, the stop-rule monitor's form
    assert np.abs(shortcut - S).max() > 1e-3


@pytest.mark.openems
def test_the_waves_tool_and_the_lumped_port_order_on_real_openems(tmp_path, monkeypatch):  # C-41, X-6; about 70 s
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    tool = make_waves()
    tool["main"](tmp_path / "out", 5e-9)
    rec = real_records(tmp_path / "out")
    S = s_matrix(rec, F)[0]
    assert S[0, 1, 0].real > 0 and recip_err(S).max() <= 1e-5
    spec = tool["microstrip"](5e-9)
    p2 = spec["ports"][1]
    spec["ports"][1] = {**p2, "start": p2["stop"], "stop": p2["start"]}  # P2's box from its signal end down
    job = write_job(tmp_path, spec, "run")  # port 1 excited, as job-1.npz
    assert run_worker(job) == 0
    rev, (_, u, _, i) = np.load(job / "waves.npz"), rec[0]
    n = min(u.shape[1], rev["u"].shape[1])
    # openEMS keeps a lumped box's given order, so P2 now reads −u and −i (Task 2's flipped() relies on it)
    assert np.abs(rev["u"][1, :n] + u[1, :n]).max() <= 1e-6 * np.abs(u[1]).max()
    assert np.abs(rev["i"][1, :n] + i[1, :n]).max() <= 1e-6 * np.abs(i[1]).max()


@pytest.mark.openems
def test_verifys_grid_elements_run_stable(tmp_path):  # spec 7.6, C-36, C-37, C-41; about 45 s
    spec = make_waves()["microstrip"](5e-9)
    spec["ports"] = [{**q, "part": False} for q in spec["ports"]] + VPORTS[1:]  # tests/test_model_spec.py
    v = verify_spec(spec, VPARTS, DUMPS / "operator_dump.vtr", DT)  # every part's cell sits on the substrate's top
    assert [g["name"] for g in v["grid"]] == ["C1", "L1", "R3"] and [q["name"] for q in v["ports"]] == ["P1", "P2"]
    job = write_job(tmp_path, v, "run")
    assert run_worker(job) == 0
    u = np.load(job / "waves.npz")["u"]
    assert np.isfinite(u).all() and np.abs(u[:, 3 * u.shape[1] // 4:]).max() < 0.5 * np.abs(u).max()  # no growth
