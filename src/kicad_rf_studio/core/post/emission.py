# SPDX-License-Identifier: GPL-3.0-or-later
"""An emission run's results (Stage 5 design 5.7, 5.8): at each far-field frequency the largest field over the sphere
at 3 m, per V of the source's incident wave and per mA of its current, the powers and the energy closure, judged only
where no ring truncates it, the source takes in power and no resistor sits in the grid; the rings the job ends with;
and their CSVs and lines, labelled relative with their stated limits. Never a dBµV/m, a limit line or a standard's
name. Never imports openEMS, CSXCAD, Qt or matplotlib."""
import csv
import io
import math
import re
from collections.abc import Iterable

import numpy as np

from kicad_rf_studio.core.model.parts import Z0
from kicad_rf_studio.core.post.farfield import ETA_LIMIT, FarField, port_dft, port_powers
from kicad_rf_studio.stoprule import RING_FACTOR, RING_WIDTH, truncated

R_M = 3.0  # m: the field's distance, the worker's 1 m transform times 1/R_M, exact in the far field (design 5.8, B6)
P_ACC_MIN = 1e-3  # × P_inc: a frequency whose source takes in less is not closure-judged (P3-A's conditioning, B8)
BACKED = 3.0  # P_rad/P_inc of at least BACKED·|ε| is closure-backed (r5's test on B8's P_inc base)
EPS_LIMIT = round(ETA_LIMIT - 1, 6)  # |ε| over it raises W_EMISSION_CLOSURE: P3-A's η ± 0.02 (B8)
EMISSION_OUTPUTS = re.compile(r"emission(_rings)?\.csv")  # an emission run's files, matched whole
EMISSION_LIMITS = ("I_LIMIT_EMISSION",)  # design 5.8: stated after every emission result
EMISSION_COLUMNS = ("f_hz", "harmonic", "e_3m_db_per_v_relative", "e_3m_db_per_ma_relative", "theta_deg", "phi_deg",
                    "p_inc_w", "p_acc_w", "p_rad_w")
TERMS = {"judged": "T_CLOSURE_JUDGED", "truncated": "T_CLOSURE_TRUNCATED", "p_acc_low": "T_CLOSURE_P_ACC_LOW",
         "resistive": "T_CLOSURE_RESISTIVE", "closure-backed": "T_CLOSURE_BACKED", "nf2ff-only": "T_NF2FF_ONLY"}


def incident(t_u: np.ndarray, u: np.ndarray, t_i: np.ndarray, i: np.ndarray, f: np.ndarray) -> np.ndarray:
    """U_inc at `f` (Hz) of one port's 1-D records, u on t_u and i on t_i (s): (U + Z0·I)/2 of port_dft's U and I, the
    forward wave of a 50 Ω source (design 5.8, B4)."""
    U, I = port_dft(t_u, u, t_i, i, f)
    return (U + Z0 * I) / 2


def _harmonic(f: float, f0: float | None) -> int | None:
    """The carrier `f0`'s harmonic n at `f` (Hz): n = round(f/f0) when n ≥ 2 and |f − n·f0| ≤ 1e-6·n·f0, so that
    openEMS's float32 copy of a harmonic reads as it; None otherwise, and without a carrier."""
    n = round(f / f0) if f0 else 0
    return n if n >= 2 and abs(f - n * f0) <= 1e-6 * n * f0 else None


