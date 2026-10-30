# SPDX-License-Identifier: GPL-3.0-or-later
"""The parts of the chain on the co-simulation grid (spec 5.7, 7.2, 7.3): each part port's Z_part, from its value and
package preset or from its S2P file; the loads that close the part ports, the layout N-port closed by them, and the
ideal schematic of the parts alone."""
from pathlib import Path

import numpy as np
import skrf as rf
from skrf.circuit import Circuit

from kicad_rf_studio.core.kicad.tracer import is_gnd, is_power
from kicad_rf_studio.core.kicad.values import bypass, part_kind, port_value
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import COPPER, CURVE_PORT, PORT, Z0, c_box_of
from kicad_rf_studio.core.project import antenna, parts


def z_part(kind: str, value: float, model: dict | None, f: np.ndarray) -> np.ndarray:
    """Z_part (F,) on f of a C, L or R of `value` (F, H or Ω) with its preset's esl_h, esr_ohm and cp_f, all 0 for no
    `model` (C-13, spec 5.7): C: ESR + jωESL + 1/(jωC); L: (ESR + jωL) ∥ 1/(jωCp); R: (R + jωESL) ∥ 1/(jωCp)."""
    esl, esr, cp = (model["esl_h"], model["esr_ohm"], model["cp_f"]) if model else (0.0, 0.0, 0.0)
    w = 2 * np.pi * f
    if kind == "C":
        return esr + 1j * w * esl + 1 / (1j * w * value)
    zs = esr + 1j * w * value if kind == "L" else value + 1j * w * esl
    return zs / (1 + 1j * w * cp * zs)  # zs ∥ 1/(jωCp), finite at zs = 0


def z_value(ref: str, text: str, model: dict | None, f: np.ndarray, *, bypasses: bool = False) -> np.ndarray | None:
    """Z_part (F,) on f of the part `ref` from its value text `text` (spec 5.7, 7.2): with `bypasses` (an antenna's
    part, Stage 3 design 5.7), a bypass first, 0 or inf at every f with no package model; else z_part of its kind,
    port_value and `model`; None when the text reads as neither."""
    if bypasses and (z := bypass(ref, text)) is not None:
        return np.full(len(f), z, complex)
    value = port_value(ref, text)
    return None if value is None else z_part(part_kind(ref), value, model, f)


def s2p_impedance(file: Path, connection: str, ref: str, f: np.ndarray) -> tuple[np.ndarray, str | None]:
    """Z_part (F,) on f of the part `ref` from its Touchstone 2-port `file`, measured in a "series" or "shunt" thru
    fixture (`connection`; C-14): series 2·Z0·(1 − S21)/S21, shunt Z0·S21/(2·(1 − S21)), with S21 the mean of S21 and
    S12 interpolated linearly on its real and imaginary parts (never Z, never extrapolated), Z0 the file's R and its
    noise data ignored. With it, the other connection when the file's own points from f[0] to f[-1] fit that
    fixture's identity better (series S11 + S21 = 1, shunt S21 − S11 = 1), else None. Refusals, each naming ref and
    path: E_S2P_MISSING, E_S2P_UNREADABLE (a reader error, or no data), E_S2P_PORTS, E_S2P_BAND (the file must span
    f[0] to f[-1])."""
    named = {"ref": ref, "path": str(file)}
    if not file.exists():
        raise KrsError("E_S2P_MISSING", **named)
    n = rf.Network()  # never rf.Network(file), which unpickles
    try:
        n.read_touchstone(str(file))
    except Exception:  # a parser of user input: whatever it raises, the file cannot be read
        raise KrsError("E_S2P_UNREADABLE", **named) from None
    if not len(n.f):
        raise KrsError("E_S2P_UNREADABLE", **named)
    if n.nports != 2:
        raise KrsError("E_S2P_PORTS", **named, ports=n.nports)
    if n.f[0] > f[0] or n.f[-1] < f[-1]:
        raise KrsError("E_S2P_BAND", **named, f_lo=f"{n.f[0] / 1e6:.1f}", f_hi=f"{n.f[-1] / 1e6:.1f}",
                       f1=f"{f[0] / 1e6:.1f}", f2=f"{f[-1] / 1e6:.1f}")
    s11, s21 = n.s[:, 0, 0], (n.s[:, 1, 0] + n.s[:, 0, 1]) / 2
    band = (n.f >= f[0]) & (n.f <= f[-1])
    miss = {"series": np.abs(s11 + s21 - 1)[band].max(initial=0.0),
            "shunt": np.abs(s21 - s11 - 1)[band].max(initial=0.0)}  # 0 for both when no point lies in the band
    other = "shunt" if connection == "series" else "series"
    s21_grid = np.interp(f, n.f, s21.real) + 1j * np.interp(f, n.f, s21.imag)
    z0 = n.z0[0, 0].real
    z = 2 * z0 * (1 - s21_grid) / s21_grid if connection == "series" else z0 * s21_grid / (2 * (1 - s21_grid))
    return z, other if miss[other] < miss[connection] else None


