# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-A, the 2D and formulas gate (Stage 4 design 5.11). Part 1: Cohn's exact coupled stripline and the cross-sections
cs2d solves for it and for Kirschning–Jansen's coupled microstrip, in mm. Task 3 adds the even/odd 4-port, and Task 9
the gate."""
import math

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
