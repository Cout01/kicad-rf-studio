# SPDX-License-Identifier: GPL-3.0-or-later
"""KiCad 9's line-calculator formulas, for the tests: Z0 (Ω) and εeff of a microstrip and of a coplanar waveguide with
a ground plane under it, and the even and odd modes of an edge-coupled microstrip, quasi-static (f → 0, where the
dispersion terms vanish), lengths in mm.

Ported from KiCad's 9.0 branch (https://gitlab.com/kicad/code/kicad, branch 9.0 at ce707d0a, 2026-05-14):
- pcb_calculator/transline/microstrip.cpp: MICROSTRIP::microstrip_Z0 and the helpers it calls;
- pcb_calculator/transline/c_microstrip.cpp (branch 9.0, read on 2026-11-02): C_MICROSTRIP::delta_u_thickness,
  filling_factor_even, filling_factor_odd, er_eff_static and Z0_even_odd, quasi-static and with no cover (every cover
  term vanishes past its range), with compute_single_line's zero-thickness single line;
- pcb_calculator/transline/coplanar.cpp: COPLANAR::calcAnalyze with backMetal (GROUNDEDCOPLANAR);
- pcb_calculator/transline/transline.cpp: TRANSLINE::ellipk and TRANSLINE::ellipke;
- pcb_calculator/transline/units.h: ZF0.
Those files are GPL-2.0-or-later, used here under GPL-3.0-or-later. Copyright (C) 2001 Gopal Narayanan, 2002 Claudio
Girardi, 2005-2006 Stefan Jahn, 2008 Michael Margraf; modified for KiCad by Jean-Pierre Charras; Copyright The KiCad
Developers."""
from __future__ import annotations

import math

from scipy.special import ellipk

ZF0 = 376.730313668  # Ω, the wave impedance of vacuum (units.h)


def _q(k: float) -> float:
    """ellipk(k) / ellipk(√(1 − k²)) as coplanar.cpp takes it. KiCad's ellipk(k) hands k to an AGM (ellipke) that
    takes the parameter m = k², so it returns K(m = k), not K of modulus k; the port keeps that, since KiCad's own
    values need it (with K of modulus k, its 0.6 / 0.15 mm GCPW reads 1.4 % higher in Z0)."""
    return float(ellipk(k) / ellipk(math.sqrt(1 - k * k)))


def _z0_homogeneous(u: float) -> float:
    """Z0 of a strip of width/height `u` in vacuum, without cover (Z0_homogeneous)."""
    f = 6.0 + (2.0 * math.pi - 6.0) * math.exp(-((30.666 / u) ** 0.7528))
    return ZF0 / (2.0 * math.pi) * math.log(f / u + math.sqrt(1.0 + 4.0 / (u * u)))


def _delta_u_thickness(u: float, t_h: float, e_r: float) -> float:
    """The width/height a strip `t_h` thick (over height) adds, on a substrate of εr `e_r` (delta_u_thickness)."""
    if t_h <= 0.0:
        return 0.0
    d = t_h / math.pi * math.log(1.0 + 4.0 * math.e * math.tanh(math.sqrt(6.517 * u)) ** 2 / t_h)
    return 0.5 * d * (1.0 + 1.0 / math.cosh(math.sqrt(e_r - 1.0)))


def microstrip(w: float, h: float, t: float, er: float, ht: float = 1e20) -> tuple[float, float]:
    """Z0 (Ω) and εeff of a microstrip `w` wide and `t` thick on `h` of εr `er`, under a cover `ht` above the ground
    plane (KiCad's H(top); 1e20, KiCad's own default, is no cover). Raises ValueError for a cover at or under the
    substrate's top, where the cover factor has no meaning."""
    if ht <= h:
        raise ValueError(f"the cover must lie above the substrate: ht = {ht} mm, h = {h} mm")
    u, t_h, h2h = w / h, t / h, ht / h
    z_h1 = _z0_homogeneous(u + _delta_u_thickness(u, t_h, 1.0))
    u += _delta_u_thickness(u, t_h, er)
    z_hr = _z0_homogeneous(u)
    a = 1.0 + math.log((u**4 + u**2 / 2704) / (u**4 + 0.432)) / 49.0 + math.log(1.0 + u**3 / 5929.741) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3.0)) ** 0.053
    q_inf = (1.0 + 10.0 / u) ** (-a * b)  # filling factor
    q_t = 2.0 * math.log(2.0) / math.pi * t_h / math.sqrt(u)  # thickness effect
    q_c = math.tanh(1.043 + 0.121 * h2h - 1.164 / h2h)  # cover effect
    e_t = 0.5 * (er + 1.0) + 0.5 * (q_inf - q_t) * q_c * (er - 1.0)
    return z_hr / math.sqrt(e_t), e_t * (z_h1 / z_hr) ** 2


