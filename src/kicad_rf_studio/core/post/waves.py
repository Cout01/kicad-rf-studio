# SPDX-License-Identifier: GPL-3.0-or-later
"""S from a run's waves (spec 7.1): the co-simulation grid, the waves a and b of every job, S = B·A⁻¹, and the layout
N-port of a run's folder."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import Z0
from kicad_rf_studio.core.post.si import uniform_grid
from kicad_rf_studio.core.project import antenna, pulse_band, si
from kicad_rf_studio.stoprule import KEPT

N_GRID = 400  # about this many points from f0/2 to band_factor·harmonics·f0
KAPPA_LIMIT = 10.0  # the largest κ_eq of A that S is computed from (C-9)


def grid(f0: float, harmonics: int, band_factor: float) -> tuple[np.ndarray, int]:
    """The co-simulation grid f and its q (C-11): f = f0·m/q from f0/2 to band_factor·harmonics·f0, so that n·f0 sits
    exactly at index n·q − q//2."""
    q = 2 * round(N_GRID / (2 * (band_factor * harmonics - 0.5)))
    m = np.arange(q // 2, int(np.floor(band_factor * harmonics * q * (1 + 1e-12))) + 1)
    return f0 * m / q, q


def band_grid(project: dict) -> np.ndarray:
    """An antenna's grid (Stage 3 design 5.6): the pulse's band, with f_lo, f0 and f_hi on it."""
    f_lo, f_hi = project["band"]["f_lo_hz"], project["band"]["f_hi_hz"]
    return np.unique(np.r_[np.linspace(*pulse_band(f_lo, f_hi), N_GRID + 1), f_lo, project["f0_hz"], f_hi])


def s_matrix(records: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
             f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """S = B·A⁻¹ and A, each (F, N, N), from N jobs' records (t_u, u, t_i, i), u and i of shape (N, n_j) cut to the
    job's end, job j exciting port j (spec 7.1, C-8). U and I are the direct DFT of u on t_u and of i on t_i, with no
    window, Δt or E(f): they cancel in B·A⁻¹. E_S_SINGULAR at the first f where κ_eq of A passes KAPPA_LIMIT (C-9)."""
    # ponytail: one DFT kernel on the longest job's times; jobs sampled at other instants would each need their own
    t_u, _, t_i, _ = max(records, key=lambda r: len(r[0]))
    k_u, k_i = (np.exp(-2j * np.pi * np.outer(t, f)) for t in (t_u, t_i))
    U = np.stack([(u @ k_u[:u.shape[1]]).T for _, u, _, _ in records], axis=2)  # (F, port, job)
    I = np.stack([(i @ k_i[:i.shape[1]]).T for _, _, _, i in records], axis=2)
    A, B = (U + Z0 * I) / (2 * np.sqrt(Z0)), (U - Z0 * I) / (2 * np.sqrt(Z0))
    kappa = kappa_eq(A)
    bad = np.flatnonzero(~(kappa <= KAPPA_LIMIT))  # NaN too
    if bad.size:
        raise KrsError("E_S_SINGULAR", kappa=f"{kappa[bad[0]]:.3g}", f_mhz=f"{f[bad[0]] / 1e6:.1f}",
                       limit=f"{KAPPA_LIMIT:g}")
    return np.linalg.solve(A.mT, B.mT).mT, A


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
    V_signal − V_reference; `markers`, the indices in f of f0, 2f0, … up to the project's harmonics (an antenna's f0
    alone), those f holds, or an SI project's marker (layout); the excitation level `a_db` (F,); model.json's port
    entries and which of them openEMS measured reversed."""
    f: np.ndarray
    markers: list[int]
    s: np.ndarray
    a_db: np.ndarray
    ports: list[dict]
    flipped: list[bool]


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
    own), at the frequencies `f` (Hz), by default the grid of `project` (spec 7.1, C-10), an antenna's band_grid; a
    point of f is n·f0 within 1e-9 relative, n up to the harmonics (1 for an antenna), and a_db is relative to its
    peak on f. An SI project's default grid is the TDR's, uniform_grid of its f_max_hz from DC, and its one marker the
    point of f nearest its marker_hz on any grid (argmin), never dropped (Stage 4 design 5.6: on the uniform grid
    240 MHz is index 48, 133 MHz index 27, read at 135, and 62.5 MHz index 12). Each job's waves are cut at its t_cut,
    both u and i, or taken whole when t_cut is None (t_max); S is then normalised to V_signal − V_reference at every
    flipped port. Raises E_RESULTS_JOB for a job whose S was not kept, then E_RESULTS_WAVES for a missing model.json,
    then for a job's missing waves file (run_dir itself when the job has none)."""
    jobs, run_dir = results["jobs"], Path(results["run_dir"])
    for job in jobs:
        if job["verdict"] not in KEPT:
            # ponytail: the term by name; test_post_waves requires one for each verdict whose S is not kept
            raise KrsError("E_RESULTS_JOB", port=job["port"], verdict="T_" + job["verdict"].upper())
    paths = [run_dir / "model.json", *(run_dir / job["waves"] if job["waves"] else run_dir for job in jobs)]
    for path in paths:
        if not path.is_file():
            raise KrsError("E_RESULTS_WAVES", path=str(path))
    records = []
    for job, path in zip(jobs, paths[1:]):
        with np.load(path) as waves:
            t_u, u, t_i, i = (waves[key] for key in ("t_u", "u", "t_i", "i"))
        n = len(t_u) if job["t_cut"] is None else np.searchsorted(t_u, job["t_cut"], "right")
        records.append((t_u[:n], u[:, :n], t_i[:n], i[:, :n]))
    f0 = project["marker_hz"] if si(project) else project["f0_hz"]
    if f is None:
        f = (uniform_grid(project["f_max_hz"]) if si(project) else band_grid(project) if antenna(project)
             else grid(f0, project["harmonics"], project["band_factor"])[0])
    s, a = s_matrix(records, f)
    ports = json.loads(paths[0].read_text(encoding="utf-8"))["ports"]
    flips = [flipped(port) for port in ports]
    d = np.where(flips, -1.0, 1.0)  # D·S·D, D = −1 at each flipped port (C-10)
    if si(project):  # the point nearest the marker, on any grid
        markers = [int(np.abs(f - f0).argmin())]
    else:
        markers = [int(k) for n in range(1, project.get("harmonics", 1) + 1)  # n·f0 to 1e-9; the grid's is n·q − q//2
                   for k in np.flatnonzero(np.isclose(f, n * f0, rtol=1e-9, atol=0))]
    return Layout(f, markers, s * np.outer(d, d), level_db(a), ports, flips)
