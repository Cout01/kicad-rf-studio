# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import golden_v1
import pytest

GOLDEN = json.loads(golden_v1.GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    home = os.getcwd()
    # digests() works in relative paths, so no byte holds this machine's folders
    os.chdir(tmp_path_factory.mktemp("golden"))
    try:
        return golden_v1.digests()
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