def coupled_microstrip(w: float, s: float, h: float, t: float, er: float) -> tuple[float, float, float, float]:
    """Zeven (Ω), εeven, Zodd (Ω) and εodd of an edge-coupled microstrip with no cover: two strips `w` wide, `s` apart
    and `t` thick on `h` of εr `er` (Kirschning and Jansen, IEEE Trans. MTT 32(1), 1984, with Jansen's 1978 thickness
    terms), as KiCad 9's c_microstrip.cpp computes them at f → 0."""
    u, g, t_h = w / h, s / h, t / h
    du_e = du_o = 0.0
    if t_h > 0:  # delta_u_thickness
        du = 1.25 * t_h / math.pi * (1 + math.log(
            (2 + (4 * math.pi * u - 2) / (1 + math.exp(-100 * (u - 1 / (2 * math.pi))))) / t_h))
        dt = t_h / (g * er)
        du_e = du * (1 - 0.5 * math.exp(-0.69 * du / dt))
        du_o = du_e + dt
    ue, uo = u + du_e, u + du_o
    z1, e1 = microstrip(w, h, 0.0, er)  # compute_single_line: zero thickness, no cover
    q_t = 2 * math.log(2) / math.pi * t_h  # delta_q_thickness × √u
    v = ue * (20 + g * g) / (10 + g * g) + g * math.exp(-g)  # filling_factor_even
    a_e = 1 + math.log((v ** 4 + v * v / 2704) / (v ** 4 + 0.432)) / 49 + math.log(1 + v ** 3 / 5929.741) / 18.7
    b_e = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    e_e = 0.5 * (er + 1) + 0.5 * (er - 1) * ((1 + 10 / v) ** (-a_e * b_e) - q_t / math.sqrt(ue))
    b_o = 0.747 * er / (0.15 + er)  # filling_factor_odd
    c_o = b_o - (b_o - 0.207) * math.exp(-0.414 * uo)
    d_o = 0.593 + 0.694 * math.exp(-0.562 * uo)
    a_o = 0.7287 * (e1 - 0.5 * (er + 1)) * (1 - math.exp(-0.179 * uo))
    e_o = (0.5 * (er + 1) + a_o - e1) * (math.exp(-c_o * g ** d_o) - q_t / math.sqrt(uo)) + e1
    q1 = 0.8695 * ue ** 0.194  # Z0_even_odd
    q2 = 1 + 0.7519 * g + 0.189 * g ** 2.31
    q3 = 0.1975 + (16.6 + (8.4 / g) ** 6) ** -0.387 + math.log(g ** 10 / (1 + (g / 3.4) ** 10)) / 241
    q4 = 2 * q1 / (q2 * (math.exp(-g) * ue ** q3 + (2 - math.exp(-g)) * ue ** -q3))
    q5 = 1.794 + 1.14 * math.log(1 + 0.638 / (g + 0.517 * g ** 2.43))
    q6 = 0.2305 + math.log(g ** 10 / (1 + (g / 5.8) ** 10)) / 281.3 + math.log(1 + 0.598 * g ** 1.154) / 5.1
    q7 = (10 + 190 * g * g) / (1 + 82.3 * g ** 3)
    q8 = math.exp(-6.5 - 0.95 * math.log(g) - (g / 0.15) ** 5)
    q9 = math.log(q7) * (q8 + 1 / 16.5)
    q10 = (q2 * q4 - q5 * math.exp(math.log(uo) * q6 * uo ** -q9)) / q2
    z_e = z1 * math.sqrt(e1 / e_e) / (1 - math.sqrt(e1) * q4 * z1 / ZF0)
    z_o = z1 * math.sqrt(e1 / e_o) / (1 - math.sqrt(e1) * q10 * z1 / ZF0)
    return z_e, e_e, z_o, e_o


def cpwg(w: float, s: float, h: float, t: float, er: float) -> tuple[float, float]:
    """Z0 (Ω) and εeff of a coplanar waveguide with a ground plane under it: a strip `w` wide, gaps `s` to the coplanar
    grounds, all `t` thick, on `h` of εr `er`."""
    q1 = _q(w / (w + s + s))
    q3 = _q(math.tanh(math.pi / 4 * w / h) / math.tanh(math.pi / 4 * (w + s + s) / h))
    qz = 1 / (q1 + q3)
    er0 = 1 + q3 * qz * (er - 1)
    if t > 0:  # the strip's thickness widens it and narrows the gaps
        d = t * 1.25 / math.pi * (1 + math.log(4 * math.pi * w / t))
        qz = 1 / (_q((w + d) / (w + d + 2 * (s - d))) + q3)
        er0 = 1 + q3 * qz * (er - 1)
        er0 -= 0.7 * (er0 - 1) * t / s / (q1 + 0.7 * t / s)
    return ZF0 / 2 * qz / math.sqrt(er0), er0