def emission_rows(sphere: FarField, t_u: np.ndarray, u: np.ndarray, t_i: np.ndarray, i: np.ndarray, rings: list[dict],
                  *, resistive: bool, f0: float | None) -> list[dict]:
    """One row per frequency of `sphere`, in its order (design 5.7, 5.8; B4, B6, B8), from the job's records u (ports,
    n) on t_u and i (ports, n) on t_i, row 0 the source and every other row a termination, and tail_fit's `rings`:
    "f_hz"; "harmonic", n or None (_harmonic); "e_3m", the largest over the sphere of √(|E_θ|² + |E_φ|²)/R_M in V/m,
    at "theta_deg" and "phi_deg"; "e_v" and "e_ma", e_3m per V of the source's incident wave and per mA of its current;
    "p_inc" and "p_acc", port_powers' of the source, "p_rad", the sphere's, and "p_term", each termination's
    −½·Re(U·I*), in W; "eps", B8's ε = (P_acc − P_rad − ΣP_term)/P_inc, and "eps_acc", the same residual over P_acc,
    report-only (AR-20); "closure", the first that holds of "truncated" (stoprule.truncated), "p_acc_low" (P_acc under
    P_ACC_MIN·P_inc) and "resistive" (`resistive`: a resistor in the grid takes power no probe measures), else
    "judged"; and "basis", "closure-backed" where judged with P_rad/P_inc at least BACKED·|ε|, else "nf2ff-only".
    Numbers are Python's."""
    f = sphere.f
    e = (np.sqrt(np.abs(sphere.e_theta) ** 2 + np.abs(sphere.e_phi) ** 2) / R_M).reshape(f.size, -1)  # (F, θ·φ)
    at_theta, at_phi = np.unravel_index(e.argmax(axis=1), sphere.e_theta.shape[1:])
    e_3m = e.max(axis=1)
    p_acc, p_inc = port_powers(t_u, u[0], t_i, i[0], f)
    p_term = np.reshape([-0.5 * np.real(U * np.conj(I))
                         for U, I in (port_dft(t_u, uk, t_i, ik, f) for uk, ik in zip(u[1:], i[1:]))], (-1, f.size))
    residual = p_acc - sphere.p_rad - p_term.sum(axis=0)
    columns = {"f_hz": f, "e_3m": e_3m, "theta_deg": sphere.theta[at_theta], "phi_deg": sphere.phi[at_phi],
               "e_v": e_3m / np.abs(incident(t_u, u[0], t_i, i[0], f)),
               "e_ma": e_3m / (np.abs(port_dft(t_u, u[0], t_i, i[0], f)[1]) * 1e3), "p_inc": p_inc, "p_acc": p_acc,
               "p_rad": sphere.p_rad, "p_term": p_term.T, "eps": residual / p_inc, "eps_acc": residual / p_acc}
    rows = []
    for k, cut in enumerate(truncated(f, rings)):
        row = {name: column[k].tolist() for name, column in columns.items()}  # Python numbers, p_term a list
        row["harmonic"] = _harmonic(row["f_hz"], f0)
        row["closure"] = ("truncated" if cut else "p_acc_low" if row["p_acc"] < P_ACC_MIN * row["p_inc"]
                          else "resistive" if resistive else "judged")
        backed = row["closure"] == "judged" and row["p_rad"] / row["p_inc"] >= BACKED * abs(row["eps"])
        row["basis"] = "closure-backed" if backed else "nf2ff-only"
        rows.append(row)
    return rows


