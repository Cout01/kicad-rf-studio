# SPDX-License-Identifier: GPL-3.0-or-later
"""Signal integrity's readings (Stage 4 design 5.1, 5.5, 5.6): the uniform grid from DC, the Gaussian rise filter and
the TDR's step response from S; mixed mode at the target; the TDT's arrival, the levels between the launches and the
skew; Hammerstad's conductor loss, for the route's loss estimate; and, from later tasks, the lines, files, verify's
comparison and compare's deltas. At module level it imports only the stdlib, numpy and core.messages: core.project
imports it for LOCAL_RISE, so scipy, scikit-rf, matplotlib, core.model.parts and core.post.antenna are imported inside
the functions that use them (C-5)."""
import csv
import io
import math
import re
import warnings
from dataclasses import dataclass

import numpy as np

from kicad_rf_studio.core.messages import render

# ponytail: a response longer than the 200 ns record wraps (an SI load holds its first point above DC at DC, so a
# series C's time constant never enters it), and Z = z_ref(1 + ρ)/(1 − ρ) has no bound as ρ → 1 (an open; draw_si
# clips its axis); P4-C or P4-D sets another N_TDR if a coupon needs one
N_TDR = 2000  # points above DC: 5 MHz apart at 10 GHz, a 200 ns record
PAD = 8  # the inverse FFT's zero padding
LEAD = 4.0  # rise times before t = 0 where the step's sum starts
# the localising TDR's rise time is LOCAL_RISE/f_max, where the filter is near −40 dB at f_max (design 5.1)
LOCAL_RISE = 1.25


def uniform_grid(f_max: float, n: int = N_TDR) -> np.ndarray:
    """The TDR's grid: `n` + 1 points from DC to `f_max` (Hz)."""
    return np.linspace(0.0, f_max, n + 1)


def rise_filter(f: np.ndarray, t_r: float) -> np.ndarray:
    """H(f) = exp(−2π²σ²f²) on `f` (Hz), σ = t_r/2.563: a Gaussian whose step rises 10–90 % in `t_r` (s)."""
    return np.exp(-2 * (math.pi * t_r / 2.563 * f) ** 2)


def step_response(s: np.ndarray, f: np.ndarray, t_r: float) -> tuple[np.ndarray, np.ndarray]:
    """The step response ρ(t) of S `s` (F,) on `f`, a uniform grid from DC (uniform_grid), through rise_filter at the
    10–90 % rise time `t_r` (s): the inverse FFT of the filtered S, zero-padded PAD times, summed from LEAD rise times
    before t = 0, since the filter's impulse is centred on t = 0 and a sum started there reads half the step (r1).
    ValueError for any other grid."""
    f = np.asarray(f, float)
    if f[0] != 0 or not np.allclose(np.diff(f), f[1] - f[0], rtol=1e-9, atol=0):
        raise ValueError("the TDR needs a uniform grid from DC")
    m = PAD * (len(f) - 1)
    spec = np.zeros(m + 1, complex)
    spec[:len(f)] = s * rise_filter(f, t_r)
    h = np.fft.irfft(spec)  # the filtered impulse response, a sample every dt
    dt = 1 / (2 * m * (f[1] - f[0]))
    k = math.ceil(LEAD * t_r / dt)
    return (np.arange(len(h)) - k) * dt, np.cumsum(np.roll(h, k))


def tdr(s11: np.ndarray, f: np.ndarray, t_r: float, z_ref: float = 50.0) -> tuple[np.ndarray, np.ndarray]:
    """The TDR of the reflection `s11` (F,) on `f` at the rise time `t_r` (s), as step_response takes them: (t in s,
    Z in Ω), Z = z_ref(1 + ρ)/(1 − ρ)."""
    t, rho = step_response(s11, f, t_r)
    return t, z_ref * (1 + rho) / (1 - rho)


# design 5.8: the significance of a differential and a single-ended TDR level; a level that close to the target marks
# no feature
DIFF_OHM, SE_OHM = 1.0, 0.5
ARRIVAL_FLOOR = 1e-3  # a TDT whose peak stays under this has no arrival: nothing passes the line
FLOOR_DB = -300.0  # the level in dB an exact zero reads as: an ideal pair's Scd21, crosstalk at DC
Level = tuple[float, float, bool]  # (t in s, Z in Ω, short)


def db(x: np.ndarray) -> np.ndarray:
    """|x| in dB, floored at FLOOR_DB, so an exact zero reads as that, never −inf with a warning."""
    with np.errstate(divide="ignore"):
        return np.maximum(20 * np.log10(np.abs(x)), FLOOR_DB)


