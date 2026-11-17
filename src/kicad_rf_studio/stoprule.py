# SPDX-License-Identifier: GPL-3.0-or-later
"""The stop rule (spec 6.3): whether, and when, a job's records show its run diverged, grew, converged or went flat, or
an SI job's residual fell too slowly past T_max. It reads the records in simulated time only, so its verdict depends on
neither the machine's speed nor how often the orchestrator polls. Times are in s and levels in dB. An emission job is
never flat, and its tail fit reads the rings still sounding at its end (Stage 5 design 5.7)."""
from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks

# provisional, P0 retunes them
PRESETS = {"draft": (-50.0, 1e-2), "normal": (-60.0, 2e-3), "strict": (-70.0, 5e-4)}  # (residual level, S tolerance)
GROWTH_DB = 20.0  # the rise of the energy envelope over its running minimum that is growth
FLAT_DB, FLAT_S = 1.0, 5e-9  # a residual that spans no more than FLAT_DB over FLAT_S is flat
FLAT_PERIODS = 20  # an antenna's flat window, in periods of f0 (Stage 3 design 5.4)
WINDOW_S = 2e-9  # the window of the residual and of the energy envelope
LAG_S = 1e-9  # the monitor compares S with S this much earlier
# an SI job past T_max (Stage 4 plan 4 ruling T-2)
RING_FIT_S = 3e-9  # the residual's last 3 ns, fitted by a line
RING_SLOPE = -0.3e9  # dB/s: a fit falling slower than 0.3 dB/ns ends the job
RING_CEILING = 4  # × T_max: the fit must reach the preset's level by then, and the job may run to it
# an emission job's tail fit (Stage 5 design 5.7)
TAIL_GAP_S = 2e-9  # the tail starts this long after 2·t0, the pulse's end
TAIL_WINDOW_S = 2e-9  # the envelope's windows, back to back
TAIL_CUT_DB = 20.0  # a port's peaks are its tail's local maxima within this of its largest
RING_FACTOR = 0.01  # a ring whose truncation factor is over this truncates the frequencies round it
RING_WIDTH = 50  # × f_r/Q: the half-width a ring truncates, its single-pole −40 dB width
N_FREQ = 101  # the monitor's frequencies across the band
Z0 = 50.0  # Ω, the reference of the port waves
KEPT = frozenset({"converged", "flat", "t_max"})  # the verdicts whose S is kept


@dataclass(frozen=True)
class Records:
    """A job's records: the port voltages `u` at `t_u` and currents `i` at `t_i`, both of shape (ports, n), and the
    log energy `e` at `te`."""
    t_u: np.ndarray
    u: np.ndarray
    t_i: np.ndarray
    i: np.ndarray
    te: np.ndarray
    e: np.ndarray


@dataclass(frozen=True)
class Verdict:
    """What the stop rule found: `kind` ("diverged", "growth", "converged", "flat" or "t_max", an SI pulse's verdict at
    or past T_max: ring), at the cut time `t`, with the port residual at the last t_u up to `t` (nan for "diverged")."""
    kind: str
    t: float
    residual_db: float


def residual_db(rec: Records, window: float = WINDOW_S) -> np.ndarray:
    """The port residual R_dB at each t_u: the peak of p = Σ_ports u² + (Z0·i)² over the last `window` (s; an SI
    pulse's stop_window, else WINDOW_S), relative to the peak of p so far; nan while p has been 0."""
    p = (rec.u ** 2 + (Z0 * rec.i) ** 2).sum(0)
    lo = np.searchsorted(rec.t_u, rec.t_u - window, "right")
    r = np.array([p[a:b + 1].max() for b, a in enumerate(lo)])
    with np.errstate(divide="ignore", invalid="ignore"):  # 0/0 before anything reaches the ports
        return 10 * np.log10(r / np.maximum.accumulate(p))


def flat_window(f0: float) -> float:
    """An antenna's flat window, in s: FLAT_PERIODS periods of `f0` (Hz), at least FLAT_S (Stage 3 design 5.4)."""
    return max(FLAT_S, FLAT_PERIODS / f0)


def stop_window(round_trip_s: float) -> float:
    """An SI run's residual window in s (Stage 4 design 5.4): 1.5 × the longest port-to-port round trip, at least
    WINDOW_S, so a pulse still travelling on a long line cannot read as converged."""
    return max(WINDOW_S, 1.5 * round_trip_s)


