# SPDX-License-Identifier: GPL-3.0-or-later
import math
from dataclasses import replace

import numpy as np
import pytest

from kicad_rf_studio.core.model.spec import dc_pulse
from kicad_rf_studio.stoprule import GROWTH_DB, Z0, Records, flat_window, growth_rise, stop_rule, stop_window
from traces import trace

EXC = {"f1": 457.5e6, "f2": 3.0195e9, "t0": 9 / (2 * math.pi * 1.281e9)}


@pytest.mark.parametrize(("kind", "preset", "verdict", "t_ns"), [
    ("converge", "draft", "converged", 9.31), ("converge", "normal", "converged", 10.70),
    ("converge", "strict", "converged", 11.81), ("flat", "normal", "flat", 12.30),
    ("nan", "normal", "diverged", 8.20), ("growth", "normal", "growth", None), ("tmax", "normal", None, None)])
def test_replay_at_decimations_1_to_16(kind, preset, verdict, t_ns):  # spec 6.3; a faster PC logs energy sparser
    rec = trace(kind)
    got = [stop_rule(replace(rec, te=rec.te[::d], e=rec.e[::d]), 0, preset, EXC) for d in range(1, 17)]
    assert {v and v.kind for v in got} == {verdict}
    if t_ns:
        assert {v.t for v in got} == {got[0].t} and got[0].t == pytest.approx(t_ns * 1e-9, abs=0.05e-9)


def prefix(rec, n):
    seen = rec.te <= rec.t_u[n - 1]
    return Records(rec.t_u[:n], rec.u[:, :n], rec.t_i[:n], rec.i[:, :n], rec.te[seen], rec.e[seen])


@pytest.mark.parametrize("chunk", [4, 64])
def test_polls_find_the_cut_of_the_whole_record(chunk):  # S does not depend on the stop latency (spec 6.3)
    rec = trace("converge")
    first = next(v for n in range(chunk, len(rec.t_u) + chunk, chunk)
                 if (v := stop_rule(prefix(rec, min(n, len(rec.t_u))), 0, "normal", EXC)))
    assert first == stop_rule(rec, 0, "normal", EXC) and stop_rule(prefix(rec, 1), 0, "normal", EXC) is None


def test_no_growth_before_the_pulse_ends():  # armed only after 2·t0
    rec = trace("converge")
    early = rec.te < 2 * EXC["t0"]
    dip = np.where(early, np.geomspace(1e-9, 1.0, len(rec.e)), rec.e)  # a deep dip inside the pulse: an unarmed
    assert stop_rule(replace(rec, e=dip), 0, "normal", EXC).kind == "converged"  # running minimum flags growth at 2.26 ns


def test_growth_rise_is_the_statistic_the_stop_rule_compares():  # D-38
    assert growth_rise(trace("growth"), EXC["t0"]) >= GROWTH_DB > 10 > growth_rise(trace("converge"), EXC["t0"])


def test_an_antennas_flat_window_counts_20_periods_of_f0():  # design 5.4
    exc = {"f1": 1.84e9, "f2": 2.99e9, "t0": 9 / (math.pi * 1.15e9)}
    rec = trace("flat", 1, 0, 1.84e9, 2.99e9)
    assert round(stop_rule(rec, 0, "normal", exc).t * 1e9, 3) == 17.179  # v1's 5 ns
    v = stop_rule(rec, 0, "normal", {**exc, "flat_s": flat_window(2.44175e9)})
    assert (v.kind, round(v.t * 1e9, 3)) == ("flat", 20.377)
    assert (flat_window(5e9), flat_window(915e6)) == (5e-9, pytest.approx(21.858e-9, rel=1e-4))


F_MAX = 10e9
SI = dc_pulse(F_MAX, 30e-9, 2e-9)  # f1 0, window_s 2 ns, flat_s 5 ns


def far_end(delay, offset=0.0, dt=2e-12, t_end=30e-9):
    """A 2-port record of SI's pulse sent into a matched line at port 1 and arriving at port 2 `delay` later, half its
    size; `offset` a level that stays on port 1 after the pulse, a charge its port cannot drain. Its log energy is held
    at 1, as openEMS's field energy under the DC pulse hardly decays (design 5.4; r1: −1.43 dB in 30 ns): the ports'
    own power falls to 0 between the pulses, which the growth detector would read as growth."""
    def pulse(t):
        return np.exp(-(2 * math.pi * F_MAX * t / 3 - 3) ** 2) * (t < 2 * SI["t0"])

    t_u = np.arange(0, t_end, dt)
    t_i = t_u + dt / 2
    u = np.array([pulse(t_u) + offset * (t_u > 2 * SI["t0"]), 0.5 * pulse(t_u - delay)])
    i = np.array([pulse(t_i), -0.5 * pulse(t_i - delay)]) / Z0
    return Records(t_u, u, t_i, i, t_u, np.ones_like(t_u))


def test_a_pulse_still_travelling_on_a_long_line_never_reads_as_converged():  # design 5.4; Review Focus 5
    rec = far_end(5e-9)  # 5 ns one way: a 10 ns round trip
    early = stop_rule(rec, 0, "normal", SI)  # the 2 ns window: converged at 2.27 ns, before port 2 sees anything
    assert early.kind == "converged" and early.t < 5e-9
    late = stop_rule(rec, 0, "normal", dc_pulse(F_MAX, 30e-9, stop_window(10e-9)))  # 15 ns, its flat window 18 ns
    assert late.kind == "converged" and 20e-9 < late.t < 21e-9  # 20.26 ns: the far end's pulse has left the window


def test_a_port_level_the_dc_pulse_leaves_behind_ends_flat_not_converged():  # design 5.4; Review Focus 5
    v = stop_rule(far_end(1e-9, offset=1e-2), 0, "normal", SI)  # a floating charge holding 1 % on port 1
    assert (v.kind, round(v.residual_db)) == ("flat", -43) and v.t < 10e-9  # 8.248 ns: S kept, flagged
