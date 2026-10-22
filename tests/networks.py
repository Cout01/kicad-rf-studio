# SPDX-License-Identifier: GPL-3.0-or-later
"""Known networks and the waves openEMS would record from them (r6-math), for the co-simulation tests and the
KRS_FAKE=network fake: S = B·A⁻¹ must give back the network the waves came from. The Touchstone helpers import skrf
inside, since the fake worker imports this module and a worker never imports skrf."""
import numpy as np

Z0, C_BOX = 50.0, 2e-14  # Ω at every port; F, the fake worker's C_box of a part port


def star(f, n, a=0.95, tau=0.2e-9):
    """The S (F, n, n) of n 50 Ω lines of amplitude a and delay tau joined at one node: passive (σ_max = a²),
    reciprocal and causal."""
    g = a * np.exp(-2j * np.pi * np.asarray(f, float) * tau)
    return (g ** 2)[:, None, None] * (2 / n * np.ones((n, n)) - np.eye(n))


def synth_records(s_of, n, f1, f2, dt, t_rec, smooth=False):
    """[(t_u, u, t_i, i)] of n jobs on the n-port s_of(f) (reference Z0), every port closed by Z0 ∥ C_BOX as an
    openEMS lumped port is, job j driving port j through it with spec 5.8's pulse (smooth: one with no exp(−9)
    steps): u at openEMS's probe instants k·Δ, Δ = (floor(1/(2·f2·dt)) // 4)·dt, i at k·Δ + dt/2, k·Δ < t_rec.
    Band-limited exact samples, synthesised on an FFT grid 8 times longer than the record (r6 §2)."""
    fm, fw = (f1 + f2) / 2, (f2 - f1) / 2
    t0 = 9 / (2 * np.pi * fw)
    if smooth:
        e = lambda t: np.sin(2 * np.pi * fm * (t - 2 * t0)) * np.exp(-(2 * np.pi * fw * (t - t0) / 3 - 3) ** 2)
    else:
        e = lambda t: np.sin(2 * np.pi * fm * (t - t0)) * np.exp(-(2 * np.pi * fw * t / 3 - 3) ** 2) * (t < 2 * t0)
    step = (int(np.floor(1 / (2 * f2 * dt))) // 4) * dt
    k = int(t_rec / step)
    m = 8 * k | 1  # odd: irfft keeps every bin
    fb = np.fft.rfftfreq(m, step)
    fb[0] = fb[1] * 1e-6
    E = np.fft.rfft(e(np.arange(m) * step))
    zt = Z0 / (1 + 2j * np.pi * fb * C_BOX * Z0)
    g = ((zt - Z0) / (zt + Z0))[:, None, None]
    S = s_of(fb)
    a = np.linalg.solve(np.eye(n) - g * S, np.eye(n) * (np.sqrt(Z0) / (Z0 + zt))[:, None, None])
    b = S @ a
    V, I = np.sqrt(Z0) * (a + b), (a - b) / np.sqrt(Z0)
    shift = np.exp(2j * np.pi * fb * dt / 2)[:, None, None]
    u, i = (np.fft.irfft(X * E[:, None, None], m, axis=0)[:k] for X in (V, I * shift))
    t_u = np.arange(k) * step
    return [(t_u, u[:, :, j].T.copy(), t_u + dt / 2, i[:, :, j].T.copy()) for j in range(n)]


def terminate_np(s, ext, zk):
    """S' = S_ee + S_ei·Γ·(I − S_ii·Γ)⁻¹·S_ie, Γ_k = (Z_k − Z0)/(Z_k + Z0) for the ports not in ext (index order),
    zk (F, M): the numpy oracle of the termination."""
    i = [k for k in range(s.shape[-1]) if k not in ext]
    g = (zk - Z0) / (zk + Z0)
    see, sei, sie, sii = (s[:, r][:, :, c] for r, c in ((ext, ext), (ext, i), (i, ext), (i, i)))
    return see + (sei * g[:, None, :]) @ np.linalg.solve(np.eye(len(i)) - sii * g[:, None, :], sie)


def thru(z, connection, z0=50.0):
    """The S (F, 2, 2) of the impedance z (F,) in a series (`connection` "series") or shunt (any other) thru fixture of
    z0 Ω."""
    s21 = 2 * z0 / (2 * z0 + z) if connection == "series" else 2 * z / (2 * z + z0)
    s11 = z / (2 * z0 + z) if connection == "series" else -z0 / (2 * z + z0)
    return np.stack([np.stack([s11, s21], -1), np.stack([s21, s11], -1)], -2)


def write_s2p(path, z, connection, f, z0=50.0):
    """A Touchstone 2-port at `path` (a .s2p name) of the impedance z (one per f, Hz) measured in a series or shunt
    fixture of z0 Ω (spec 9.1's synthetic S2P files from ideal RLC)."""
    import skrf as rf

    rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=thru(z, connection, z0), z0=z0,
               name="part").write_touchstone(str(path.with_suffix("")))
    return path


def read_s(path):
    """The S of a Touchstone file, read the safe way."""
    import skrf as rf

    n = rf.Network()
    n.read_touchstone(str(path))
    return n.s
