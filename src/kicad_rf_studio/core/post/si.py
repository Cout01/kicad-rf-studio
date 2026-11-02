# SPDX-License-Identifier: GPL-3.0-or-later
"""Signal integrity's time-domain readings (Stage 4 design 5.1, 5.6): the uniform grid from DC, the Gaussian rise filter
and the TDR's step response from S. Pure numpy: it never imports openEMS or scikit-rf."""
import math

import numpy as np

# ponytail: a response longer than the 1/Δf record wraps, and Z = z_ref(1 + ρ)/(1 − ρ) has no bound as ρ → 1 (an
# open); plan 3 retunes N_TDR
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
