# SPDX-License-Identifier: GPL-3.0-or-later
"""The validity indicators of an S (spec 7.4): passivity, reciprocity and the loss budget, flags and never gates; and
the measures that compare two responses (spec 7.6): |ΔS| and the null shifts."""
import math

import numpy as np
from scipy.constants import c
from scipy.signal import find_peaks

from kicad_rf_studio.core.model.parts import Z0

# ponytail: the spec's provisional limits; plan 5 (P0) tightens them
SIGMA_LIMIT, RECIP_LIMIT, LOSS_LIMIT = 1.02, 0.02, 0.02  # C-35
NULL_PROMINENCE_DB, NULL_WINDOW, NULL_HALF = 20.0, 0.05, 4  # C-39: prominence, ± match window, fit half-width


def sigma_max(s: np.ndarray) -> np.ndarray:
    """σ_max (F,): the largest singular value of S (F, N, N) at each f, above 1 where S makes power (C-33); never
    skrf's `passivity`, which is not σ_max."""
    return np.linalg.norm(s, 2, axis=(-2, -1))


def recip_err(s: np.ndarray) -> np.ndarray:
    """The reciprocity error (F,): the largest |S_ij − S_ji| over i, j at each f (C-33)."""
    return np.abs(s - s.mT).max(axis=(-2, -1))


def loss_budget(s: np.ndarray, ext: list[int], zk: np.ndarray) -> np.ndarray:
    """P_layout (F,): the power the layout N-port `s` (F, N, N) loses itself for a unit wave into port ext[0], the
    other ports of `ext` matched and every other port, the m-th of them in index order, closed by zk[:, m] (zk: F, M)
    of Γ = (Z − Z0)/(Z + Z0) (C-34). The waves out of the closed ports b_i = (I − S_ii·Γ)⁻¹·S_ie[:, :, 0] give
    S'_e1 = S_ee[:, :, 0] + S_ei·Γ·b_i, P_u = 1 − Σ_e |S'_e1|² and the part losses P_parts = Σ_k |b_k|²·(1 − |Γ_k|²);
    P_layout = P_u − P_parts, and M = 0 gives P_parts = 0."""
    closed = [k for k in range(s.shape[-1]) if k not in ext]
    g = (zk - Z0) / (zk + Z0)
    s_ee0, s_ei = s[:, ext, ext[0]], s[:, ext][:, :, closed]  # S_ee[:, :, 0] (F, P), S_ei (F, P, M)
    s_ie0, s_ii = s[:, closed, ext[0]], s[:, closed][:, :, closed]  # S_ie[:, :, 0] (F, M), S_ii (F, M, M)
    b = np.linalg.solve(np.eye(len(closed)) - s_ii * g[:, None, :], s_ie0[..., None])[..., 0]  # b_i (F, M)
    s_e1 = s_ee0 + (s_ei @ (g * b)[..., None])[..., 0]  # S'_e1 (F, P)
    return 1 - (np.abs(s_e1) ** 2).sum(axis=1) - (np.abs(b) ** 2 * (1 - np.abs(g) ** 2)).sum(axis=1)


def loss_expected(sections: list[tuple[float, float, float, float]], f0: float) -> float:
    """The expected dielectric loss of the straight sections (εr, εeff, tanδ, length in mm), a lower bound (C-25):
    1 − exp(−2·Σ α_d·ℓ), α_d = (π·f0/c)·εr·(εeff − 1)/(√εeff·(εr − 1))·tanδ in Np/m. The model's constant κ makes
    the effective tanδ = tanδ·f0/f, so the loss is the same at every f."""
    alpha_l = sum(math.pi * f0 / c * er * (eeff - 1) / (math.sqrt(eeff) * (er - 1)) * tan_d * length_mm * 1e-3
                  for er, eeff, tan_d, length_mm in sections)
    return 1 - math.exp(-2 * alpha_l)