def distance_mm(t, eeff: float):
    """The distance along the route, in mm, of the round-trip time `t` (s) at `eeff`: t·c/(2·√eeff); of a rise time,
    its resolution length t_r·v/2 (design 5.6)."""
    from scipy.constants import c  # here only (C-5)

    # ponytail: one 2D εeff for the whole route, the measured line's length-weighted one: a pad, a via or a neck of
    # another εeff, or a pair's odd mode a few % faster, sits a few % off along this axis; a per-section axis if a gate
    # needs it
    return t * c / (2 * math.sqrt(eeff)) * 1e3


COPPER_RHO = 1.72e-8  # Ω·m, KiCad's calculator's 5.8e7 S/m


def hammerstad(f: float, w_mm: float, z0: float) -> float:
    """Hammerstad and Jensen's conductor attenuation in Np/m of a microstrip `w_mm` wide of impedance `z0` (Ω) at `f`
    (Hz), smooth copper (roughness factor 1), as scikit-rf's MLine.analyse_loss: R_s/(z0·w)·K_i,
    R_s = √(π·f·μ0·COPPER_RHO), K_i = exp(−1.2·(z0/η0)^0.7), μ0 and η0 = √(μ0/ε0) from scipy.constants, imported
    inside (C-5)."""
    from scipy.constants import epsilon_0, mu_0  # here only (C-5)

    # ponytail: a microstrip formula, valid where the copper is 3 skin depths thick or more (25 µm at 62.5 MHz); an
    # inner-layer section's conductor loss is a microstrip estimate, and a thinner copper or a lower marker reads it low
    r_s = math.sqrt(math.pi * f * mu_0 * COPPER_RHO)
    return r_s / (z0 * w_mm * 1e-3) * math.exp(-1.2 * (z0 / math.sqrt(mu_0 / epsilon_0)) ** 0.7)


def mixed_mode(s: np.ndarray, f: np.ndarray, target: float, paired: bool) -> np.ndarray:
    """S (F, N, N) at Z0 on every port, ports in project.json's order, renormalised to the target (Stage 4 design 5.5;
    Stage 1 7.7: s_def "power" passed explicitly, the impedances real, so every definition agrees): a pair's [P start,
    N start, P end, N end] through scikit-rf's Network.se2gmm(p=2) to [d0, d1, c0, c1], `target` the differential
    reference and target/4 the common one; a net's start and end renormalised to `target` (Network.renormalize, one
    impedance a port); a victim's ends stay at Z0."""
    import skrf as rf  # here only (C-5)

    from kicad_rf_studio.core.model.parts import Z0

    # ponytail: the common reference is target/4, the uncoupled pair's; a measured Zcomm if P4-B needs it
    network = rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s.copy(), z0=Z0, s_def="power")
    if paired:
        network.se2gmm(p=2, z0_mm=np.array([target, target, target / 4, target / 4]), s_def="power")
    else:
        network.renormalize([target, target] + [Z0] * (s.shape[1] - 2), s_def="power")
    return network.s


def arrival(t: np.ndarray, step: np.ndarray) -> float | None:
    """The time (s) `step`, a TDT on step_response's `t`, first reaches half its peak, interpolated linearly between
    that sample and the one before (design 5.6); None when its peak is under ARRIVAL_FLOOR: nothing passes."""
    # ponytail: step_response's sample at t sums the impulse up to t + dt/2, so an arrival reads half a sample (3.1 ps
    # at 10 GHz) early; a skew, a difference, does not
    peak = step.max()
    if peak < ARRIVAL_FLOOR:
        return None
    k = int(np.argmax(step >= peak / 2))
    return float(np.interp(peak / 2, step[k - 1:k + 1], t[k - 1:k + 1]))


