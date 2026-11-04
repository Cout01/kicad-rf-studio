# SPDX-License-Identifier: GPL-3.0-or-later
"""Signal integrity's readings (Stage 4 design 5.1, 5.5, 5.6): the uniform grid from DC, the Gaussian rise filter and
the TDR's step response from S; mixed mode at the target; the TDT's arrival, the levels between the launches and the
skew; Hammerstad's conductor loss, for the route's loss estimate; and, from later tasks, the lines, files, verify's
comparison and compare's deltas. At module level it imports only the stdlib, numpy and core.messages: core.project
imports it for LOCAL_RISE, so scipy, scikit-rf, matplotlib, core.model.parts and core.post.antenna are imported inside
the functions that use them (C-5)."""
import math
import warnings
from dataclasses import dataclass

import numpy as np

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
