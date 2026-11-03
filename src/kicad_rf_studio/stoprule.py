# SPDX-License-Identifier: GPL-3.0-or-later
"""The stop rule (spec 6.3): whether, and when, a job's records show its run diverged, grew, converged or went flat.
It reads the records in simulated time only, so its verdict depends on neither the machine's speed nor how often the
orchestrator polls. Times are in s and levels in dB."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

# provisional, P0 retunes them
PRESETS = {"draft": (-50.0, 1e-2), "normal": (-60.0, 2e-3), "strict": (-70.0, 5e-4)}  # (residual level, S tolerance)
GROWTH_DB = 20.0  # the rise of the energy envelope over its running minimum that is growth
FLAT_DB, FLAT_S = 1.0, 5e-9  # a residual that spans no more than FLAT_DB over FLAT_S is flat
FLAT_PERIODS = 20  # an antenna's flat window, in periods of f0 (Stage 3 design 5.4)
WINDOW_S = 2e-9  # the window of the residual and of the energy envelope
LAG_S = 1e-9  # the monitor compares S with S this much earlier
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
    """What the stop rule found: `kind` ("diverged", "growth", "converged" or "flat"), at the cut time `t`, with the
    port residual at the last t_u up to `t` (nan for "diverged")."""
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


def stop_rule(rec: Records, k: int, preset: str, exc: dict) -> Verdict | None:
    """The earliest verdict on `rec`, a tie going to the first of diverged, growth, converged and flat, or None when
    there is none yet or `rec` has fewer than 2 samples. `k` is the 0-based row of the excited port, `preset` a key of
    PRESETS and `exc` the spec's excitation (f1, f2, t0, an antenna's or an SI pulse's flat window "flat_s", else
    FLAT_S, and an SI pulse's "window_s", the residual's window, else WINDOW_S). Causal: a verdict at t uses no sample
    after t, so the verdict on a prefix of a record is the earliest verdict of the whole record."""
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
             "flat": _flat(rec, r_db, level, exc["t0"], exc.get("flat_s", FLAT_S))}
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