def levels(t: np.ndarray, z: np.ndarray, t_r: float, t_far: float | None, target: float,
           ohm: float) -> tuple[Level, Level] | None:
    """The TDR `z` on `t`'s lowest and highest levels between the launches (design 5.6), each (t, Z, short), searched
    where t_r < t < t_far − t_r, the far port's launch at t_far; None without t_far, or with that span empty (a route
    no longer than its two launches). A level is short, on a feature under two resolution lengths and so not its
    impedance, when it lies more than `ohm` off `target` and either of two widths is under 2·t_r: its run past half
    its height from `target`, within 0 ≤ t ≤ t_far (the route between the ports, so a short route clips no level), or,
    when it stands more than `ohm` above its own base in the span (scipy.signal.peak_prominences), its width at half
    that prominence (peak_widths): a short feature on a route that is itself off the target."""
    from scipy.signal import peak_prominences, peak_widths  # here only (C-5)

    # ponytail: half-height widths from the target and from the level's own base, tuned on synthetic lines (the neck
    # and a pad, each on and off the target, a uniform mistuned route, launches of 0.3 nH); P4-F checks it on the
    # neck and the gap
    if t_far is None:
        return None
    span = np.flatnonzero((t > t_r) & (t < t_far - t_r))
    if not span.size:
        return None
    route = np.flatnonzero((t >= 0) & (t <= t_far))
    out = []
    for k in (span[np.argmin(z[span])], span[np.argmax(z[span])]):
        half, side = (z[k] + target) / 2, np.sign(z[k] - target) or 1.0
        i = j = k
        while i > route[0] and (z[i - 1] - half) * side > 0:
            i -= 1
        while j < route[-1] and (z[j + 1] - half) * side > 0:
            j += 1
        x, at = side * z[span], [k - span[0]]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # scipy's PeakPropertyWarning: an extreme at an edge
            prominence = peak_prominences(x, at)
        local = peak_widths(x, at, 0.5, prominence)[0][0] * (t[1] - t[0]) if prominence[0][0] > ohm else math.inf
        out.append((float(t[k]), float(z[k]), bool(abs(z[k] - target) > ohm and min(t[j] - t[i], local) < 2 * t_r)))
    return out[0], out[1]


@dataclass(frozen=True)
class Reading:
    """A chain's SI reading (Stage 4 design 5.6): `f` (Hz, the uniform grid from DC); `s` (F, P, P), the chain at Z0;
    `m`, mixed_mode's; `marker`, the grid index nearest marker_hz; `rise`, (LOCAL_RISE/f_max_hz, rise_s); `t` and `z`,
    the localising TDR of m[:, 0, 0] at the target; `z_link`, the link's, on the same `t`; `tdt` and `tdt_link`, the
    step of m[:, 1, 0] at each rise time, on the same `t`; `t_far`, twice arrival(t, tdt), None without one; `levels`;
    `skew`, a pair's legs' arrivals (P, N), None for a net or when either has none; `xt`, per victim in port order,
    (NEXT's peak dB, its Hz, FEXT's peak dB, its Hz); `eeff`, the distance axis's 2D εeff."""
    f: np.ndarray
    s: np.ndarray
    m: np.ndarray
    marker: int
    rise: tuple[float, float]
    t: np.ndarray
    z: np.ndarray
    z_link: np.ndarray
    tdt: np.ndarray
    tdt_link: np.ndarray
    t_far: float | None
    levels: tuple[Level, Level] | None
    skew: tuple[float, float] | None
    xt: list[tuple[float, float, float, float]]
    eeff: float


def read(s: np.ndarray, f: np.ndarray, project: dict, eeff: float) -> Reading:
    """The Reading of the chain `s` (F, P, P) at Z0 on `f`, the uniform grid from DC, for the SI project dict
    `project`, its distances at the 2D εeff `eeff`. It takes the chain, never the layout, so the part ports are closed
    (Stage 4 design 5.6)."""
    # ponytail: NEXT at a victim's first-named end and FEXT at its second, so --victim names the end nearer the
    # measured line's start first; a pick by geometry if users swap them
    paired, target = project["pair"] is not None, project["target_ohm"]
    m = mixed_mode(s, f, target, paired)
    rise = (LOCAL_RISE / project["f_max_hz"], project["rise_s"])
    t, z = tdr(m[:, 0, 0], f, rise[0], target)
    tdt = step_response(m[:, 1, 0], f, rise[0])[1]
    first = arrival(t, tdt)
    t_far = None if first is None else 2 * first
    skew = None
    if paired:
        p, n = (arrival(*step_response(s[:, i, j], f, rise[0])) for i, j in ((2, 0), (3, 1)))
        skew = None if p is None or n is None else (p, n)

    def peak(x: np.ndarray) -> tuple[float, float]:  # |x|'s highest point: (dB, Hz)
        d = db(x)
        return float(d.max()), float(f[np.argmax(d)])

    return Reading(f=f, s=s, m=m, marker=int(np.argmin(np.abs(f - project["marker_hz"]))), rise=rise, t=t, z=z,
                   z_link=np.interp(t, *tdr(m[:, 0, 0], f, rise[1], target)), tdt=tdt,
                   tdt_link=np.interp(t, *step_response(m[:, 1, 0], f, rise[1])), t_far=t_far,
                   levels=levels(t, z, rise[0], t_far, target, DIFF_OHM if paired else SE_OHM), skew=skew,
                   xt=[(*peak(m[:, v, 0]), *peak(m[:, v + 1, 0])) for v in range(4 if paired else 2, m.shape[1], 2)],
                   eeff=eeff)


