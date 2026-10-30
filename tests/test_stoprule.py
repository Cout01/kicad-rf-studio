# SPDX-License-Identifier: GPL-3.0-or-later
import math
from dataclasses import replace

import numpy as np
import pytest

from kicad_rf_studio.stoprule import GROWTH_DB, Records, flat_window, growth_rise, stop_rule
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
