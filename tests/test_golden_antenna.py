# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import golden_antenna
import golden_v1
import pytest

GOLDEN = json.loads(golden_antenna.GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("golden_antenna"))  # relative paths only, so no byte holds this machine's folders
    try:
        return golden_antenna.digests()
    finally:
        os.chdir(home)


def test_the_antennas_build_byte_for_byte_what_they_did_at_037bc4b(now):  # Stage 4 design 3, 4, 5.12 item 1
    assert set(now["models"]) == set(golden_antenna.BANDS) and "verify" in now["models"]["ifa2g4_pi"]
    # an antenna's model spec, its hash, the pi's verify model, project.json, new's lines or a blocking gate moved
    assert now["models"] == GOLDEN["models"]


def test_the_antennas_outputs_and_the_2d_readouts_are_byte_for_byte_what_they_were_at_037bc4b(now):  # design 3, 4
    assert set(now["outputs"]) == set(golden_antenna.BANDS) | set(golden_v1.CASES)
    assert set(now["outputs"]["ifa2g4"]) == {"readout", "layout.s1p", "farfield.csv", "antenna_summary.csv",
                                             "antenna_summary.png", "lines"}
    assert set(now["outputs"]["ifa2g4_pi"]) == {"readout", "layout.s4p", "chain.s1p", "antenna_summary.png", "lines"}
    assert all(set(now["outputs"][name]) == {"readout"} for name in golden_v1.CASES)  # v1's, which golden_v1 lacks
    # ponytail: the output bytes are the recording machine's (golden_v1.env), which leaves out Pillow, summary.png's
    # encoder; its version joins env() at the next ruled re-recording
    if golden_v1.env() != GOLDEN["env"]:
        pytest.skip("the antenna output pins compare only on the env that recorded them (golden_v1.env())")
    assert now["outputs"] == GOLDEN["outputs"]  # a results/ file, a result line or a 2D readout moved