def si_limits(project: dict) -> tuple[str, ...]:
    """The stated limits of an SI result (design 5.6), in this order: I_LIMIT_SI_CROP, I_LIMIT_PEC (v1's),
    I_LIMIT_SI_DEBYE or I_LIMIT_SI_LOSSLESS by project["dielectric"], I_LIMIT_SI_BODIES, I_LIMIT_SI_PORTS,
    I_LIMIT_SI_RESOLUTION."""
    return ("I_LIMIT_SI_CROP", "I_LIMIT_PEC",
            "I_LIMIT_SI_LOSSLESS" if project["dielectric"] == "lossless" else "I_LIMIT_SI_DEBYE",
            "I_LIMIT_SI_BODIES", "I_LIMIT_SI_PORTS", "I_LIMIT_SI_RESOLUTION")


def si_lines(project: dict, r: Reading, route: dict) -> list[tuple[str, dict]]:
    """An SI result's lines (Stage 4 design 5.6) of the reading `r` and the run's `route`, which follow chain_results'
    (I_BASIS up to the indicators): I_SI_RELATIVE; I_SI_INSERTION (Sdd21, a net's S21, at the marker and at f_max);
    I_SI_WORST of Sdd11 (S11), then for a pair of Scd21, and I_SI_COMMON (Scc21 at the marker); I_SI_TDR; the lowest
    then the highest level as I_SI_TDR_LEVEL, or I_SI_TDR_SHORT on a short feature, else I_SI_TDR_SHORT_ROUTE with
    t_far, else I_SI_TDR_NO_ARRIVAL {floor: ARRIVAL_FLOOR}; I_SI_SKEW for a pair with both arrivals; I_SI_CROSSTALK per
    victim (project's victim lines in order, its first net, start and end; source T_PAIR_DRIVE or T_LINE_DRIVE);
    I_SI_LOSS_CONDUCTOR at the project's marker_hz (the formula's own frequency, not the grid point's), then
    I_SI_LOSS_DIELECTRIC with a lossless dielectric; W_NO_SECTIONS in their place when the route has no loss
    estimate."""
    paired, target = project["pair"] is not None, project["target_ohm"]
    marker_mhz, f_max_ghz = f"{r.f[r.marker] / 1e6:g}", f"{r.f[-1] / 1e9:g}"
    res = distance_mm(r.rise[0], r.eeff)  # the localising resolution length

    def worst(mode: str, x: np.ndarray) -> tuple[str, dict]:  # x's largest dB over f, at its grid point
        d = db(x)
        k = int(np.argmax(d))
        return "I_SI_WORST", {"mode": mode, "worst_db": f"{d[k]:.2f}", "f_mhz": f"{r.f[k] / 1e6:g}"}

    lines = [("I_SI_RELATIVE", {}),
             ("I_SI_INSERTION", {"mode": "Sdd21" if paired else "S21", "marker_mhz": marker_mhz,
                                 "at_marker_db": f"{db(r.m[r.marker, 1, 0]):.3f}", "f_max_ghz": f_max_ghz,
                                 "at_f_max_db": f"{db(r.m[-1, 1, 0]):.3f}"}),
             worst("Sdd11" if paired else "S11", r.m[:, 0, 0])]
    if paired:
        lines += [worst("Scd21", r.m[:, 3, 0]),
                  ("I_SI_COMMON", {"scc21_db": f"{db(r.m[r.marker, 3, 2]):.2f}", "marker_mhz": marker_mhz})]
    lines.append(("I_SI_TDR", {"kind": "T_DIFFERENTIAL" if paired else "T_SINGLE_ENDED",
                               "rise_ps": f"{r.rise[0] * 1e12:g}", "res_mm": f"{res:.1f}",
                               "link_ps": f"{r.rise[1] * 1e12:g}",
                               "link_res_mm": f"{distance_mm(r.rise[1], r.eeff):.1f}", "eeff": f"{r.eeff:.2f}"}))
    if r.levels is not None:
        for level, (t, z, short) in zip(("T_LOWEST", "T_HIGHEST"), r.levels):
            shown = {"level": level, "z": f"{z:.2f}", "t_ps": f"{t * 1e12:.1f}",
                     "d_mm": f"{distance_mm(t, r.eeff):.1f}"}
            if short:
                lines.append(("I_SI_TDR_SHORT", {**shown, "two_res_mm": f"{2 * res:.1f}"}))
            else:
                band = abs(z - target) <= project["tolerance"] * target
                lines.append(("I_SI_TDR_LEVEL", {**shown, "verdict": "T_IN_BAND" if band else "T_OUT_OF_BAND"}))
    elif r.t_far is not None:  # the route's round trip within its two launches
        lines.append(("I_SI_TDR_SHORT_ROUTE", {"t_far_ps": f"{r.t_far * 1e12:.1f}",
                                               "two_rise_ps": f"{2 * r.rise[0] * 1e12:g}"}))
    else:  # no step passes the measured line
        lines.append(("I_SI_TDR_NO_ARRIVAL", {"floor": f"{ARRIVAL_FLOOR:g}"}))
    if r.skew is not None:
        p, n = r.skew
        lines.append(("I_SI_SKEW", {"skew_ps": f"{(n - p) * 1e12:+.2f}", "n_ps": f"{n * 1e12:.1f}",
                                    "p_ps": f"{p * 1e12:.1f}"}))
    victims = [line["chain"] for line in project["lines"] if line["role"] == "victim"]
    lines += [("I_SI_CROSSTALK", {"net": v["nets"][0], "source": "T_PAIR_DRIVE" if paired else "T_LINE_DRIVE",
                                  "start": v["start"], "next_db": f"{next_db:.2f}", "next_mhz": f"{next_hz / 1e6:g}",
                                  "end": v["end"], "fext_db": f"{fext_db:.2f}", "fext_mhz": f"{fext_hz / 1e6:g}"})
              for v, (next_db, next_hz, fext_db, fext_hz) in zip(victims, r.xt)]
    if route["loss_db"] is None:  # no section solved: no loss estimate
        return lines + [("W_NO_SECTIONS", {})]
    conductor, dielectric = route["loss_db"]["conductor"], route["loss_db"]["dielectric"]
    lines.append(("I_SI_LOSS_CONDUCTOR", {"length_mm": f"{route['length_mm']:.1f}",
                                          "marker_mhz": f"{project['marker_hz'] / 1e6:g}",
                                          "at_marker_db": f"{conductor[0]:.3f}", "f_max_ghz": f_max_ghz,
                                          "at_f_max_db": f"{conductor[1]:.3f}"}))
    if project["dielectric"] == "lossless":
        lines.append(("I_SI_LOSS_DIELECTRIC", {"at_marker_db": f"{dielectric[0]:.3f}",
                                               "at_f_max_db": f"{dielectric[1]:.3f}"}))
    return lines


