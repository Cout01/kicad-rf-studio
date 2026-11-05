# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio.core.model.spec import dc_pulse
from kicad_rf_studio.stoprule import (GROWTH_DB, RING_CEILING, Z0, Records, ceiling, flat_window, growth_rise, ring,
                                      stop_rule, stop_window)
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


RING = json.loads((Path(__file__).parent / "fixtures" / "ring" / "plane_gap.json").read_text(encoding="utf-8"))
SI9 = dc_pulse(F_MAX, 9e-9, 2e-9)  # T_max 9 ns: its ceiling 36 ns


def decay(slope_db_ns, dt=0.04e-9):  # a residual from 6 to 40 ns, -45 dB at 9 ns
    t = np.arange(6e-9, 40e-9, dt)
    return t, -45.0 + slope_db_ns * 1e9 * (t - 9e-9)


def test_the_ring_rule_runs_on_while_the_residual_falls_fast_enough():  # ruling T-2; Review Focus 4
    t, r = decay(-1.0)  # -60 dB at 24 ns, under the ceiling
    assert ring(t, r, -60.0, 9e-9) == math.inf
    for slope in (-0.5, -0.2, 0.0, 0.3):  # -60 dB at 39 ns, past the ceiling; slower than 0.3 dB/ns; flat; rising
        t, r = decay(slope)
        assert ring(t, r, -60.0, 9e-9) == t[np.argmax(t >= 9e-9)]  # T_max, as today
    assert ring(t[t < 9e-9], r[t < 9e-9], -60.0, 9e-9) == math.inf  # nothing past T_max yet
    assert RING_CEILING == 4 and ceiling(SI9) == pytest.approx(36e-9) and ceiling({**EXC, "t_max": 5e-9}) == 5e-9


def test_the_ring_rule_lets_every_plane_gap_job_run_to_its_convergence():  # ruling T-2: plan 3's 14 jobs past T_max
    assert len(RING["jobs"]) == 14
    for job in RING["jobs"]:  # slopes -0.68 to -2.09 dB/ns, the latest projection 23.9 ns
        t, r = np.array(job["t_ns"]) * 1e-9, np.array(job["residual_db"])
        assert (t >= RING["t_max_s"]).sum() >= 300, (job["run"], job["port"])
        assert ring(t, r, RING["level_db"], RING["t_max_s"]) == math.inf, (job["run"], job["port"])


def tail(slope_db_ns, dt=2e-12, t_end=12e-9):
    """SI9's pulse on port 1, then a level on it falling `slope_db_ns` dB/ns from -40 dB at 2 ns: a ringing plane."""
    t_u = np.arange(0, t_end, dt)
    pulse = np.exp(-(2 * math.pi * F_MAX * t_u / 3 - 3) ** 2) * (t_u < 2 * SI9["t0"])
    level = 10 ** ((-40 + slope_db_ns * 1e9 * (t_u - 2e-9)) / 20) * (t_u > 2 * SI9["t0"])
    zero = np.zeros_like(t_u)
    return Records(t_u, np.array([pulse + level, zero]), t_u + dt / 2, np.array([pulse, zero]) / Z0, t_u,
                   np.ones_like(t_u))


def test_an_si_job_whose_planes_ring_slowly_ends_at_t_max_and_a_v1_one_never_by_the_ring():  # T-2; Review Focus 4
    v = stop_rule(tail(-0.25), 0, "normal", SI9)  # 0.25 dB/ns: slower than 0.3, and 1.25 dB over 5 ns, not flat
    assert v.kind == "t_max" and v.t == pytest.approx(9e-9, abs=2e-12)
    assert stop_rule(tail(-1.0), 0, "normal", SI9) is None  # fast enough: it runs on toward 36 ns
    v1 = {key: SI9[key] for key in ("f1", "f2", "t0", "t_max", "expr")}  # no window_s: no SI pulse
    assert stop_rule(tail(-0.25), 0, "normal", v1) is None
