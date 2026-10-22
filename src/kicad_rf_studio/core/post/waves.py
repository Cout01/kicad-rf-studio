# SPDX-License-Identifier: GPL-3.0-or-later
"""S from a run's waves (spec 7.1): the co-simulation grid, the waves a and b of every job, and S = B·A⁻¹."""
import numpy as np

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import Z0

N_GRID = 400  # about this many points from f0/2 to band_factor·harmonics·f0
KAPPA_LIMIT = 10.0  # the largest κ_eq of A that S is computed from (C-9)


def grid(f0: float, harmonics: int, band_factor: float) -> tuple[np.ndarray, int]:
    """The co-simulation grid f and its q (C-11): f = f0·m/q from f0/2 to band_factor·harmonics·f0, so that n·f0 sits
    exactly at index n·q − q//2."""
    q = 2 * round(N_GRID / (2 * (band_factor * harmonics - 0.5)))
    m = np.arange(q // 2, int(np.floor(band_factor * harmonics * q * (1 + 1e-12))) + 1)
    return f0 * m / q, q


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
        raise KrsError("E_S_SINGULAR", kappa=f"{kappa[bad[0]]:.3g}", f_mhz=f"{f[bad[0]] / 1e6:.1f}")
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