def part_impedances(project: dict, folder: Path, refs: list[str], f: np.ndarray
                    ) -> tuple[dict[str, np.ndarray], list[tuple[str, dict]]]:
    """Z_part (F,) on f of each part in `refs` (C-13..C-15, spec 7.2): from its s2p file, read at folder / file
    (folder: project.json's), when it names one, else z_part of its kind, port_value and model, or an antenna's
    bypasses (z_value); and W_S2P_FIXTURE for each file that fits the other fixture. Raises E_PART_NO_VALUE for a part
    with neither a file nor a value that z_value reads, and s2p_impedance's refusals."""
    by_ref, z, notes = parts(project), {}, []
    for ref in refs:
        part = by_ref[ref]
        if s2p := part["s2p"]:
            file = (folder / s2p["file"]).resolve()
            z[ref], fits = s2p_impedance(file, s2p["connection"], ref, f)
            if fits:
                notes.append(("W_S2P_FIXTURE", {"ref": ref, "path": str(file), "named": s2p["connection"],
                                                "fits": fits}))
        else:
            z[ref] = z_value(ref, part["value"], part["model"], f, bypasses=antenna(project))
            if z[ref] is None:
                raise KrsError("E_PART_NO_VALUE", ref=ref, value=part["value"])
    return z, notes


def with_box(z: np.ndarray, f: np.ndarray, c_box: float) -> np.ndarray:
    """The load (F,) that closes a part port: its Z_part `z` across its box's capacitance c_box (F),
    z ∥ 1/(jω·c_box) = z/(1 + jω·c_box·z), finite at z = 0 (spec 7.2); an open part's (z inf, Stage 3 design 5.7) is
    the box's capacitance alone, 1/(jω·c_box)."""
    y = 2j * np.pi * f * c_box
    with np.errstate(invalid="ignore"):  # inf·0j in the unused branch
        return np.where(np.isinf(z), 1 / y, z / (1 + y * z))


def loads(zparts: dict[str, np.ndarray], refs: list[str], c_box: dict, f: np.ndarray) -> np.ndarray:
    """The loads (F, M) of the part ports `refs`, column m for refs[m]: with_box of its Z_part and of the C_box the
    run recorded for it, which E_CBOX refuses when it is missing, not finite or not above 0 (C-16). M may be 0."""
    z = [with_box(zparts[ref], f, c_box_of(c_box, ref)) for ref in refs]
    return np.array(z, complex).reshape(len(refs), len(f)).T