SI_OUTPUTS = re.compile(r"(layout|chain)\.s\d+p|si_summary\.(png|csv)|si_tdr\.csv")  # an SI run's files, matched whole
TDR_COLUMNS = ("t_s", "distance_mm", "z_ohm", "z_link_ohm", "tdt", "tdt_link")  # si_tdr.csv's


def si_csv(project: dict, r: Reading) -> bytes:
    """si_summary.csv (design 5.6): one row per grid point, f_hz, marker ("marker" at r.marker, else ""), then a pair's
    sdd11_db, sdd11_deg, sdd21_db, sdd21_deg, scc11_db, scc21_db, scd11_db, scd21_db, or a net's s11_db, s11_deg,
    s21_db, s21_deg, then next{k}_db and fext{k}_db for victim k from 1; dB by db, degrees by np.angle;
    comma-separated, "\\n" line ends, numbers as Python's repr (csv.writer, as summary_csv)."""
    m, paired = r.m, project["pair"] is not None
    columns = {"f_hz": r.f.tolist(), "marker": ["marker" if k == r.marker else "" for k in range(len(r.f))]}
    s = "sdd" if paired else "s"
    for name, x in ((f"{s}11", m[:, 0, 0]), (f"{s}21", m[:, 1, 0])):
        columns[f"{name}_db"], columns[f"{name}_deg"] = db(x).tolist(), np.angle(x, deg=True).tolist()
    if paired:
        for name, i, j in (("scc11", 2, 2), ("scc21", 3, 2), ("scd11", 2, 0), ("scd21", 3, 0)):
            columns[f"{name}_db"] = db(m[:, i, j]).tolist()
    for k, v in enumerate(range(4 if paired else 2, m.shape[1], 2), 1):  # a victim's start, then its end
        columns[f"next{k}_db"], columns[f"fext{k}_db"] = db(m[:, v, 0]).tolist(), db(m[:, v + 1, 0]).tolist()
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(zip(*columns.values()))
    return out.getvalue().encode("utf-8")


def _span(r: Reading) -> np.ndarray:
    """The plot's span, a mask on r.t: from −2·r.rise[0] to (r.t_far or 0) + 2·r.rise[1] (tdr_csv, draw_si)."""
    # ponytail: with no arrival the plot ends 2 link rise times past t = 0 (1 to 6 ns at the presets), so a long line's
    # open beyond that is cut; results.route's round trip if that matters
    return (r.t >= -2 * r.rise[0]) & (r.t <= (r.t_far or 0) + 2 * r.rise[1])