def ceiling(exc: dict) -> float:
    """The simulated time a job of the excitation `exc` may run to: RING_CEILING × T_max for an SI pulse (one with
    "window_s"), else its T_max."""
    return RING_CEILING * exc["t_max"] if "window_s" in exc else exc["t_max"]


def ring(t: np.ndarray, r_db: np.ndarray, level: float, t_max: float) -> float:
    """The first t at or past `t_max` where the residual `r_db` (dB, on `t`, s) over its last RING_FIT_S, fitted by a
    least-squares line, does not project `level` by RING_CEILING·t_max: its slope above RING_SLOPE (falling slower
    than 0.3 dB/ns, flat or rising) or its crossing later than that; inf while it does, or before t_max (Stage 4 plan 4
    ruling T-2, read as a fit renewed at every sample: an SI job whose planes ring runs on, the stop rule's converged
    verdict ending it)."""
    # ponytail: a polyfit per sample past T_max; cumulative sums if polls lag on long records
    # ponytail: T-2's 3 ns fit; a route whose window_s passes 3 ns can read its held peak as flat and end at T_max, as
    # before; fit over window_s + 1 ns if such a route rings
    lo = np.searchsorted(t, t - RING_FIT_S, "right")
    for n in np.flatnonzero(t >= t_max):
        tt, rr = t[lo[n]:n + 1], r_db[lo[n]:n + 1]
        ok = np.isfinite(rr)
        if ok.sum() < 2:
            return float(t[n])
        b, a = np.polyfit(tt[ok], rr[ok], 1)
        if b > RING_SLOPE or t[n] + (level - (a + b * t[n])) / b > RING_CEILING * t_max:
            return float(t[n])
    return math.inf


def stop_rule(rec: Records, k: int, preset: str, exc: dict) -> Verdict | None:
    """The earliest verdict on `rec`, a tie going to the first of diverged, growth, converged, flat and t_max, or None
    when there is none yet or `rec` has fewer than 2 samples. `k` is the 0-based row of the excited port, `preset` a
    key of PRESETS and `exc` the spec's excitation (f1, f2, t0, an antenna's or an SI pulse's flat window "flat_s",
    else FLAT_S, and an SI pulse's "window_s", the residual's window, else WINDOW_S, with its "t_max"). "t_max" is an
    SI pulse's verdict at or past T_max, where ring finds the residual too slow to converge by the ceiling; any other
    job runs to its T_max with no verdict. Causal: a verdict at t uses no sample after t, so the verdict on a prefix of
    a record is the earliest verdict of the whole record. An emission pulse's job (one with "emission") is never flat:
    a ringing board runs to its T_max, where tail_fit reads the rings (Stage 5 design 5.7)."""
    # ponytail: each poll recomputes the rule on the whole record; fine below about 1e4 samples, make it incremental
    # if polls lag
    if len(rec.t_u) < 2:
        return None
    bad = ((rec.t_u, ~np.isfinite(rec.u).all(0)), (rec.t_i, ~np.isfinite(rec.i).all(0)), (rec.te, ~np.isfinite(rec.e)))
    t_bad = min(np.min(t, initial=np.inf, where=b) for t, b in bad)
    keep, keep_e = (rec.t_u < t_bad) & (rec.t_i < t_bad), rec.te < t_bad  # the other rules see only finite samples
    rec = Records(rec.t_u[keep], rec.u[:, keep], rec.t_i[keep], rec.i[:, keep], rec.te[keep_e], rec.e[keep_e])
    level, tol = PRESETS[preset]
    r_db = residual_db(rec, exc.get("window_s", WINDOW_S))
    # ponytail: the growth detector keeps v1's 2 ns window under an SI pulse, whose field energy holds; an SI ruling if
    # P4-D sees false growth
    found = {"diverged": t_bad, "growth": _growth(rec, exc["t0"]),
             "converged": _converged(rec, r_db, k, level, tol, exc),
             "flat": np.inf if exc.get("emission") else _flat(rec, r_db, level, exc["t0"], exc.get("flat_s", FLAT_S)),
             "t_max": ring(rec.t_u, r_db, level, exc["t_max"]) if "window_s" in exc else np.inf}
    kind = min(found, key=found.get)  # the first of the earliest
    if found[kind] == np.inf:
        return None
    t = float(found[kind])
    return Verdict(kind, t, np.nan if kind == "diverged" else float(r_db[np.searchsorted(rec.t_u, t, "right") - 1]))


