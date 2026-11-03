# SPDX-License-Identifier: GPL-3.0-or-later
import math
import time
from dataclasses import replace

import numpy as np
import pytest
from scipy.constants import c as C_0

import kicad_lines
from kicad_rf_studio.core.cs2d import CrossSection, Rect, ShortError, pair, reference_box, solve
from kicad_rf_studio.core.geometry.mask import smeared_epsilon
from p4a import WIDE, cohn, ms_pair, stripline_pair

T_M, EPS_M = 0.010, 3.3  # the mask defaults (spec 5.3)
DZ0 = 0.025  # mm: dz0 = max(t_m, min(d/3, h/4)) at d = 0.15 mm / 2 (spec 5.4)


def ms_cs(w, h, t, er, fill_all=False):
    """A microstrip `w` wide on `h` of εr `er` over a ground plane, copper `t` thick, in its reference box;
    `fill_all` fills the whole box with the dielectric."""
    cond = (Rect(-w / 2, w / 2, h, h + t, role="signal"), Rect(-WIDE, WIDE, -t, 0, role="ground"))
    box = reference_box(cond, h)
    return CrossSection(cond, (Rect(-WIDE, WIDE, *(box[2:] if fill_all else (0, h)), er),), box)


def gcpw_cs(w, s, h, t, er, mask="none"):
    """A grounded CPW: a strip `w` wide, gaps `s` to the coplanar grounds, copper `t` thick, on `h` of εr `er` over a
    ground plane, in its reference box. `mask` "exact" fills the gaps over the copper and lays a T_M coat on it all
    (the Decisions' exact model); "smeared" lays the coat over DZ0 at the smeared εr instead."""
    a, b = w / 2, w / 2 + s
    cond = (Rect(-a, a, h, h + t, role="signal"), Rect(-WIDE, -b, h, h + t, role="ground"),
            Rect(b, WIDE, h, h + t, role="ground"), Rect(-WIDE, WIDE, -t, 0, role="ground"))
    diel = [Rect(-WIDE, WIDE, 0, h, er)]
    if mask != "none":
        c, e = (T_M, EPS_M) if mask == "exact" else (DZ0, smeared_epsilon(T_M, EPS_M, DZ0))
        diel += [Rect(-b, -a, h, h + t, EPS_M), Rect(a, b, h, h + t, EPS_M), Rect(-WIDE, WIDE, h + t, h + t + c, e)]
    return CrossSection(cond, tuple(diel), reference_box(cond, h))


def _fill(v, d):
    """`v` and lines between them, cells of `d` or finer (a gap of d within float noise stays one cell)."""
    v = np.unique(v)
    return np.unique(np.concatenate([np.linspace(a, b, int(np.ceil((b - a) / d - 1e-9)) + 1)
                                     for a, b in zip(v, v[1:])]))


def coarse_lines(cs, d):
    """Lines as the mesh rule puts them at cell `d` (spec 5.4): d/4 inside and 3d/4 outside each conductor's sides,
    one on each copper face, and cells of d or finer everywhere else in the box."""
    x0, x1, z0, z1 = cs.box
    xs = [e + o for r in cs.conductors
          for e, o in ((r.x0, d / 4), (r.x0, -3 * d / 4), (r.x1, -d / 4), (r.x1, 3 * d / 4)) if x0 < e < x1]
    zs = [v for r in cs.conductors for v in (r.z0, r.z1) if z0 < v < z1]
    return _fill([x0, x1, *xs], d), _fill([z0, z1, *zs], d)


def test_homogeneous_eps_eff():  # any line fully embedded in εr = 4.0
    assert solve(ms_cs(w=1.0, h=0.5, t=0.035, er=4.0, fill_all=True)).eps_eff == pytest.approx(4.0, rel=1e-3)


def test_parallel_plate():  # strip spanning the box width, open sides
    r = solve(CrossSection((Rect(0, 2, 1.0, 1.035, role="signal"), Rect(0, 2, -0.035, 0, role="ground")),
                           (Rect(0, 2, 0, 1.0, 4.0),), (0, 2, -0.035, 1.035), sides="open"))
    assert r.z0 == pytest.approx(376.730313 * 1.0 / 2 / 2.0, rel=5e-3) and r.eps_eff == pytest.approx(4.0, rel=1e-3)


