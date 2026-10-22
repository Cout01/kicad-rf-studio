# SPDX-License-Identifier: GPL-3.0-or-later
"""The parts of the chain on the co-simulation grid (spec 5.7, 7.2): each part port's Z_part, from its value and
package preset or from its S2P file."""
from pathlib import Path

import numpy as np
import skrf as rf

from kicad_rf_studio.core.kicad.values import part_kind, port_value
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import parts


def z_part(kind: str, value: float, model: dict | None, f: np.ndarray) -> np.ndarray:
    """Z_part (F,) on f of a C, L or R of `value` (F, H or Ω) with its preset's esl_h, esr_ohm and cp_f, all 0 for no
    `model` (C-13, spec 5.7): C: ESR + jωESL + 1/(jωC); L: (ESR + jωL) ∥ 1/(jωCp); R: (R + jωESL) ∥ 1/(jωCp)."""
    esl, esr, cp = (model["esl_h"], model["esr_ohm"], model["cp_f"]) if model else (0.0, 0.0, 0.0)
    w = 2 * np.pi * f
    if kind == "C":
        return esr + 1j * w * esl + 1 / (1j * w * value)
    zs = esr + 1j * w * value if kind == "L" else value + 1j * w * esl
    return zs / (1 + 1j * w * cp * zs)  # zs ∥ 1/(jωCp), finite at zs = 0


def s2p_impedance(file: Path, connection: str, ref: str, f: np.ndarray) -> tuple[np.ndarray, str | None]:
    """Z_part (F,) on f of the part `ref` from its Touchstone 2-port `file`, measured in a "series" or "shunt" thru
    fixture (`connection`; C-14): series 2·Z0·(1 − S21)/S21, shunt Z0·S21/(2·(1 − S21)), with S21 the mean of S21 and
    S12 interpolated linearly on its real and imaginary parts (never Z, never extrapolated), Z0 the file's R and its
    noise data ignored. With it, the other connection when the file's own points from f[0] to f[-1] fit that
    fixture's identity better (series S11 + S21 = 1, shunt S21 − S11 = 1), else None. Refusals, each naming ref and
    path: E_S2P_MISSING, E_S2P_UNREADABLE (a reader error, or no data), E_S2P_PORTS, E_S2P_BAND (the file must span
    f[0] to f[-1])."""
    named = {"ref": ref, "path": str(file)}
    if not file.exists():
        raise KrsError("E_S2P_MISSING", **named)
    n = rf.Network()  # never rf.Network(file), which unpickles
    try:
        n.read_touchstone(str(file))
    except Exception:  # a parser of user input: whatever it raises, the file cannot be read
        raise KrsError("E_S2P_UNREADABLE", **named) from None
    if not len(n.f):
        raise KrsError("E_S2P_UNREADABLE", **named)
    if n.nports != 2:
        raise KrsError("E_S2P_PORTS", **named, ports=n.nports)
    if n.f[0] > f[0] or n.f[-1] < f[-1]:
        raise KrsError("E_S2P_BAND", **named, f_lo=f"{n.f[0] / 1e6:.1f}", f_hi=f"{n.f[-1] / 1e6:.1f}",
                       f1=f"{f[0] / 1e6:.1f}", f2=f"{f[-1] / 1e6:.1f}")
    s11, s21 = n.s[:, 0, 0], (n.s[:, 1, 0] + n.s[:, 0, 1]) / 2
    band = (n.f >= f[0]) & (n.f <= f[-1])
    miss = {"series": np.abs(s11 + s21 - 1)[band].max(initial=0.0),
            "shunt": np.abs(s21 - s11 - 1)[band].max(initial=0.0)}  # 0 for both when no point lies in the band
    other = "shunt" if connection == "series" else "series"
    s21_grid = np.interp(f, n.f, s21.real) + 1j * np.interp(f, n.f, s21.imag)
    z0 = n.z0[0, 0].real
    z = 2 * z0 * (1 - s21_grid) / s21_grid if connection == "series" else z0 * s21_grid / (2 * (1 - s21_grid))
    return z, other if miss[other] < miss[connection] else None


def part_impedances(project: dict, folder: Path, refs: list[str], f: np.ndarray
                    ) -> tuple[dict[str, np.ndarray], list[tuple[str, dict]]]:
    """Z_part (F,) on f of each part in `refs` (C-13..C-15, spec 7.2): from its s2p file, read at folder / file
    (folder: project.json's), when it names one, else z_part of its kind, port_value and model; and W_S2P_FIXTURE for
    each file that fits the other fixture. Raises E_PART_NO_VALUE for a part with neither a file nor a port_value, and
    s2p_impedance's refusals."""
    by_ref, z, notes = parts(project), {}, []
    for ref in refs:
        part = by_ref[ref]
        if s2p := part["s2p"]:
            file = (folder / s2p["file"]).resolve()
            z[ref], fits = s2p_impedance(file, s2p["connection"], ref, f)
            if fits:
                notes.append(("W_S2P_FIXTURE", {"ref": ref, "path": str(file), "named": s2p["connection"],
                                                "fits": fits}))
        else:
            value = port_value(ref, part["value"])
            if value is None:
                raise KrsError("E_PART_NO_VALUE", ref=ref, value=part["value"])
            z[ref] = z_part(part_kind(ref), value, part["model"], f)
    return z, notes
