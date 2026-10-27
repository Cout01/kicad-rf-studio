# SPDX-License-Identifier: GPL-3.0-or-later
"""S from a run's waves (spec 7.1): the co-simulation grid, the waves a and b of every job, S = B·A⁻¹, and the layout
N-port of a run's folder."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import Z0
from kicad_rf_studio.stoprule import KEPT

N_GRID = 400  # about this many points from f0/2 to band_factor·harmonics·f0
KAPPA_LIMIT = 10.0  # the largest κ_eq of A that S is computed from (C-9)
TAIL_WINDOW_S = 6e-9  # the tail's fit window: a record's last 6 ns after the pulse (A-9)
TAIL_ORDER_MAX = 16  # the most poles a channel's tail takes
TAIL_SVD_REL = 1e-3  # a pole per Hankel singular value at least this × the largest
TAIL_FIT_TOL = 1e-2  # the largest share of a channel's window norm its poles may leave unexplained
TAIL_GROW = 1e-2  # the largest growth of a pole over the window; more refuses the tail
TAIL_TAU_MAX_S = 40e-9  # the slowest in-band decay a tail extrapolates
TAIL_MIN_SAMPLES = 3 * TAIL_ORDER_MAX  # 48: the fewest window samples a tail is fitted on
TAIL_WARN = 0.02  # W_TAIL_LARGE above this largest |S − S_dft| (design 5.2)


def grid(f0: float, harmonics: int, band_factor: float) -> tuple[np.ndarray, int]:
    """The co-simulation grid f and its q (C-11): f = f0·m/q from f0/2 to band_factor·harmonics·f0, so that n·f0 sits
    exactly at index n·q − q//2."""
    q = 2 * round(N_GRID / (2 * (band_factor * harmonics - 0.5)))
    m = np.arange(q // 2, int(np.floor(band_factor * harmonics * q * (1 + 1e-12))) + 1)
    return f0 * m / q, q


def tail(x: np.ndarray, t: np.ndarray, f: np.ndarray, t_free: float) -> np.ndarray | None:
    """The DFT (C, F) on f of each channel of x (C, n), sampled at t, continued beyond t[-1] by its fitted decaying
    poles (A-9, p7-tails' v3b, frozen by plan 7): a matrix pencil over the last TAIL_WINDOW_S after t_free (the pulse's
    end, 2·t0), its order the Hankel singular values ≥ TAIL_SVD_REL × the largest, at most TAIL_ORDER_MAX, the
    amplitudes fitted on every pole, the decaying ones alone extrapolated. None when the window holds fewer than
    TAIL_MIN_SAMPLES, or when a channel leaves more than TAIL_FIT_TOL of its norm unexplained, holds a pole growing by
    more than TAIL_GROW over the window, or keeps an in-band pole slower than TAIL_TAU_MAX_S. An all-zero channel
    gets no tail."""
    # ponytail: a pole the pencil puts on or just outside the unit circle without growing by TAIL_GROW is left out of
    # the tail, not refused; the stop rule's flat verdict flags such a job
    dt = t[1] - t[0]
    m0 = np.searchsorted(t, max(t[-1] - TAIL_WINDOW_S, t_free))  # the window starts after the pulse
    n = len(t) - m0
    if n < TAIL_MIN_SAMPLES:
        return None
    ph, out = np.exp(-2j * np.pi * f * dt), np.zeros((x.shape[0], len(f)), complex)
    for ch, y in enumerate(x[:, m0:]):
        if not (norm := np.linalg.norm(y)):
            continue
        _, s, vh = np.linalg.svd(np.lib.stride_tricks.sliding_window_view(y, n // 3 + 1), full_matrices=False)
        v = vh[:min(TAIL_ORDER_MAX, int((s >= TAIL_SVD_REL * s[0]).sum()))].conj().T
        z = np.linalg.eigvals(np.linalg.pinv(v[:-1]) @ v[1:])
        vd = z ** np.arange(n)[:, None]
        c = np.linalg.lstsq(vd, y, rcond=None)[0]
        if np.linalg.norm(vd @ c - y) > TAIL_FIT_TOL * norm or (np.abs(z) ** n > 1 + TAIL_GROW).any():
            return None
        z, c = z[np.abs(z) < 1], c[np.abs(z) < 1]  # decaying poles only beyond the cut
        if (dt / np.abs(1 - z * ph[:, None]).min(0) > TAIL_TAU_MAX_S).any():
            return None  # an in-band pole too slow to extrapolate
        out[ch] = np.exp(-2j * np.pi * f * (t[-1] + dt)) * (c * z ** n / (1 - z * ph[:, None])).sum(1)
    return out


def s_matrix(records: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]], f: np.ndarray,
             t_free: float | None = None) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """S = B·A⁻¹ and A, each (F, N, N), from N jobs' records (t_u, u, t_i, i), u and i of shape (N, n_j) cut to the
    job's end, job j exciting port j (spec 7.1, C-8), and the 0-based jobs that fell back. U and I are the direct DFT
    of u on t_u and of i on t_i, with no window, Δt or E(f): they cancel in B·A⁻¹. With `t_free`, the pulse's end, each
    job's U and I add the tails of its u and i beyond its cut, each on its own time base (A-9); a job whose record
    holds fewer than TAIL_MIN_SAMPLES samples, or for which either tail is None, keeps both plain and falls back.
    E_S_SINGULAR at the first f where κ_eq of A passes KAPPA_LIMIT (C-9)."""
    # ponytail: one DFT kernel on the longest job's times; jobs sampled at other instants would each need their own
    t_u, _, t_i, _ = max(records, key=lambda r: len(r[0]))
    k_u, k_i = (np.exp(-2j * np.pi * np.outer(t, f)) for t in (t_u, t_i))
    U = np.stack([(u @ k_u[:u.shape[1]]).T for _, u, _, _ in records], axis=2)  # (F, port, job)
    I = np.stack([(i @ k_i[:i.shape[1]]).T for _, _, _, i in records], axis=2)
    fallen = []
    for j, (t_uj, u, t_ij, i) in enumerate(records if t_free is not None else []):
        short = len(t_uj) < TAIL_MIN_SAMPLES  # falls back without calling tail: a one-sample record has no t[1]
        tail_u, tail_i = (None, None) if short else (tail(u, t_uj, f, t_free), tail(i, t_ij, f, t_free))
        if tail_u is None or tail_i is None:
            fallen.append(j)
        else:
            U[:, :, j] += tail_u.T
            I[:, :, j] += tail_i.T
    A, B = (U + Z0 * I) / (2 * np.sqrt(Z0)), (U - Z0 * I) / (2 * np.sqrt(Z0))
    kappa = kappa_eq(A)
    bad = np.flatnonzero(~(kappa <= KAPPA_LIMIT))  # NaN too
    if bad.size:
        raise KrsError("E_S_SINGULAR", kappa=f"{kappa[bad[0]]:.3g}", f_mhz=f"{f[bad[0]] / 1e6:.1f}",
                       limit=f"{KAPPA_LIMIT:g}")
    return np.linalg.solve(A.mT, B.mT).mT, A, fallen


def kappa_eq(a: np.ndarray) -> np.ndarray:
    """κ_eq (F,): the 2-norm condition number of A (F, N, N) after scaling each column to unit norm, so a job's level
    does not count; a zero column stays zero."""
    norm = np.linalg.norm(a, axis=1, keepdims=True)
    return np.linalg.cond(a / np.where(norm > 0, norm, 1))


def level_db(a: np.ndarray) -> np.ndarray:
    """The excitation level (F,) in dB (C-12): the lowest over the jobs j of 20·log10(|A_jj(f)| / max over f of
    |A_jj|)."""
    d = np.abs(np.diagonal(a, axis1=1, axis2=2))
    return (20 * np.log10(d / d.max(axis=0))).min(axis=1)


@dataclass(frozen=True)
class Layout:
    """The layout N-port of a run (spec 7.1): S (F, N, N) on f, ports in job order and every port
    V_signal − V_reference; `markers`, the indices in f of f0, 2f0, … up to the project's harmonics, those f holds;
    the excitation level `a_db` (F,); model.json's port entries and which of them openEMS measured reversed; `s_dft`,
    the plain DFT's S, normalised the same way; `fallback`, the ports of the jobs whose tail fit failed, whose S is
    their plain DFT (A-9)."""
    f: np.ndarray
    markers: list[int]
    s: np.ndarray
    a_db: np.ndarray
    ports: list[dict]
    flipped: list[bool]
    s_dft: np.ndarray
    fallback: list[str]


def flipped(port: dict) -> bool:
    """Whether openEMS measured the model.json `port` as V_reference − V_signal: a CurvePort whose start, its reference
    end, lies higher than its stop along the axis of the largest |stop − start| component, as openEMS orders a
    CurvePort's ends along that axis (ports.py v0.37.0). A lumped port keeps its box's given order."""
    if port["kind"] != "curve":
        return False
    axis = np.argmax(np.abs(np.subtract(port["stop"], port["start"])))  # as openEMS picks it: the first on a tie
    return port["start"][axis] > port["stop"][axis]


def layout(project: dict, results: dict, f: np.ndarray | None = None) -> Layout:
    """The layout N-port of the run `results` holds, its `run_dir` and `jobs` (project.json's results, or verify's
    own), at the frequencies `f` (Hz), by default the grid of `project` (spec 7.1, C-10); a point of f is n·f0 within
    1e-9 relative, and a_db is relative to its peak on f. Each job's waves are cut at its t_cut, both u and i, or taken
    whole when t_cut is None (t_max); S takes each job's fitted tail beyond its cut, after model.json's 2·t0 (A-9), and
    is then normalised to V_signal − V_reference at every flipped port. Raises E_RESULTS_JOB for a job whose S was not
    kept, then E_RESULTS_WAVES for a missing model.json, then for a job's missing waves file (run_dir itself when the
    job has none)."""
    jobs, run_dir = results["jobs"], Path(results["run_dir"])
    for job in jobs:
        if job["verdict"] not in KEPT:
            raise KrsError("E_RESULTS_JOB", port=job["port"], verdict=job["verdict"])
    paths = [run_dir / "model.json", *(run_dir / job["waves"] if job["waves"] else run_dir for job in jobs)]
    for path in paths:
        if not path.is_file():
            raise KrsError("E_RESULTS_WAVES", path=str(path))
    spec = json.loads(paths[0].read_text(encoding="utf-8"))
    records = []
    for job, path in zip(jobs, paths[1:]):
        with np.load(path) as waves:
            t_u, u, t_i, i = (waves[key] for key in ("t_u", "u", "t_i", "i"))
        n = len(t_u) if job["t_cut"] is None else np.searchsorted(t_u, job["t_cut"], "right")
        records.append((t_u[:n], u[:, :n], t_i[:n], i[:, :n]))
    f0 = project["f0_hz"]
    if f is None:
        f = grid(f0, project["harmonics"], project["band_factor"])[0]
    # ponytail: a second, plain DFT pass for s_dft, and every reduction refits the tails (about 0.3 s on lpf915, no
    # cache); one pass and a cache by run folder if retune slows
    s_dft = s_matrix(records, f)[0]
    s, a, fallen = s_matrix(records, f, 2 * spec["excitation"]["t0"])
    ports = spec["ports"]
    flips = [flipped(port) for port in ports]
    d = np.where(flips, -1.0, 1.0)  # D·S·D, D = −1 at each flipped port (C-10)
    dd = np.outer(d, d)
    markers = [int(k) for n in range(1, project["harmonics"] + 1)  # n·f0 to 1e-9; the grid's is index n·q − q//2
               for k in np.flatnonzero(np.isclose(f, n * f0, rtol=1e-9, atol=0))]
    return Layout(f, markers, s * dd, level_db(a), ports, flips, s_dft * dd, [jobs[k]["port"] for k in fallen])
