# SPDX-License-Identifier: GPL-3.0-or-later
import json

import golden_v1


def test_v1_builds_and_writes_byte_for_byte_what_it_did_at_4e5edda(tmp_path, monkeypatch):  # Stage 3 design 3, 4; RF 4
    monkeypatch.chdir(tmp_path)  # digests() works in relative paths, so no byte holds this machine's folders
    golden = json.loads(golden_v1.GOLDEN.read_text(encoding="utf-8"))
    now = golden_v1.digests()
    assert set(now["models"]) == {"lpf915", "lpf915-45", "coupon_gcpw_pads", "calibration"}
    assert "verify" in now["models"]["lpf915"]
    assert now["models"] == golden["models"]  # a v1 model spec, its hash, verify's model, project.json or new's lines moved
    assert set(now["outputs"]) == {"lpf915", "coupon_gcpw_pads"}
    if golden_v1.env() == golden["env"]:  # ponytail: the output bytes are the recording machine's (golden_v1.env)
        assert now["outputs"] == golden["outputs"]  # a v1 results/ file or result line moved
