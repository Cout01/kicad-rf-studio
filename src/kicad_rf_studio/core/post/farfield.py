# SPDX-License-Identifier: GPL-3.0-or-later
"""The far field (Stage 3 design 5.5): openEMS's transform files read with h5py; the port's powers over the recording's
window; the efficiencies and gains; and their validity flag. Never imports openEMS."""
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np

from kicad_rf_studio.core.model.parts import Z0

ETA_LIMIT = 1.02  # η_rad above it raises W_ETA_RAD (design 5.5)


@dataclass(frozen=True)
class FarField:
    """One transform's far field: f (F,) in Hz, the values stored (float32); theta (T,) and phi (P,) in degrees; p_rad
    (F,), openEMS's radiated power in W; and the directivity, linear: d_max (F,), openEMS's Dmax, and d (F, T, P)."""
    f: np.ndarray
    theta: np.ndarray
    phi: np.ndarray
    p_rad: np.ndarray
    d_max: np.ndarray
    d: np.ndarray


def read_far_field(path: Path) -> FarField:
    """The far field in the CalcNF2FF file `path`, in openEMS 0.37.0's layout: /Mesh/theta and /Mesh/phi in radians as
    float32 (returned in degrees, rounded to 1e-4), and /Mesh/r; /nf2ff's attributes Frequency, Prad and Dmax; per
    frequency n, the real (θ, φ) dataset P_rad/FD/f{n}; and d = 4π·r²·P_rad/Prad. ValueError naming the file in
    another layout: openEMS's legacy one (f0_real in E_theta/FD) or a P_rad dataset that is not (len θ, len φ). It
    reads no E dataset: plan 2 adds E_θ and E_φ with the far-field CSV."""
    # ponytail: openEMS 0.37.0's layout only; W_OPENEMS_UNTESTED warns outside 0.37.x
    with h5py.File(path, "r") as h5:
        theta, phi, r = (np.asarray(h5["Mesh"][name], dtype=float) for name in ("theta", "phi", "r"))
        nf = h5["nf2ff"]
        f, p_rad, d_max = (np.asarray(nf.attrs[name], dtype=float) for name in ("Frequency", "Prad", "Dmax"))
        legacy = "f0_real" in nf["E_theta/FD"]
        p = [nf[f"P_rad/FD/f{n}"][()] for n in range(len(f))]
    if legacy or any(q.shape != (len(theta), len(phi)) for q in p):
        raise ValueError(f"{path}: not openEMS 0.37.0's far-field layout (the legacy split, or P_rad not (θ, φ))")
    return FarField(f, np.round(np.degrees(theta), 4), np.round(np.degrees(phi), 4), p_rad, d_max,
                    4 * np.pi * r ** 2 * np.array(p) / p_rad[:, None, None])


def port_powers(t_u: np.ndarray, u: np.ndarray, t_i: np.ndarray, i: np.ndarray,
                f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(P_acc, P_inc) at `f` (Hz) of one port's 1-D records, u on t_u and i on t_i (s), each over its whole record at
    the probes' rate: the far field's window and rate, as the frequency-domain dumps accumulate to the engine's last
    step, not to the cut, at that same rate (over-sampling 4). U and I are openEMS's DFT_time2freq for a pulse, each
    on its own time axis: X(f) = 2·Δt·Σ x·exp(−j2πft), Δt = t[1] − t[0]. P_acc = ½·Re(U·I*) and P_inc =
    |U + Z0·I|²/(8·Z0), CalcPort's ½·Re(uf_inc·if_inc*) for a real Z0 (probed: equal to CalcPort within 2e-16)."""
    U, I = (2 * (t[1] - t[0]) * np.array([np.sum(x * np.exp(-2j * np.pi * fk * t)) for fk in f])
            for t, x in ((t_u, u), (t_i, i)))
    return 0.5 * np.real(U * np.conj(I)), np.abs(U + Z0 * I) ** 2 / (8 * Z0)


def efficiencies(sphere: FarField, p_acc: np.ndarray, p_inc: np.ndarray) -> dict[str, np.ndarray]:
    """The efficiencies and gains (F,) of `sphere` with port_powers' P_acc and P_inc at sphere.f, all linear (design
    5.5): eta_rad = P_rad/P_acc, eta_tot = P_rad/P_inc, gain = D_max·η_rad and realized_gain = D_max·η_tot."""
    eta_rad, eta_tot = sphere.p_rad / p_acc, sphere.p_rad / p_inc
    return {"eta_rad": eta_rad, "eta_tot": eta_tot, "gain": sphere.d_max * eta_rad,
            "realized_gain": sphere.d_max * eta_tot}


def eta_lines(f: np.ndarray, eta_rad: np.ndarray) -> list[tuple[str, dict]]:
    """One W_ETA_RAD line at the largest η_rad on `f` (Hz) when it is above ETA_LIMIT (design 5.5): the far field
    then radiates more power than the port accepts. No line otherwise; a non-finite η_rad counts as the largest."""
    k = int(np.argmax(np.where(np.isfinite(eta_rad), eta_rad, np.inf)))  # a NaN or inf balance is the worst
    flag = ("W_ETA_RAD", {"eta": f"{eta_rad[k]:.3f}", "f_mhz": f"{f[k] / 1e6:.1f}", "limit": f"{ETA_LIMIT:g}"})
    return [flag] if not eta_rad[k] <= ETA_LIMIT else []
