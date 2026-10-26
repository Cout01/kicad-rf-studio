# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import p0
from kicad_rf_studio.stoprule import stop_rule

TRACES = sorted((Path(__file__).parent / "fixtures" / "traces").glob("*.npz"))


def test_real_traces_are_committed():  # spec 9.1, D-40
    assert [p.name for p in TRACES] == [*(f"coupon_gcpw_pads-k{k}.npz" for k in (1, 2)),
                                        *(f"lpf915-k{k}.npz" for k in range(1, 7))]
    assert all(p.stat().st_size <= p0.TRACE_BYTES for p in TRACES)


@pytest.mark.parametrize("path", TRACES, ids=lambda p: p.stem)
def test_real_traces_replay_to_their_live_verdict_at_decimations_1_to_16(path):  # spec 6.3, D-40
    rec, k, exc, t_cut = p0.load_trace(path)
    step = float(np.diff(rec.te).max())
    for d in range(1, 17):  # a faster PC logs its energy sparser
        v = stop_rule(replace(rec, te=rec.te[::d], e=rec.e[::d]), k, "normal", exc)
        assert v.kind == "converged" and abs(v.t - t_cut) <= (d - 1) * step
