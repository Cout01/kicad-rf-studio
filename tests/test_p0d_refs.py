# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import numpy as np
import pytest

import p0
import p0a
import p0d
from kicad_rf_studio.core.model.spec import spec_hash

REFS = Path(__file__).parent / "fixtures" / "p0d"
TRACES = Path(__file__).parent / "fixtures" / "traces"


def test_the_windows_references_are_committed_with_generic_members():  # D-48
    for name in p0d.MODELS:
        with np.load(REFS / f"{name}.npz") as z:
            extra = {"z0", "eeff"} if name in p0a.COUPONS else set()
            assert set(z.files) == {"f", "S", "t_cut", "spec_hash"} | extra, name


@pytest.mark.xfail(strict=True, reason="plan 6's slot role moved the P0 models; Task 10 regenerates tests/fixtures/p0d")
def test_the_references_are_the_models_p0d_builds_here(tmp_path):  # D-47: CI compares the same models
    p0d.models(tmp_path)
    for name in p0d.MODELS:
        built = spec_hash(json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8")))
        with np.load(REFS / f"{name}.npz") as z:
            assert str(z["spec_hash"]) == built, name


@pytest.mark.parametrize("name", ["coupon_gcpw_pads", "lpf915"])
def test_the_draft_replay_of_the_committed_traces_reproduces_the_references(name):  # D-48: exact by causality
    traces = [p0.load_trace(p) for p in sorted(TRACES.glob(f"{name}-k*.npz"))]
    with np.load(REFS / f"{name}.npz") as ref:
        s, t_cut = p0.s_of(traces, ref["f"], "draft")
        assert np.array_equal(t_cut, ref["t_cut"]) and np.abs(s - ref["S"]).max() <= 1e-12