# Task 7 ruling: the formulas' thickness terms drift once the copper is thick next to h or the gap. Hammerstad–Jensen
# at t/h = 0.175 reads 2.3 % high in Z0 and 2.3 % low in εeff, so that case gets 3 %. KiCad's CPWG narrows each gap by
# 1.25t/π·(1 + ln(4πw/t)), 0.089 mm of 0.15 mm here, which puts its εeff 7–10 % low and its Z0 2.4–3.4 % high: at
# 35 µm, Z0 is held to spec 9.2's 5 % budget against KiCad's calculator; on 1 µm copper, where that term is small,
# Z0 and εeff keep 3 %.
@pytest.mark.parametrize("w,h,er,tol", [(1.35, 0.76, 4.5, 0.02), (3.0, 1.5, 4.5, 0.02), (0.3, 0.2, 3.66, 0.03)])
def test_microstrip_vs_hammerstad_jensen(w, h, er, tol):
    z, e = kicad_lines.microstrip(w, h, 0.035, er)
    r = solve(ms_cs(w, h, 0.035, er))
    assert r.z0 == pytest.approx(z, rel=tol) and r.eps_eff == pytest.approx(e, rel=tol)


@pytest.mark.parametrize("w,s,h,er", [(0.6, 0.15, 0.76, 4.5), (1.0, 0.2, 1.5, 4.5)])
def test_gcpw_vs_kicad(w, s, h, er):
    z, _ = kicad_lines.cpwg(w, s, h, 0.035, er)
    assert solve(gcpw_cs(w, s, h, 0.035, er)).z0 == pytest.approx(z, rel=0.05)
    z, e = kicad_lines.cpwg(w, s, h, 0.001, er)
    r = solve(gcpw_cs(w, s, h, 0.001, er))
    assert r.z0 == pytest.approx(z, rel=0.03) and r.eps_eff == pytest.approx(e, rel=0.03)


def test_mask_lowers_z0_and_smear_matches_exact():  # 50 Ω-class GCPW
    a, b_, c = (solve(gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5, mask=m)) for m in ("none", "exact", "smeared"))
    assert -0.10 < b_.z0 / a.z0 - 1 < -0.02 and b_.eps_eff > a.eps_eff
    assert c.z0 == pytest.approx(b_.z0, rel=0.005) and c.eps_eff == pytest.approx(b_.eps_eff, rel=0.01)


def test_grid_convergence():  # given coarse lines give a different but close answer
    ref = solve(cs := gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5))
    x, z = coarse_lines(cs, d=0.075)
    assert abs(solve(cs, x, z).z0 / ref.z0 - 1) < 0.05


def test_speed():  # spec: about 0.1 s per section
    t = time.perf_counter()
    solve(gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5))
    assert time.perf_counter() - t < 1.0


def test_reference_box():
    ms = ms_cs(1.35, 0.76, 0.035, 4.5)
    assert ms.box == pytest.approx((-8.275, 8.275, -0.035, 8.395))  # 10 h past the strip, down to the plane's bottom
    cpw = (Rect(-0.3, 0.3, 0, 0.035, role="signal"), Rect(0.45, WIDE, 0, 0.035, role="ground"))
    assert reference_box(cpw, 0.5) == pytest.approx((-5.3, 5.3, -5.0, 5.035))  # no plane under it: 10 h under


def test_given_lines_are_bounded_by_the_box():  # fit2d may pass every mesh line; the box faces bound the solve
    cs = gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5)
    x, z = coarse_lines(cs, d=0.075)
    inside = solve(cs, x, z)
    assert inside != solve(cs)
    wide = solve(cs, np.concatenate([x[1:-1], [-50.0, 50.0]]), np.concatenate([z[1:-1], [-30.0, 30.0]]))
    assert wide.z0 == pytest.approx(inside.z0, rel=1e-9) and wide.eps_eff == pytest.approx(inside.eps_eff, rel=1e-9)


def test_conductors_sit_on_the_grid_edges_they_hold():  # openEMS's rule: metal on the Yee edges whose middle it holds
    x = z = np.linspace(-1, 1, 5)  # lines every 0.5 mm

    def sheet(a, b):
        return CrossSection((Rect(a, b, 0, 0, role="signal"),), (), (-1, 1, -1, 1))

    assert solve(sheet(0.2, 0.3), x, z).z0 > 0  # it holds the middle of the edge from 0 to 0.5 at z = 0
    with pytest.raises(ValueError):
        solve(sheet(0.1, 0.2), x, z)  # it holds no node and no edge middle: lost, as in the FDTD model