def _rises(rec: Records, t0: float) -> Iterator[tuple[float, float]]:
    """(te, rise) at each te after the pulse (te > 2·t0): the rise in dB of the energy envelope over its minimum on
    the earlier samples after the pulse, -inf at the first. The envelope is the peak of E_dB over the last WINDOW_S,
    widened to the last 4 samples, so a sparse log does not alias it."""
    on = rec.e > 0  # a sample at 0 has no dB: skipped
    te, e_db = rec.te[on], 10 * np.log10(rec.e[on])
    lo = np.minimum(np.searchsorted(te, te - WINDOW_S, "right"), np.arange(len(te)) - 3).clip(0)
    floor = np.inf
    for m in np.flatnonzero(te > 2 * t0):
        env = e_db[lo[m]:m + 1].max()
        yield te[m], env - floor
        floor = min(floor, env)


def _growth(rec: Records, t0: float) -> float:
    """The first te after the pulse where the energy envelope rises GROWTH_DB over its running minimum (_rises); inf
    when it never does."""
    return next((t for t, rise in _rises(rec, t0) if rise >= GROWTH_DB), np.inf)


def growth_rise(rec: Records, t0: float) -> float:
    """The largest rise in dB of the energy envelope over its running minimum after the pulse (te > 2·t0), the
    statistic _growth compares with GROWTH_DB (D-38); 0.0 when it never rises."""
    return float(max([0.0, *(rise for _, rise in _rises(rec, t0))]))


def _converged(rec: Records, r_db: np.ndarray, k: int, level: float, tol: float, exc: dict) -> float:
    """The first t_u after 2·t0 + LAG_S with the residual at most `level` and the monitor at most `tol`; inf when none.
    The monitor at n is the largest |s_j(n) − s_j(m)| over ports j and N_FREQ frequencies from f1 to f2, m the last
    sample LAG_S or more before n and s_j = (U_j − Z0·I_j)/(U_k + Z0·I_k), from the DFTs of u on t_u and of i on t_i
    cut at that sample."""
    t_u = rec.t_u
    cand = np.flatnonzero((t_u > 2 * exc["t0"] + LAG_S) & (r_db <= level))
    if not len(cand):
        return np.inf
    m = np.searchsorted(t_u, t_u[cand] - LAG_S, "right") - 1
    f = np.linspace(exc["f1"], exc["f2"], N_FREQ)[:, None]
    n = cand[-1] + 1  # one cumulative sum over the samples gives every cut at once
    U = np.cumsum(rec.u[:, None, :n] * np.exp(-2j * np.pi * f * t_u[:n]), axis=-1)
    I = np.cumsum(rec.i[:, None, :n] * np.exp(-2j * np.pi * f * rec.t_i[:n]), axis=-1)

    def s(at):
        return (U[..., at] - Z0 * I[..., at]) / (U[k][:, at] + Z0 * I[k][:, at])

    hit = cand[np.abs(s(cand) - s(m)).max(axis=(0, 1)) <= tol]
    return t_u[hit[0]] if len(hit) else np.inf


def _flat(rec: Records, r_db: np.ndarray, level: float, t0: float, window: float = FLAT_S) -> float:
    """The first t_u at or after 2·t0 + `window` with the residual above `level` and spanning at most FLAT_DB over the
    last `window` (s); inf when none."""
    t_u = rec.t_u
    lo = np.searchsorted(t_u, t_u - window, "right")
    for n in np.flatnonzero((t_u >= 2 * t0 + window) & (r_db > level)):
        if np.ptp(r_db[lo[n]:n + 1]) <= FLAT_DB:
            return t_u[n]
    return np.inf