def tdr_csv(r: Reading) -> bytes:
    """si_tdr.csv (design 5.6): antenna._csv (imported inside) of TDR_COLUMNS, one row per sample of r.t from
    −2·r.rise[0] to (r.t_far or 0) + 2·r.rise[1], the plot's span: t_s, distance_mm (distance_mm at r.eeff), z_ohm (the
    localising TDR), z_link_ohm, tdt and tdt_link."""
    from kicad_rf_studio.core.post.antenna import _csv  # here only (C-5)

    k = _span(r)
    return _csv(TDR_COLUMNS, np.column_stack([r.t[k], distance_mm(r.t[k], r.eeff), r.z[k], r.z_link[k], r.tdt[k],
                                              r.tdt_link[k]]))


def draw_si(fig, curves: list[tuple[str, Reading]], project: dict, title: str, label: str | None = None) -> list:
    """si_summary.png's and compare.png's plots (design 5.6, 5.8) on the matplotlib Figure `fig`, each curve
    (name, Reading) on every panel: the TDR, the localising rise solid and the link's dashed, against the distance
    along the route on _span, with the round-trip time on a secondary axis on top (distance_mm at the first curve's
    εeff), the target band shaded (target ± tolerance), the first curve's launches shaded (its first resolution length
    at 0 and before t_far), every curve's levels a dot ("o") or, on a short feature, a cross ("x"), and the Ω axis
    from 0 to 3·target (an open's Z, unbounded as ρ → 1, clipped); |S| in dB against GHz (a pair's Sdd21, Sdd11, Scc21
    and Scd21, a net's S21 and S11) with a line at the marker; and, when the first curve holds crosstalk (its xt), each
    victim's NEXT and FEXT, named by the project's victim lines. A TDR curve is labelled by its rise time and its
    resolution length ("125 ps, 9.4 mm"), an |S| curve by its symbol, after the curve's name when there are two
    curves. Under `title`, then I_SI_RELATIVE, then `label` when given; the rendered si_limits, one a line, at the foot
    (fig.supxlabel, as draw_antenna). Returns the axes, the TDR's first."""
    first, two = curves[0][1], len(curves) > 1
    paired, target, tolerance = project["pair"] is not None, project["target_ohm"], project["tolerance"]
    axes = list(fig.subplots(1, 3 if first.xt else 2))
    ax_tdr, ax_s = axes[:2]
    symbols = ((("Sdd21", 1, 0), ("Sdd11", 0, 0), ("Scc21", 3, 2), ("Scd21", 3, 0)) if paired
               else (("S21", 1, 0), ("S11", 0, 0)))
    victims = [line["chain"]["nets"][0] for line in project["lines"] if line["role"] == "victim"]
    for name, r in curves:
        prefix, k, ghz = f"{name} " if two else "", _span(r), r.f / 1e9
        color = None
        for z, style, t_r in ((r.z, "-", r.rise[0]), (r.z_link, "--", r.rise[1])):
            trace, = ax_tdr.plot(distance_mm(r.t[k], r.eeff), z[k], style, color=color,
                                 label=f"{prefix}{t_r * 1e12:g} ps, {distance_mm(t_r, r.eeff):.1f} mm")
            color = trace.get_color()  # the link's in the localising curve's colour
        for t, z, short in r.levels or ():
            ax_tdr.plot(distance_mm(t, r.eeff), z, "x" if short else "o", color=color)
        for symbol, i, j in symbols:
            ax_s.plot(ghz, db(r.m[:, i, j]), label=prefix + symbol)
        if first.xt:
            for net, v in zip(victims, range(4 if paired else 2, r.m.shape[1], 2)):
                axes[2].plot(ghz, db(r.m[:, v, 0]), label=f"{prefix}NEXT {net}")
                axes[2].plot(ghz, db(r.m[:, v + 1, 0]), label=f"{prefix}FEXT {net}")
    ax_tdr.axhspan(target * (1 - tolerance), target * (1 + tolerance), color="grey", alpha=0.2,
                   label=render("I_PLOT_TARGET"))
    res = distance_mm(first.rise[0], first.eeff)
    ax_tdr.axvspan(0, res, color="grey", alpha=0.1)  # the launches: each port's first resolution length
    if first.t_far is not None:
        far = distance_mm(first.t_far, first.eeff)
        ax_tdr.axvspan(far - res, far, color="grey", alpha=0.1)
    ax_tdr.set(xlabel=render("I_PLOT_DISTANCE"), ylabel=render("I_PLOT_IMPEDANCE"), ylim=(0, 3 * target))
    per_ps = distance_mm(1e-12, first.eeff)  # mm of route per ps of round trip
    ax_tdr.secondary_xaxis("top", functions=(lambda d: d / per_ps, lambda ps: ps * per_ps)).set_xlabel(
        render("I_PLOT_TIME"))
    ax_s.axvline(first.f[first.marker] / 1e9, color="grey", linewidth=0.5)
    for ax in axes:
        if ax is not ax_tdr:
            ax.set(xlabel=render("I_PLOT_FREQUENCY"), ylabel="|S| (dB)")
        ax.legend()
    fig.suptitle(title + "\n" + render("I_SI_RELATIVE") + ("\n" + label if label else ""), wrap=True)
    fig.supxlabel("\n".join(render(code) for code in si_limits(project)), x=0.01, ha="left", fontsize="small",
                  wrap=True)
    return axes


