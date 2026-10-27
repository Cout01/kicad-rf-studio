# SPDX-License-Identifier: GPL-3.0-or-later
import json
import shutil
import warnings
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.waves import flipped, grid, kappa_eq, layout, level_db, s_matrix, tail
from networks import star, synth_records, terminate_np

F0, F1, F2 = 915e6, 457.5e6, 3.0195e9
DT = 1.73972e-13  # the dumps model's dt (tests/test_readers.py)
F, Q = grid(F0, 3, 1.1)
T0 = 9 / (np.pi * (F2 - F1))  # the synthetic pulse's t0, 9/(2π·fw): fake_run's model.json holds it (A-9)
DT_P = 41.3969e-12  # lpf915's probe step; the tail tests' records
T_FREE = 2.236e-9  # 2·t0 of the 915 MHz band: the pulse's end
MODES = [(1.0, 2.961e9, 10e-9), (0.5, 2.440e9, 13.5e-9)]  # P0-B's co-simulation poles near f2 (p7-tails)


def test_the_grid_puts_f0_and_its_harmonics_on_exact_points():  # C-11
    assert (len(F), Q, F[0]) == (398, 142, F1)
    assert (F[71], F[213], F[355]) == (F0, 2 * F0, 3 * F0)  # bit-exact
    assert F[-1] <= F2 and np.allclose(np.diff(F), F0 / Q, rtol=1e-12, atol=0)


@pytest.mark.parametrize("n", [2, 3, 6])
def test_s_is_the_network_the_waves_came_from(n):  # spec 7.1, C-8; r6 §12: ≤ 1e-5, ≤ 1e-13 smooth
    S, A, fallen = s_matrix(synth_records(lambda f: star(f, n), n, F1, F2, DT, 10e-9), F)
    assert np.abs(S - star(F, n)).max() <= 1e-5 and kappa_eq(A).max() <= 1.02 and fallen == []
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
    _, A, _ = s_matrix(synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9), F)
    assert level_db(A)[[0, 71, 213, 355]] == pytest.approx([-19.65, -8.08, -0.10, -12.06], abs=0.05)


@pytest.mark.parametrize("bad", ["dead", "duplicated"])
def test_a_dead_or_duplicated_job_is_a_coded_refusal_without_a_warning(bad):  # C-9
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    t, u, ti, i = rec[1]
    rec[1] = (t, 0 * u, ti, 0 * i) if bad == "dead" else rec[0]
    with warnings.catch_warnings(), pytest.raises(KrsError) as e:
        warnings.simplefilter("error")
        s_matrix(rec, F)
    assert (e.value.code, e.value.params["f_mhz"], e.value.params["limit"]) == ("E_S_SINGULAR", "457.5", "10")


P915 = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1}


def port(name, part=False):
    return {"name": name, "kind": "lumped", "dir": "x", "start": [0.0, 0.0, 0.0], "stop": [1.0, 0.0, 0.0],
            "nodes": [], "part": part}