def test_a_node_held_by_the_signal_and_a_ground_is_a_short():  # FDTD zeroes E on both edges: the line is shorted
    cs = gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5)
    x = np.arange(-26, 27) * 0.3 + 0.05  # lines every 0.3 mm: at 0.35 the edge to the left lies in the strip and the
    z = coarse_lines(cs, d=0.075)[1]  # edge to the right in the ground
    for c in (cs, replace(cs, conductors=cs.conductors[::-1])):  # whatever the conductors' order
        with pytest.raises(ValueError, match="short"):
            solve(c, x, z)


def test_cohns_and_kirschning_jansens_coupled_lines_as_ported():  # Stage 4 design 5.11; r4's worked example
    ze, zo = cohn(0.15, 0.15, 0.5, 4.3)
    assert (round(ze, 2), round(zo, 2), round(2 * zo, 1), round((ze - zo) / (ze + zo), 3)) == (71.98, 52.01, 104.0,
                                                                                               0.161)
    assert kicad_lines.coupled_microstrip(0.15, 0.15, 0.2, 0.001, 4.3) == pytest.approx(
        (97.1232802849029, 3.249327590191874, 65.3666499716574, 2.7706356176104663), rel=1e-9)  # KiCad 9.0's formulas
    z, _ = kicad_lines.microstrip(0.15, 0.2, 0.0, 4.3)
    far = kicad_lines.coupled_microstrip(0.15, 1.4, 0.2, 0.0, 4.3)  # 7 h apart, inside the formula's range: weak
    assert far[0] == pytest.approx(z, rel=1e-2) and far[2] == pytest.approx(z, rel=1e-2)  # even +0.67 %, odd -0.87 %


def test_a_coupled_stripline_against_cohn_at_thin_copper():  # Stage 4 design 5.9, 5.11: P4-A's 0.5 %
    p = pair(stripline_pair(0.15, 0.15, 0.5, 1e-4, 4.3))
    ze, zo = cohn(0.15, 0.15, 0.5, 4.3)
    assert p.z_even == pytest.approx(ze, rel=0.005) and p.z_odd == pytest.approx(zo, rel=0.005)  # -0.26 %, -0.34 %
    assert p.eps_even == pytest.approx(4.3, rel=1e-9) and p.eps_odd == pytest.approx(4.3, rel=1e-9)  # homogeneous
    assert (p.z_diff, p.z_comm, p.k) == (2 * p.z_odd, p.z_even / 2, (p.z_even - p.z_odd) / (p.z_even + p.z_odd))
    (c11, c12), (c21, c22) = p.c
    assert c12 == c21 < 0 < c11 == c22
    for z, c in ((p.z_even, c11 + c12), (p.z_odd, c11 - c12)):  # a homogeneous line: Z = √εr / (c0·C)
        assert z * c * C_0 / math.sqrt(4.3) == pytest.approx(1, rel=1e-9)


def test_a_coupled_microstrip_against_kirschning_jansen():  # Stage 4 design 5.11: P4-A's 3 % at 1 µm
    p = pair(ms_pair(0.15, 0.15, 0.2, 0.001, 4.3))
    assert (p.z_even, p.eps_even, p.z_odd, p.eps_odd) == pytest.approx(
        kicad_lines.coupled_microstrip(0.15, 0.15, 0.2, 0.001, 4.3), rel=0.03)  # -1.32, -0.75, -0.47, -0.89 %


def test_a_pair_is_two_mirror_image_lines_that_never_share_a_node():  # Review Focus 1
    cs = ms_pair(0.15, 0.15, 0.2, 0.035, 4.3)
    p_leg, n_leg, plane = cs.conductors
    for conductors, match in (((p_leg, replace(n_leg, x1=n_leg.x1 + 0.05), plane), "mirror"),
                              ((p_leg, replace(n_leg, z1=n_leg.z1 + 0.01), plane), "mirror"),
                              ((p_leg, plane), "two signal"),
                              ((p_leg, n_leg, replace(p_leg, x0=-1.0, x1=-0.9), plane), "two signal")):
        with pytest.raises(ValueError, match=match):
            pair(replace(cs, conductors=conductors))
    with pytest.raises(ShortError):  # lines every 0.2 mm: the node at x 0 holds an edge of each leg
        pair(cs, np.array([-0.4, -0.2, 0.0, 0.2, 0.4]))
    with pytest.raises(ValueError, match="no grid edge"):  # lines that miss the N leg: a lone line, not a pair
        pair(cs, np.array([-1.0, -0.15, 0.0, 1.0]))