def tail_fit(t: np.ndarray, u: np.ndarray, exc: dict, t_end: float) -> list[dict]:
    """The rings an emission job leaves at its end `t_end` (s), read from every port's voltage, the rows of `u` on `t`
    (Stage 5 design 5.7; AR-5): {"f_hz", "q", "factor"}, ascending in f. A port's tail runs from 2·t0 + TAIL_GAP_S to
    t_end; its peaks are the local maxima of its Hann-windowed DFT, on a grid of 1/(4·span) over the pulse band (f1,
    f2), within TAIL_CUT_DB of its largest. Their amplitudes are fitted jointly in back-to-back TAIL_WINDOW_S windows,
    and a line through each one's envelope in dB gives Q = (20/ln 10)·π·f_r/|slope| and the truncation factor
    e^(−π·f_r·t_end/Q), or q None and factor 1.0 for an envelope that does not decay. Over the ports, the entries
    within 2/span of a group's first are one ring, the one of the largest factor (BC6). Empty for a quiet tail or one
    shorter than 3 windows."""
    t_s = 2 * exc["t0"] + TAIL_GAP_S
    span = t_end - t_s
    n_win = math.floor(span / TAIL_WINDOW_S)
    if n_win < 3:
        return []
    grid = exc["f1"] + np.arange(math.floor((exc["f2"] - exc["f1"]) * 4 * span) + 1) / (4 * span)
    tail = (t >= t_s) & (t < t_end)
    tt, xs = t[tail], u[:, tail]
    # Hann: a rectangle's −13 dB sidelobes would read as peaks within 20 dB (the builder's, design 6)
    tapered = np.hanning(tt.size) * xs
    spectra = np.abs([tapered @ np.exp(-2j * np.pi * f * tt) for f in grid])  # (grid, ports)
    edges = t_s + np.arange(n_win + 1) * TAIL_WINDOW_S
    windows = [(tt >= a) & (tt < b) for a, b in zip(edges, edges[1:])]  # back to back, rectangular
    centres = edges[:-1] + TAIL_WINDOW_S / 2
    found = []
    for x, spectrum in zip(xs, spectra.T):
        if spectrum.max() == 0:
            continue
        top = find_peaks(spectrum)[0]
        peaks = grid[top[spectrum[top] >= spectrum.max() * 10 ** (-TAIL_CUT_DB / 20)]]  # this port's own peaks
        amps = []
        for w in windows:
            # jointly (the builder's, AR-5): a lone DFT leaks a neighbour 0.6 GHz off into the envelope
            # ponytail: 2·peaks columns must stay under a window's samples (about 48 at f2 3 GHz); a peak list that
            # long would need fewer, stronger peaks
            arg = 2 * np.pi * np.outer(tt[w], peaks)
            c = np.linalg.lstsq(np.hstack([np.cos(arg), np.sin(arg)]), x[w], rcond=None)[0]
            amps.append(np.hypot(c[:peaks.size], c[peaks.size:]))
        for f_r, a in zip(peaks, np.array(amps).T):
            on = a > 0
            if on.sum() < 3:
                continue
            slope = np.polyfit(centres[on], 20 * np.log10(a[on]), 1)[0]  # dB/s
            if slope < 0:
                q = float(20 / math.log(10) * math.pi * f_r / -slope)
                found.append({"f_hz": float(f_r), "q": q, "factor": math.exp(-math.pi * f_r * t_end / q)})
            else:  # an envelope that does not decay has no Q (AR-5)
                found.append({"f_hz": float(f_r), "q": None, "factor": 1.0})
    groups: list[list[dict]] = []
    for r in sorted(found, key=lambda r: r["f_hz"]):
        if groups and r["f_hz"] - groups[-1][0]["f_hz"] <= 2 / span:
            groups[-1].append(r)
        else:
            groups.append([r])
    return [max(g, key=lambda r: r["factor"]) for g in groups]  # BC6: the worst over the ports


def truncated(f: np.ndarray, rings: list[dict]) -> np.ndarray:
    """Whether each frequency of `f` (Hz) is truncated by tail_fit's `rings` (Stage 5 design 5.7): within
    RING_WIDTH·f_r/Q of a ring whose factor is over RING_FACTOR, or at every frequency when a ring has no Q (AR-5)."""
    out = np.zeros(f.shape, bool)
    for r in rings:
        if r["q"] is None:
            out[:] = True
        elif r["factor"] > RING_FACTOR:
            out |= np.abs(f - r["f_hz"]) <= RING_WIDTH * r["f_hz"] / r["q"]
    return out
