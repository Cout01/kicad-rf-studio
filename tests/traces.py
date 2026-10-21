# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic job records for replaying the stop rule (spec 6.3): the pulse of spec 5.8 into port `k`, then a decaying
ring on every port, as openEMS's probes and log energy would record them."""
import numpy as np

from kicad_rf_studio.stoprule import Z0, Records


def trace(kind, ports=2, k=0, f1=457.5e6, f2=3.0195e9, dt=4.1e-11, t_end=40e-9) -> Records:
    """Records of `kind`: "converge" (the ring decays with τ = 1 ns; any other kind not named here too), "tmax"
    (τ = 6 ns, too slow to converge in 40 ns), "flat" (a steady sine stays on the last port), "growth" (a sine on the
    last port grows after 8 ns) or "nan" (a NaN voltage on the last port at sample 200). u is sampled at t_u, i half a
    step later, the energy at t_u."""
    fm, fw = (f1 + f2) / 2, (f2 - f1) / 2
    t0 = 9 / (2 * np.pi * fw)
    tau = 6e-9 if kind == "tmax" else 1e-9

    def pulse(t):
        return np.sin(2 * np.pi * fm * (t - t0)) * np.exp(-(2 * np.pi * fw * t / 3 - 3) ** 2) * (t < 2 * t0)

    def ring(j, t):
        a = 0.3 if j == k else 0.2
        return a * np.exp(-np.maximum(t - 2 * t0, 0) / tau) * np.sin(2 * np.pi * (1.0 + 0.3 * j) * 1e9 * t) * (t > t0)

    def added(t):  # what "flat" or "growth" adds to the last port
        if kind == "flat":
            return 1e-2 * np.sin(2 * np.pi * 1.2e9 * t)
        return 1e-4 * np.exp(np.maximum(t - 8e-9, 0) / 1.3e-9) * (t > 8e-9) * np.sin(2 * np.pi * 1.5e9 * t)

    t_u = np.arange(0, t_end, dt)
    t_i = t_u + dt / 2
    u = np.array([0.5 * pulse(t_u) * (j == k) + ring(j, t_u) for j in range(ports)])
    i = np.array([0.5 * pulse(t_i) * (j == k) - ring(j, t_i) for j in range(ports)]) / Z0
    if kind in ("flat", "growth"):  # the added term also goes into the current, as −term/Z0
        u[-1] += added(t_u)
        i[-1] -= added(t_i) / Z0
    if kind == "nan":
        u[-1, min(200, len(t_u) - 1)] = np.nan
    return Records(t_u, u, t_i, i, t_u, (u ** 2 + (Z0 * i) ** 2).sum(0))