def _csv(header: list[str], rows: Iterable[list]) -> bytes:
    """A CSV file of `header`, then `rows`: comma-separated, "\\n" line ends, numbers as Python's repr and None empty,
    as antenna._csv writes."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def emission_csv(rows: list[dict], names: list[str]) -> bytes:
    """emission.csv (design 5.8) of emission_rows' `rows`, in their order: EMISSION_COLUMNS, then p_term_<name>_w per
    termination of `names`, eps, closure and p_rad_basis. The field at 3 m is in dB re 1 (V/m)/V and dB re 1
    (V/m)/mA, 20·log10 of e_v and e_ma; the harmonic is empty where there is none."""
    return _csv([*EMISSION_COLUMNS, *(f"p_term_{name}_w" for name in names), "eps", "closure", "p_rad_basis"],
                ([r["f_hz"], r["harmonic"], 20 * np.log10(r["e_v"]), 20 * np.log10(r["e_ma"]), r["theta_deg"],
                  r["phi_deg"], r["p_inc"], r["p_acc"], r["p_rad"], *r["p_term"], r["eps"], r["closure"], r["basis"]]
                 for r in rows))


def rings_csv(rings: list[dict]) -> bytes:
    """emission_rings.csv (design 5.7) of tail_fit's `rings`: f_hz, q (empty for a ring that does not decay), factor,
    and truncating, whether the ring truncates frequencies: it has no Q, or its factor is over RING_FACTOR."""
    return _csv(["f_hz", "q", "factor", "truncating"],
                ([r["f_hz"], r["q"], r["factor"], r["q"] is None or r["factor"] > RING_FACTOR] for r in rings))


def ring_lines(rings: list[dict], t_end: float) -> list[tuple[str, dict]]:
    """The lines of tail_fit's `rings` at the job's end `t_end` (s) (design 5.7), in their order: W_EMISSION_RING for a
    ring with a Q whose factor is over RING_FACTOR, with the half-width RING_WIDTH·f_r/Q it truncates, and
    W_EMISSION_RING_HELD for a ring with none."""
    t_ns, lines = f"{t_end * 1e9:.2f}", []
    for r in rings:
        f_mhz = f"{r['f_hz'] / 1e6:.1f}"
        if r["q"] is None:
            lines.append(("W_EMISSION_RING_HELD", {"f_mhz": f_mhz, "t_ns": t_ns}))
        elif r["factor"] > RING_FACTOR:
            lines.append(("W_EMISSION_RING", {"f_mhz": f_mhz, "t_ns": t_ns, "q": f"{r['q']:.0f}",
                                              "factor": f"{r['factor']:.4f}",
                                              "width_mhz": f"{RING_WIDTH * r['f_hz'] / r['q'] / 1e6:.1f}"}))
    return lines


def emission_lines(project: dict, rows: list[dict]) -> list[tuple[str, dict]]:
    """The lines of emission_rows' `rows` (design 5.8): I_EMISSION_BAND, the project's band and the harmonics among the
    rows; I_EMISSION_HARMONIC per harmonic row, in their order; I_EMISSION_CLOSURE at the largest |ε| over the judged
    rows, a non-finite one the largest as eta_lines has it, or I_EMISSION_NOT_JUDGED; then W_EMISSION_CLOSURE when that
    |ε| is over EPS_LIMIT."""
    band = project["band"]
    harmonics = [r for r in rows if r["harmonic"]]
    shown = ", ".join(f"{r['f_hz'] / 1e6:g}" for r in harmonics) + " MHz" if harmonics else "T_NONE"
    lines = [("I_EMISSION_BAND", {"count": len(rows), "f_lo_mhz": f"{band['f_lo_hz'] / 1e6:g}",
                                  "f_max_mhz": f"{band['f_max_hz'] / 1e6:g}", "harmonics": shown})]
    lines += [("I_EMISSION_HARMONIC", {"n": r["harmonic"], "f_mhz": f"{r['f_hz'] / 1e6:g}",
                                       "e_v_db": f"{20 * np.log10(r['e_v']):.2f}",
                                       "e_ma_db": f"{20 * np.log10(r['e_ma']):.2f}", "theta_deg": f"{r['theta_deg']:g}",
                                       "phi_deg": f"{r['phi_deg']:g}", "rad_pct": f"{100 * r['p_rad'] / r['p_inc']:.3g}",
                                       "basis": TERMS[r["basis"]], "eps": f"{r['eps']:.4f}",
                                       "closure": TERMS[r["closure"]]})
              for r in harmonics]
    judged = [r for r in rows if r["closure"] == "judged"]
    if not judged:
        return lines + [("I_EMISSION_NOT_JUDGED", {"total": len(rows)})]
    worst = max(judged, key=lambda r: abs(r["eps"]) if math.isfinite(r["eps"]) else math.inf)
    at = {"eps": f"{abs(worst['eps']):.4f}", "f_mhz": f"{worst['f_hz'] / 1e6:g}", "limit": f"{EPS_LIMIT:g}"}
    lines.append(("I_EMISSION_CLOSURE", {"judged": len(judged), "total": len(rows), **at}))
    if not abs(worst["eps"]) <= EPS_LIMIT:  # a NaN is over it too
        lines.append(("W_EMISSION_CLOSURE", at))
    return lines