def si_png(curves: list[tuple[str, Reading]], project: dict, title: str, label: str | None = None) -> bytes:
    """si_summary.png (design 5.6): draw_si on a Figure drawn by Agg, never a pyplot figure, as PNG at 100 dpi, as
    summary_png builds v1's."""
    from matplotlib.figure import Figure  # here only: no other code of the core loads matplotlib (C-5)

    fig = Figure(figsize=(15, 4.5), layout="constrained")
    draw_si(fig, curves, project, title, label)
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=100)
    return out.getvalue()


def compare_verify(own: Reading, retuned: Reading) -> dict:
    """verify's comparison of an SI project (Stage 4 design 5.7), in plain floats: the largest |ΔS| of own.s against
    retuned.s over every entry and over f from the first point above DC (the retune's DC point is its 5 MHz load held
    there, verify's the FDTD's own), and the f where it lies; and the TDR's levels, [[own lowest Z, retuned's, short],
    [own highest Z, retuned's, short]], short when either marks that level short, None when either reads none."""
    ds = np.abs(own.s[1:] - retuned.s[1:]).max(axis=(1, 2))  # per point above DC
    k = int(ds.argmax())
    levels = (None if own.levels is None or retuned.levels is None
              else [[a[1], b[1], a[2] or b[2]] for a, b in zip(own.levels, retuned.levels)])
    return {"ds_max": float(ds[k]), "f_hz": float(own.f[k + 1]), "levels": levels}


# design 5.8: the significance thresholds registered before any gate runs; gate P4-E keeps or widens each (plan 4)
IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS = 0.05, 0.5, -50.0, 1.0


def si_deltas(project: dict, base: Reading, variant: Reading) -> list[dict]:
    """The deltas of `variant` against `base` (Stage 4 design 5.8), rows of antenna.DELTA_COLUMNS (imported inside) in
    plain floats (None for no value), delta = variant − base: tdr_lowest and tdr_highest (Ω, DIFF_OHM for a pair,
    SE_OHM for a net; None when either has no levels; `marker` "short" when either level is short, so compare.csv
    keeps the mark); sdd21 (a net's s21) at "marker" and at "f_max", with its f_hz (dB, IL_DB); sdd11_worst
    (s11_worst), and for a pair scd21_worst (dB, DB); for a pair skew (ps, N − P, SKEW_PS; None without both
    arrivals); and for each victim next and fext, the victim's first net in `marker` (dB, DB). Resolved when |delta| >
    threshold, and for the DB rows only when the higher of the two levels stands above LEVEL_FLOOR_DB; None when the
    delta is None. Short features compare too (design 5.6: the same settings filter alike)."""
    from kicad_rf_studio.core.post.antenna import DELTA_COLUMNS  # here only (C-5)

    # ponytail: antenna.deltas' row, with the floor; one shared helper if a third kind compares
    def row(quantity, marker, f_hz, b, v, unit, threshold, floor=False):  # numbers as Python floats
        f_hz, b, v = (None if x is None else float(x) for x in (f_hz, b, v))
        delta = None if b is None or v is None else v - b
        resolved = None if delta is None else abs(delta) > threshold and (not floor or max(b, v) > LEVEL_FLOOR_DB)
        return dict(zip(DELTA_COLUMNS, (quantity, marker, f_hz, b, v, unit, delta, unit, threshold, resolved)))

    paired = project["pair"] is not None
    s, rows = "sdd" if paired else "s", []
    for k, quantity in enumerate(("tdr_lowest", "tdr_highest")):
        b, v = (r.levels[k] if r.levels else (None, None, False) for r in (base, variant))  # (t, Z, short)
        rows.append(row(quantity, "short" if b[2] or v[2] else "", None, b[1], v[1], "Ω",
                        DIFF_OHM if paired else SE_OHM))
    for marker, k in (("marker", base.marker), ("f_max", -1)):  # the variant's grid is the base's, by the fingerprint
        rows.append(row(f"{s}21", marker, base.f[k], db(base.m[k, 1, 0]), db(variant.m[k, 1, 0]), "dB", IL_DB))
    for quantity, i, j in ((f"{s}11_worst", 0, 0), *((("scd21_worst", 3, 0),) if paired else ())):
        rows.append(row(quantity, "", None, db(base.m[:, i, j]).max(), db(variant.m[:, i, j]).max(), "dB", DB, True))
    if paired:
        b, v = (None if r.skew is None else (r.skew[1] - r.skew[0]) * 1e12 for r in (base, variant))
        rows.append(row("skew", "", None, b, v, "ps", SKEW_PS))
    victims = [line["chain"]["nets"][0] for line in project["lines"] if line["role"] == "victim"]
    for net, xb, xv in zip(victims, base.xt, variant.xt):  # xt: (NEXT dB, Hz, FEXT dB, Hz)
        rows += [row("next", net, None, xb[0], xv[0], "dB", DB, True),
                 row("fext", net, None, xb[2], xv[2], "dB", DB, True)]
    return rows