def indicator_lines(f: np.ndarray, a_db: np.ndarray, s: np.ndarray, p_layout: np.ndarray | None,
                    expected: float, *, in_grid: bool = False) -> list[tuple[str, dict]]:
    """The indicator lines of S (F, N, N) on f (spec 7.4, C-33..C-35), each at its worst f with the excitation level
    a_db there (C-12): passivity, reciprocity and, given loss_budget's `p_layout`, the loss budget against
    loss_expected's `expected`, as I_VERIFY_LOSS_BUDGET or W_VERIFY_LOSS_BUDGET when the parts sat `in_grid` (verify's
    S: no part loss is removed). Each takes its W_ form above its limit."""
    def at(k: int) -> dict:
        return {"f_mhz": f"{f[k] / 1e6:.1f}", "a_db": f"{a_db[k]:.1f}"}

    sigma, err = sigma_max(s), recip_err(s)
    k, j = sigma.argmax(), err.argmax()
    lines = [("W_PASSIVITY" if sigma[k] > SIGMA_LIMIT else "I_PASSIVITY",
              {"sigma": f"{sigma[k]:.4f}", "limit": f"{SIGMA_LIMIT:g}", **at(k)}),
             ("W_RECIPROCITY" if err[j] > RECIP_LIMIT else "I_RECIPROCITY",
              {"err": f"{err[j]:.2e}", "limit": f"{RECIP_LIMIT:g}", **at(j)})]
    if p_layout is not None:
        k = p_layout.argmax()  # the worst excess, as `expected` is the same at every f
        warn, info = ("W_VERIFY_LOSS_BUDGET", "I_VERIFY_LOSS_BUDGET") if in_grid else ("W_LOSS_BUDGET", "I_LOSS_BUDGET")
        lines.append((warn if p_layout[k] - expected > LOSS_LIMIT else info,
                      {"layout_pct": f"{100 * p_layout[k]:.2f}", "expected_pct": f"{100 * expected:.2f}",
                       "limit_pct": f"{100 * LOSS_LIMIT:g}", **at(k)}))
    return lines


def _null_at(f: np.ndarray, s21: np.ndarray, k: int) -> float:
    """The null of S21 near the grid index k (C-39): the minimum of |p| over 4001 points across k ± NULL_HALF, p the
    complex quadratic least-squares fit of S21 there on (f − f_k)/Δf."""
    df = f[1] - f[0]
    window = slice(max(k - NULL_HALF, 0), k + NULL_HALF + 1)
    u = (f[window] - f[k]) / df
    fine = np.linspace(u[0], u[-1], 4001)
    return float(f[k] + fine[np.abs(np.polyval(np.polyfit(u, s21[window], 2), fine)).argmin()] * df)


def nulls(f: np.ndarray, s21: np.ndarray, floor: float) -> np.ndarray:
    """The null frequencies (Hz) of |S21| on f (C-39): the peaks of −dB of prominence NULL_PROMINENCE_DB whose two
    shoulders, the |S21| at their bases, both stand at `floor` or above, so that noise makes none; each refined in
    the complex S21, never in dB at the null."""
    x = -20 * np.log10(np.abs(s21))
    peaks, props = find_peaks(x, prominence=NULL_PROMINENCE_DB)
    shoulder = 10 ** (-np.maximum(x[props["left_bases"]], x[props["right_bases"]]) / 20)
    return np.array([_null_at(f, s21, k) for k, low in zip(peaks, shoulder) if low >= floor])


def match_null(f: np.ndarray, s21: np.ndarray, fn: float) -> float | None:
    """The null of S21 that matches fn (C-39): the minimum of |S21| on f within fn·(1 ± NULL_WINDOW), refined as
    nulls refines one; None when it sits on the window's edge, so the window holds no null."""
    idx = np.flatnonzero(np.abs(f / fn - 1) <= NULL_WINDOW)
    k = idx[np.abs(s21[idx]).argmin()]
    return None if k in (idx[0], idx[-1]) else _null_at(f, s21, k)


def compare(a: np.ndarray, b: np.ndarray, f: np.ndarray, k0: int, floor: float) -> dict:
    """How b differs from the reference a (verify's), each S (F, P, P) on f (spec 7.6, C-38, C-39), in plain floats:
    |ΔS21| in dB and the complex |ΔS11| at the grid index k0, the largest |ΔS| over f and every entry, and each null
    of a's S21 (`nulls` with `floor`) with its shift (f_a − f_b)/f_b to b's match_null, None when b has none there."""
    db21 = 20 * np.log10(np.abs([a[k0, 1, 0], b[k0, 1, 0]]))
    shifts = []
    for fa in nulls(f, a[:, 1, 0], floor).tolist():
        fb = match_null(f, b[:, 1, 0], fa)
        shifts.append({"f_hz": fa, "shift": None if fb is None else (fa - fb) / fb})
    return {"ds21_db_f0": float(abs(db21[0] - db21[1])), "ds11_f0": float(abs(a[k0, 0, 0] - b[k0, 0, 0])),
            "ds_max": float(np.abs(a - b).max()), "nulls": shifts}
