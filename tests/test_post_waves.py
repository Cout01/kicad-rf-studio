# SPDX-License-Identifier: GPL-3.0-or-later
import json
import shutil
import warnings
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.waves import grid, kappa_eq, level_db, s_matrix
from networks import star, synth_records

F0, F1, F2 = 915e6, 457.5e6, 3.0195e9
DT = 1.73972e-13  # the dumps model's dt (tests/test_readers.py)
F, Q = grid(F0, 3, 1.1)


def test_the_grid_puts_f0_and_its_harmonics_on_exact_points():  # C-11
    assert (len(F), Q, F[0]) == (398, 142, F1)
    assert (F[71], F[213], F[355]) == (F0, 2 * F0, 3 * F0)  # bit-exact
    assert F[-1] <= F2 and np.allclose(np.diff(F), F0 / Q, rtol=1e-12, atol=0)


@pytest.mark.parametrize("n", [2, 3, 6])
def test_s_is_the_network_the_waves_came_from(n):  # spec 7.1, C-8; r6 §12: ≤ 1e-5, ≤ 1e-13 smooth
    S, A = s_matrix(synth_records(lambda f: star(f, n), n, F1, F2, DT, 10e-9), F)
    assert np.abs(S - star(F, n)).max() <= 1e-5 and kappa_eq(A).max() <= 1.02
    smooth = s_matrix(synth_records(lambda f: star(f, n), n, F1, F2, DT, 15e-9, smooth=True), F)[0]
    assert np.abs(smooth - star(F, n)).max() <= 1e-13


def test_job_scale_and_order_cancel_and_the_half_step_counts():  # C-8
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    S = s_matrix(rec, F)[0]
    scaled = [(t, u * k, ti, i * k) for (t, u, ti, i), k in zip(rec, (0.1, 3.0, 10.0))]
    assert np.abs(s_matrix(scaled, F)[0] - S).max() <= 1e-13
    assert np.abs(s_matrix(rec[::-1], F)[0] - S).max() == 0
    cut = [(t[:n], u[:, :n], ti[:n], i[:, :n]) for (t, u, ti, i), n in zip(rec, (120, 200, 242))]
    assert np.abs(s_matrix(cut, F)[0] - star(F, 3)).max() <= 1e-5  # jobs of different lengths
    no_half_step = [(t, u, t, i) for t, u, _, i in rec]
    assert np.abs(s_matrix(no_half_step, F)[0] - star(F, 3)).max() > 1e-4


def test_the_excitation_level_is_the_pulse_spectrum():  # spec 5.8, C-12
    _, A = s_matrix(synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9), F)
    assert level_db(A)[[0, 71, 213, 355]] == pytest.approx([-19.65, -8.08, -0.10, -12.06], abs=0.05)


@pytest.mark.parametrize("bad", ["dead", "duplicated"])
def test_a_dead_or_duplicated_job_is_a_coded_refusal_without_a_warning(bad):  # C-9
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    t, u, ti, i = rec[1]
    rec[1] = (t, 0 * u, ti, 0 * i) if bad == "dead" else rec[0]
    with warnings.catch_warnings(), pytest.raises(KrsError) as e:
        warnings.simplefilter("error")
        s_matrix(rec, F)
    assert (e.value.code, e.value.params["f_mhz"]) == ("E_S_SINGULAR", "457.5")