def fake_run(tmp_path, rec, ports, t_cut=None):
    """A run folder with model.json (`ports`, and the synthetic pulse's t0 as its excitation) and one waves.npz per
    job of `rec`, and its results."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "model.json").write_text(json.dumps({"ports": ports, "excitation": {"t0": T0}}), encoding="utf-8")
    jobs = []
    for k, ((t_u, u, t_i, i), q) in enumerate(zip(rec, ports), 1):
        (run / f"job-{k}").mkdir()
        np.savez(run / f"job-{k}" / "waves.npz", t_u=t_u, u=u, t_i=t_i, i=i)
        jobs.append({"port": q["name"], "verdict": "converged", "t_cut": t_cut, "t_stop": float(t_u[-1]),
                     "residual_db": -61.0, "waves": f"job-{k}/waves.npz"})
    return {"run_dir": str(run), "jobs": jobs}


def test_the_layout_is_reduced_from_the_run_folder(tmp_path):  # spec 7.1, 6.3, C-8
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    t, u, ti, i = rec[0]
    late = 1e-2 * np.sin(2 * np.pi * 1e9 * t) * (t > 5e-9)  # after t_cut: a reduction that ignores the cut fails
    rec[0] = (t, u + late, ti, i + late / 50)
    lay = layout(P915, fake_run(tmp_path, rec, [port("P1"), port("P2"), port("C1", True)], t_cut=4e-9))
    assert (lay.markers, lay.flipped, [q["name"] for q in lay.ports]) == ([71, 213, 355], [False] * 3,
                                                                          ["P1", "P2", "C1"])
    assert np.array_equal(lay.f, F) and np.abs(lay.s - star(F, 3)).max() <= 1e-5
    assert lay.a_db[71] == pytest.approx(-8.08, abs=0.05)
    assert lay.fallback == ["P1", "P2", "C1"] and np.array_equal(lay.s, lay.s_dft)  # Review Focus 1: cut at 4 ns


def test_a_reversed_curve_port_is_normalised_and_the_chain_does_not_change(tmp_path):  # C-10, X-7
    flip = np.array([[1.0], [1.0], [-1.0]])
    rec = [(t, u * flip, ti, i * flip) for t, u, ti, i in synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)]
    curve = {"name": "L1", "kind": "curve", "dir": None, "start": [2.0, 5.0, 0.78], "stop": [2.0, 4.0, 0.78],
             "nodes": [], "part": True}
    lay = layout(P915, fake_run(tmp_path, rec, [port("P1"), port("P2"), curve]))
    assert lay.flipped == [False, False, True] and np.abs(lay.s - star(F, 3)).max() <= 1e-5
    zk = np.full((len(F), 1), 30 + 20j)
    raw = s_matrix(rec, F, 2 * T0)[0]
    assert np.abs(terminate_np(lay.s, [0, 1], zk) - terminate_np(raw, [0, 1], zk)).max() <= 1e-12
    assert not flipped({**curve, "start": [2.0, 4.0, 0.78], "stop": [2.0, 5.0, 0.78]}) and not flipped(port("P1"))


@pytest.mark.parametrize("what", ["verdict", "waves", "folder"])
def test_results_that_cannot_be_reduced_name_the_fix(tmp_path, what):  # C-22, X-5, P-8
    results = fake_run(tmp_path, synth_records(lambda f: star(f, 2), 2, F1, F2, DT, 10e-9), [port("P1"), port("P2")])
    run = Path(results["run_dir"])
    if what == "verdict":
        results["jobs"][1]["verdict"] = "diverged"
        expected = ("E_RESULTS_JOB", {"port": "P2", "verdict": "diverged"})
    elif what == "waves":
        (run / "job-2" / "waves.npz").unlink()
        expected = ("E_RESULTS_WAVES", {"path": str(run / "job-2" / "waves.npz")})
    else:
        shutil.rmtree(run)
        expected = ("E_RESULTS_WAVES", {"path": str(run / "model.json")})
    with pytest.raises(KrsError) as e:
        layout(P915, results)
    assert (e.value.code, e.value.params) == expected


def test_the_layout_at_other_frequencies_is_the_same_reduction(tmp_path):  # P0: EMerge's points, another band
    results = fake_run(tmp_path, synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9),
                       [port("P1"), port("P2"), port("C1", True)])
    whole, some = layout(P915, results), layout(P915, results, f=F[[71, 213, 300]])
    assert np.array_equal(some.f, F[[71, 213, 300]]) and some.markers == [0, 1]
    assert np.abs(some.s - whole.s[[71, 213, 300]]).max() <= 1e-12


def ring(t, modes):
    """Σ a·e^(−t/τ)·cos(2π·f·t) over `modes` (a, f, τ) as one channel (1, n)."""
    return sum(a * np.exp(-t / tau) * np.cos(2 * np.pi * fm * t) for a, fm, tau in modes)[None]


def continuation(modes, n):
    """The DFT on F of `modes` sampled at k·DT_P for every k ≥ n, from their true poles."""
    ph, out = np.exp(-2j * np.pi * F * DT_P), 0
    for a, fm, tau in modes:
        for z in np.exp((-1 / tau + np.array([2j, -2j]) * np.pi * fm) * DT_P):
            out = out + a / 2 * z ** n * np.exp(-2j * np.pi * F * n * DT_P) / (1 - z * ph)
    return out


def test_tail_is_the_analytic_continuation_of_damped_sinusoids():  # A-9 (E-1); measured 1.1e-13
    t = np.arange(0, 13.21e-9, DT_P)  # 320 samples: P0-B's verify P1 cut
    exact = continuation(MODES, len(t))
    assert np.abs(tail(ring(t, MODES), t, F, T_FREE)[0] - exact).max() <= 1e-8 * np.abs(exact).max()


def test_cut_plus_tail_equals_the_whole_record_dft():  # A-9; measured 9.1e-14
    t, whole = np.arange(0, 13.21e-9, DT_P), np.arange(0, 400e-9, DT_P)
    dft = [ring(x, MODES)[0] @ np.exp(-2j * np.pi * np.outer(x, F)) for x in (t, whole)]
    assert np.abs(dft[0] + tail(ring(t, MODES), t, F, T_FREE)[0] - dft[1]).max() <= 1e-6 * np.abs(dft[1]).max()


@pytest.mark.parametrize("modes", [[(1.0, 1e9, 200e-9)], [(1.0, 1e9, -20e-9)]], ids=["slow in band", "growing"])
def test_a_slow_in_band_or_a_growing_mode_falls_back(modes):  # Review Focus 2
    t = np.arange(0, 13.21e-9, DT_P)
    assert tail(ring(t, modes), t, F, T_FREE) is None


def test_an_undamped_mode_above_the_band_does_not_refuse():  # Review Focus 2: verify's 3.096 GHz mode, above f2
    t = np.arange(0, 13.21e-9, DT_P)
    x = ring(t, [(1.0, 2.961e9, 10e-9)]) + 0.01 * np.cos(2 * np.pi * 3.096e9 * t)
    assert F[-1] < 3.096e9 and tail(x, t, F, T_FREE) is not None


def test_a_record_shorter_than_48_samples_after_the_pulse_falls_back():  # Review Focus 1: Draft cuts near 4 ns
    short, enough = (np.arange(0, end, DT_P) for end in (4.2e-9, 4.25e-9))  # 47 and 48 samples after T_FREE
    assert tail(ring(short, MODES), short, F, T_FREE) is None
    assert tail(ring(enough, MODES), enough, F, T_FREE) is not None


def upto(rec, t_cut):
    """`rec` cut at t_cut, u and i at the same count, as layout cuts a job."""
    return [(t[:n], u[:, :n], ti[:n], i[:, :n]) for t, u, ti, i in rec for n in [np.searchsorted(t, t_cut, "right")]]


def growing(rec):
    """`rec` with job 0's u and i carrying a mode that grows after 5 ns, as traces' "growth" kind adds it."""
    t, u, ti, i = rec[0]
    g = lambda x: 1e-3 * np.exp(np.maximum(x - 5e-9, 0) / 1.3e-9) * (x > 5e-9) * np.sin(2 * np.pi * 1.5e9 * x)
    return [(t, u + g(t), ti, i - g(ti) / 50), *rec[1:]]


def test_a_job_whose_tail_fails_keeps_its_plain_dft():  # Review Focus 1, 2: per job, u and i together
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    assert s_matrix(growing(rec), F, 2 * T0)[2] == [0]
    for t_cut in (4e-9, 0.0):  # 43 samples after 2·t0, then one sample, which tail's t[1] lacks: every job falls back
        cut = upto(rec, t_cut)
        S, _, fallen = s_matrix(cut, F, 2 * T0)
        assert fallen == [0, 1, 2] and np.array_equal(S, s_matrix(cut, F)[0])


def test_the_layout_names_the_job_whose_tail_failed(tmp_path):  # A-9
    rec = growing(synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9))
    lay = layout(P915, fake_run(tmp_path, rec, [port("P1"), port("P2"), port("C1", True)]))
    assert lay.fallback == ["P1"] and np.array_equal(lay.s, s_matrix(rec, F, 2 * T0)[0])
    assert np.array_equal(lay.s_dft, s_matrix(rec, F)[0])