def terminate(s: np.ndarray, ext: list[int], zk: np.ndarray, f: np.ndarray) -> np.ndarray:
    """S (F, P, P) of the layout N-port `s` (F, N, N) at its ports `ext`, in that order, with every other port k, the
    m-th of them in index order, closed by the load zk[:, m] (zk: F, M), through scikit-rf's Circuit (spec 7.2). Z0
    at every port; with M = 0 it is `s` at `ext`."""
    freq = rf.Frequency.from_f(f, unit="Hz")
    layout = rf.Network(frequency=freq, s=s, z0=Z0, name="layout")
    cnx = [[(Circuit.Port(freq, f"port{n}", z0=Z0), 0), (layout, k)] for n, k in enumerate(ext)]
    closed = [k for k in range(s.shape[-1]) if k not in ext]
    cnx += [[(layout, k), (rf.Network(frequency=freq, z=zk[:, m].reshape(-1, 1, 1), z0=Z0, name=f"load{k}"), 0)]
            for m, k in enumerate(closed)]
    return Circuit(cnx).s_external


def ideal_schematic(project: dict, zparts: dict[str, np.ndarray], f: np.ndarray) -> np.ndarray:
    """S (F, 2, 2) of the chain's series and shunt parts alone, each at its Z_part in `zparts`, with no layout, no
    C_box and no traces (C-30); `others` are left out. P1 sits on chain.nets[0] and P2 on chain.nets[-1], 50 Ω each.
    A nodal solve: a net off the chain that is GND or power (classes.gnd_nets and power_nets, or is_gnd and is_power
    by name where a list is null) is ground; a copper part, and a port or curve_port part whose Z_part is 0 at every
    f, joins its two nets; an open part is left out; every other port or curve_port part puts 1/Z_part in Y between
    the nodes of its nets (a ground end on the diagonal only); Q (n, 2) holds 1 at P1's node and at P2's, none on a
    grounded net; S = 2·Qᵀ·(Y + Q·Qᵀ/Z0)⁻¹·Q/Z0 − I."""
    chain, classes = project["chain"], project["classes"]
    gnd, power = classes["gnd_nets"], classes["power_nets"]
    chain_parts = chain["series"] + chain["shunt"]
    root = {}  # union-find over the nets; "" is the ground group

    def find(net: str) -> str:
        while root.setdefault(net, net) != net:
            net = root[net]
        return net

    def join(a: str, b: str) -> None:
        a, b = sorted((find(a), find(b)))  # "" sorts first, so ground stays the root of any group it joins
        root[b] = a

    for q in chain_parts:
        for net in q["nets"]:
            if net not in chain["nets"] and ((is_gnd(net) if gnd is None else net in gnd)
                                             or (is_power(net) if power is None else net in power)):
                join("", net)
        if q["role"] == COPPER or (q["role"] in (PORT, CURVE_PORT) and not np.any(zparts[q["ref"]])):
            join(*q["nets"])
    ports = [q for q in chain_parts if q["role"] in (PORT, CURVE_PORT)]
    node = {}  # the groups that are nodes, by index: chain.nets' first; ground is none of them
    for net in [*chain["nets"], *(net for q in ports for net in q["nets"])]:
        if (group := find(net)) != "":
            node.setdefault(group, len(node))
    n = len(node)

    def at(net: str) -> int:
        """The index of the net's node; ground's is n, a slot that Y and Q drop."""
        return node.get(find(net), n)

    Y = np.zeros((len(f), n, n), complex)
    for q in ports:
        if np.any(z := zparts[q["ref"]]):  # a part of 0 Ω joined its nets above
            v = np.zeros(n + 1)
            v[at(q["nets"][0])] += 1
            v[at(q["nets"][1])] -= 1
            Y += np.outer(v[:n], v[:n]) / z[:, None, None]
    Q = np.zeros((n + 1, 2))
    Q[[at(chain["nets"][0]), at(chain["nets"][-1])], [0, 1]] = 1
    Q = Q[:n]
    return 2 * Q.T @ np.linalg.solve(Y + Q @ Q.T / Z0, Q) / Z0 - np.eye(2)