def si_delta_lines(project: dict, rows: list[dict]) -> list[tuple[str, dict]]:
    """compare's lines of si_deltas' rows (design 5.8), each with its verdict, T_RESOLVED or T_NOT_RESOLVED:
    I_SI_COMPARE_LEVEL per TDR row (level T_LOWEST, T_HIGHEST), I_SI_COMPARE_LEVEL_SHORT when its marker is "short",
    or one I_SI_COMPARE_NO_LEVELS for both when they hold none; I_SI_COMPARE_INSERTION per sdd21 row (mode Sdd21 or
    S21, f_mhz); I_SI_COMPARE_WORST (mode Sdd11, S11, Scd21); I_SI_COMPARE_SKEW, or I_SI_COMPARE_NO_SKEW;
    I_SI_COMPARE_XT (kind NEXT or FEXT, net); then I_SI_COMPARE_THRESHOLDS {ohm, il_db, db, floor_db, ps} (:g, ohm by
    the project's kind). Ω and dB to 2 decimals, an insertion's dB to 3, the skew's ps signed to 2, each delta
    signed."""
    def shown(r: dict, digits: int, sign: str = "") -> dict:  # the row's numbers and its verdict
        return {"base": f"{r['base']:{sign}.{digits}f}", "variant": f"{r['variant']:{sign}.{digits}f}",
                "delta": f"{r['delta']:+.{digits}f}", "verdict": "T_RESOLVED" if r["resolved"] else "T_NOT_RESOLVED"}

    lines = []
    for r in rows:
        q = r["quantity"]  # a symbol in lower case: sdd21, s11_worst, next
        if q.startswith("tdr_") and r["delta"] is None:
            lines += [("I_SI_COMPARE_NO_LEVELS", {})] if q == "tdr_lowest" else []  # both rows hold none
        elif q.startswith("tdr_"):
            lines.append(("I_SI_COMPARE_LEVEL_SHORT" if r["marker"] == "short" else "I_SI_COMPARE_LEVEL",
                          {"level": "T_LOWEST" if q == "tdr_lowest" else "T_HIGHEST", **shown(r, 2)}))
        elif q in ("sdd21", "s21"):
            lines.append(("I_SI_COMPARE_INSERTION", {"mode": q.capitalize(), "f_mhz": f"{r['f_hz'] / 1e6:g}",
                                                     **shown(r, 3)}))
        elif q.endswith("_worst"):
            lines.append(("I_SI_COMPARE_WORST", {"mode": q.removesuffix("_worst").capitalize(), **shown(r, 2)}))
        elif q == "skew":
            lines.append(("I_SI_COMPARE_NO_SKEW", {}) if r["delta"] is None
                         else ("I_SI_COMPARE_SKEW", shown(r, 2, "+")))
        else:  # next or fext, its victim's first net in the marker
            lines.append(("I_SI_COMPARE_XT", {"kind": q.upper(), "net": r["marker"], **shown(r, 2)}))
    return lines + [("I_SI_COMPARE_THRESHOLDS", {"ohm": f"{DIFF_OHM if project['pair'] is not None else SE_OHM:g}",
                                                 "il_db": f"{IL_DB:g}", "db": f"{DB:g}",
                                                 "floor_db": f"{LEVEL_FLOOR_DB:g}", "ps": f"{SKEW_PS:g}"})]
