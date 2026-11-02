# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-A, the 2D and formulas gate (Stage 4 design 5.11). Part 1, the reference models: Cohn's exact coupled stripline,
the cross-sections cs2d solves for it and for Kirschning–Jansen's coupled microstrip, in mm, and the even/odd 4-port of
a uniform coupled pair (even_odd_s). Task 9 adds the gate."""
import math

import numpy as np
from scipy.constants import c as C_0
from scipy.special import ellipk

from kicad_rf_studio.core.cs2d import CrossSection, Rect, reference_box

WIDE = 1e3  # mm: planes run past any box; the solver keeps what lies in it


def cohn(w: float, s: float, b: float, er: float) -> tuple[float, float]:
    """Zeven and Zodd (Ω) of Cohn's exact zero-thickness edge-coupled stripline (S. B. Cohn, IRE Trans. MTT 3(5), 1955):
    two strips `w` wide and `s` apart, centred between ground planes `b` apart, in εr `er`."""
    def ratio(k: float) -> float:  # K(k')/K(k) of modulus k; scipy's ellipk takes the parameter m = k²
        return float(ellipk(1 - k * k) / ellipk(k * k))

    a, c = math.tanh(math.pi * w / (2 * b)), math.tanh(math.pi * (w + s) / (2 * b))
    return 30 * math.pi / math.sqrt(er) * ratio(a * c), 30 * math.pi / math.sqrt(er) * ratio(a / c)


def stripline_pair(w: float, s: float, b: float, t: float, er: float) -> CrossSection:
    """Two strips `w` wide, `s` apart and `t` thick, centred between 35 µm planes `b` apart in εr `er`, the P leg first;
    the box spans the planes and 10·b past the strips."""
    z = b / 2
    legs = (Rect(-s / 2 - w, -s / 2, z - t / 2, z + t / 2, role="signal"),
            Rect(s / 2, s / 2 + w, z - t / 2, z + t / 2, role="signal"))
    planes = (Rect(-WIDE, WIDE, -0.035, 0, role="ground"), Rect(-WIDE, WIDE, b, b + 0.035, role="ground"))
    box = (round(-s / 2 - w - 10 * b, 6), round(s / 2 + w + 10 * b, 6), -0.035, round(b + 0.035, 6))
    return CrossSection(legs + planes, (Rect(-WIDE, WIDE, 0, b, er),), box)


def ms_pair(w: float, s: float, h: float, t: float, er: float) -> CrossSection:
    """Two strips `w` wide, `s` apart and `t` thick on `h` of εr `er` over a plane `t` thick, the P leg first, in their
    reference box (cs2d.reference_box)."""
    conductors = (Rect(-s / 2 - w, -s / 2, h, h + t, role="signal"), Rect(s / 2, s / 2 + w, h, h + t, role="signal"),
                  Rect(-WIDE, WIDE, -t, 0, role="ground"))
    return CrossSection(conductors, (Rect(-WIDE, WIDE, 0, h, er),), reference_box(conductors, h))


def even_odd_s(z_even: float, eps_even: float, z_odd: float, eps_odd: float, length_mm: float, f: np.ndarray,
               z_ref: float = 50.0) -> np.ndarray:
    """S (F, 4, 4) on `f` (Hz) of a uniform coupled pair `length_mm` long, from its even and odd modes' Z (Ω) and εeff,
    its ports [P near, N near, P far, N far] at `z_ref` (Ω). Each mode is a line of its Z and electrical length between
    z_ref ports, which is exact for a lossless quasi-TEM pair (r4). P4-A's and P4-B's reference, which no product code
    reads."""
    def mode(z_m: float, eps_m: float) -> tuple[np.ndarray, np.ndarray]:  # the mode's Γ and T
        th = 2 * np.pi * f * (length_mm / 1e3) * math.sqrt(eps_m) / C_0
        z = z_m / z_ref
        den = 2 * np.cos(th) + 1j * (z + 1 / z) * np.sin(th)
        return 1j * (z - 1 / z) * np.sin(th) / den, 2 / den

    (g_e, t_e), (g_o, t_o) = mode(z_even, eps_even), mode(z_odd, eps_odd)
    a, b, c, d = (g_e + g_o) / 2, (g_e - g_o) / 2, (t_e + t_o) / 2, (t_e - t_o) / 2  # b NEXT, c the thru, d FEXT
    return np.array([[a, b, c, d], [b, a, d, c], [c, d, a, b], [d, c, b, a]]).transpose(2, 0, 1)
