# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-A, the 2D and formulas gate (Stage 4 design 5.11). Part 1, the reference models: Cohn's exact coupled stripline,
the cross-sections cs2d solves for it and for Kirschning–Jansen's coupled microstrip, in mm, and the even/odd 4-port of
a uniform coupled pair (even_odd_s). Part 2: the gate. measure() checks cs2d's pair against REFS (Cohn at 0.1 µm;
Kirschning–Jansen at 1 µm, and at 35 µm on 1.0 and 1.5 mm substrates; the fixtures' 0.2 mm stack recorded at 18 and
35 µm), the even/odd 4-port's identities and the TDR on an ideal line; tests/test_p4a.py runs it in CI.

Dev-time: `python tools/p4a.py --out DIR` writes p4a.json and p4a.md in DIR/p4a for docs/validation/."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.constants import c as C_0
from scipy.special import ellipk

import p0
from kicad_rf_studio.core.cs2d import CrossSection, Rect, pair, reference_box
from kicad_rf_studio.core.post.si import LOCAL_RISE, tdr, uniform_grid

WIDE = 1e3  # mm: planes run past any box; the solver keeps what lies in it
REFS = json.loads((p0.FIX / "p4a" / "references.json").read_text(encoding="utf-8"))  # committed, never regenerated
COLS = ["check", "case", "quantity", "reference", "measured", "error", "limit", "pass"]  # a row's keys, in order
TDR_LIMIT = 0.05  # Ω: the design's "60.0 then 50.0 Ω", to one decimal


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


def measure() -> dict:
    """P4-A's 50 rows against REFS, in order, each a dict of COLS whose pass is None where the row is recorded, never
    gated, and the verdict, "fail" when any row's pass is False:
    - cohn, kj_1um, kj_35um and kj_recorded: cs2d's pair of stripline_pair or ms_pair at the case's own t_mm, else its
      group's; the error measured/reference − 1, passing at |error| ≤ the group's limit; kj_35um's εeff recorded;
    - identity: the even/odd 4-port of the first Cohn case's modes at z_ref √(Ze·Zo) (FEXT, S11, NEXT's peak at the
      quarter wave), and REFS["tdr"]'s line uncoupled against its step's bounce series; the error |measured −
      reference|, passing at ≤ its limit;
    - tdr: that line's TDR at τ, and its Z farthest from z_ref from 4τ + 4·t_r to 20 ns; the error measured −
      reference, passing at |error| < TDR_LIMIT."""
    rows = []

    def add(check: str, case: str, quantity: str, reference: float, measured, error, limit: float | None,
            strict: bool = False) -> None:  # floats, so that pass is a bool or None
        measured, error = float(measured), float(error)
        passed = None if limit is None else abs(error) < limit if strict else abs(error) <= limit
        rows.append(dict(zip(COLS, (check, case, quantity, reference, measured, error, limit, passed))))

    def text(c: dict) -> str:  # a case's geometry, its own t_mm as t: "w 0.15 s 0.15 b 0.5 er 4.3"
        return " ".join(f"{k.removesuffix('_mm')} {v}" for k, v in c.items() if not k.startswith(("z_", "eps_")))

    for key, cross_section in (("cohn", stripline_pair), ("kj_1um", ms_pair), ("kj_35um", ms_pair),
                               ("kj_recorded", ms_pair)):
        group = REFS[key]
        for c in group["cases"]:
            p = pair(cross_section(c["w"], c["s"], c.get("b", c.get("h")), c.get("t_mm", group["t_mm"]), c["er"]))
            for q in ("z_even", "eps_even", "z_odd", "eps_odd"):
                if q in c:  # Cohn's cases hold no εeff
                    limit = None if key == "kj_35um" and q.startswith("eps") else group["limit"]
                    add(key, text(c), q, c[q], getattr(p, q), getattr(p, q) / c[q] - 1, limit)
    first, length, limit = REFS["cohn"]["cases"][0], REFS["identity"]["length_mm"], REFS["identity"]["limit"]
    ze, zo, er = first["z_even"], first["z_odd"], first["er"]
    f_q = C_0 / (4 * length / 1e3 * math.sqrt(er))  # the quarter wave
    s = even_odd_s(ze, er, zo, er, length, np.r_[np.linspace(0, 3 * f_q, 301), f_q], math.sqrt(ze * zo))
    for q, reference, measured in (("fext", 0.0, np.abs(s[:, 3, 0]).max()), ("s11", 0.0, np.abs(s[:, 0, 0]).max()),
                                   ("next_peak", (ze - zo) / (ze + zo), abs(s[-1, 1, 0]))):
        add("identity", f"{text(first)} l {length}", q, reference, measured, abs(measured - reference), limit)
    line = REFS["tdr"]
    z_line, eps, z_ref, f_max = line["z_line"], line["eps"], line["z_ref"], line["f_max_hz"]
    tau, gamma = line["length_mm"] / 1e3 * math.sqrt(eps) / C_0, (z_line - z_ref) / (z_line + z_ref)  # one way; Γ
    case = f"z {z_line} eps {eps} l {line['length_mm']}"

    def s11(f: np.ndarray) -> np.ndarray:  # the line in both modes, uncoupled
        return even_odd_s(z_line, eps, z_line, eps, line["length_mm"], f, z_ref)[:, 0, 0]

    f = np.linspace(0, f_max, 401)
    x = np.exp(-4j * np.pi * f * tau)  # e^(−2jθ), θ = 2πfτ
    bounce = np.abs(s11(f) - gamma * (1 - x) / (1 - gamma ** 2 * x)).max()
    add("identity", case, "bounce", 0.0, bounce, bounce, limit)
    f, t_r = uniform_grid(f_max), LOCAL_RISE / f_max
    t, z = tdr(s11(f), f, t_r, z_ref)
    late = z[(t >= 4 * tau + 4 * t_r) & (t <= 20e-9)]  # past the second round trip, as in tests/test_post_si.py
    for q, reference, measured in (("plateau", z_line, np.interp(tau, t, z)),
                                   ("late", z_ref, late[np.argmax(np.abs(late - z_ref))])):
        add("tdr", case, q, reference, measured, measured - reference, TDR_LIMIT, strict=True)
    return {"rows": rows, "verdict": "fail" if any(r["pass"] is False for r in rows) else "pass"}


def main(argv: list[str] | None = None) -> int:
    """python tools/p4a.py --out DIR: measure(), timed, into DIR/p4a/p4a.json through p0.save with the versions and
    REFS, and its rows as a table in p4a.md beside it. Returns 0 for a pass, else 1."""
    parser = argparse.ArgumentParser(prog="p4a", description="P4-A, the 2D and formulas gate (Stage 4 design 5.11).")
    parser.add_argument("--out", required=True, help="the folder p4a/ is written in, outside every git work tree")
    out = Path(parser.parse_args(argv).out) / "p4a"
    t0 = time.perf_counter()
    m = measure()
    wall_s = time.perf_counter() - t0
    p0.save(out / "p4a.json", {"gate": "P4-A", "versions": p0.versions(), "references": REFS, "wall_s": wall_s, **m})
    (out / "p4a.md").write_text("## P4A-1 Checks\n\n" + p0.table(m["rows"], COLS) + "\n", encoding="utf-8")
    return 0 if m["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
