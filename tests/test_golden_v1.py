# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import golden_s5
import golden_v1
import p3a
import pytest

GOLDEN = json.loads(golden_v1.GOLDEN.read_text(encoding="utf-8"))
SHARED = json.loads(golden_s5.GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    home = os.getcwd()
    # digests() works in relative paths, so no byte holds this machine's folders
    os.chdir(tmp_path_factory.mktemp("golden"))
    try:
        return golden_v1.digests()
    finally:
        os.chdir(home)


@pytest.fixture(scope="module")
def shared(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("shared"))  # relative paths only, as `now`
    try:
        return golden_s5.shared_v1()
    finally:
        os.chdir(home)


def test_v1_builds_byte_for_byte_what_it_did_at_4e5edda(now):  # Stage 3 design 3, 4; RF 4
    assert set(now["models"]) == {"lpf915", "lpf915-45", "coupon_gcpw_pads", "calibration"}
    assert "verify" in now["models"]["lpf915"]
    # a v1 model spec, its hash, verify's model, project.json or new's lines moved
    assert now["models"] == GOLDEN["models"]
    assert set(now["outputs"]) == {"lpf915", "coupon_gcpw_pads"}


def test_v1_writes_byte_for_byte_what_it_did_at_4e5edda(now):  # Stage 3 design 3, 4; RF 4
    # ponytail: the output bytes are the recording machine's (golden_v1.env), which leaves out Pillow, summary.png's
    # encoder; its version joins env() at the next ruled re-recording
    if golden_v1.env() != GOLDEN["env"]:
        pytest.skip("v1's output pins compare only on the env that recorded them (tools/golden_v1.py env())")
    assert now["outputs"] == GOLDEN["outputs"]  # a v1 results/ file or result line moved


def test_v1s_shared_outputs_stand_as_they_were_at_a87bcc1(shared):  # Stage 5 design 8 risk 11; plan 3 ruling 2
    pins = SHARED["v1"]
    assert set(shared["cases"]) == set(golden_v1.CASES) and set(shared["run"]) == {"lpf915"}
    assert {"load", "cost", "csx", "csx_verify"} <= set(shared["cases"]["lpf915"])
    assert set(shared["run"]["lpf915"]) == {"cost", "run", "verify", "files"} and set(shared["p3a"]) == set(p3a.STEPS)
    assert len(shared["stop"]) == 8 and all(len(v) == 3 for v in shared["stop"].values())
    # a load note, a cost line, a CSX call, a stop verdict or a P3-A spec moved
    assert {k: v for k, v in shared.items() if k != "run"} == {k: v for k, v in pins.items() if k != "run"}
    if golden_v1.env() != SHARED["env"]:
        pytest.skip("the run pins compare only on the env that recorded them (golden_v1.env())")
    assert shared["run"] == pins["run"]  # an exit, a record, an event line, a job file or a results/ file moved
