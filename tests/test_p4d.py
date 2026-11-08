# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np
import pytest

import p4
import p4d
from kicad_rf_studio import runs
from kicad_rf_studio.core.project import load_project
from test_cli_si import si_project
from test_p4 import gates  # noqa: F401 (the fixture)

USB_DC = np.array([[1 / 3, 0, 2 / 3, 0, 0, 0, 2 / 3, 0], [0, 1 / 3, 0, 2 / 3, 0, 0, 0, 2 / 3],
                   [2 / 3, 0, 1 / 3, 0, 0, 0, 2 / 3, 0], [0, 2 / 3, 0, 1 / 3, 0, 0, 0, 2 / 3], [0, 0, 0, 0, 0, 1, 0, 0],
                   [0, 0, 0, 0, 1, 0, 0, 0], [2 / 3, 0, 2 / 3, 0, 0, 0, 1 / 3, 0], [0, 2 / 3, 0, 2 / 3, 0, 0, 0, 1 / 3]])


def test_the_usb_fixtures_dc_reference_is_its_copper_projector(tmp_path):  # D-2: S = 2P - I
    names, s = p4d.dc_s(si_project(tmp_path / "u"))
    assert names == ["P1", "P2", "P3", "P4", "P5", "P6", "R1", "R2"]
    assert np.abs(s) == pytest.approx(np.abs(USB_DC), abs=1e-12)


def test_mlines_dielectric_loss_is_the_reference():  # D-1, D-3: t 35 um, PEC copper
    assert p4d.il_ref(np.array([1e8, 1e9, 5e9, 10e9])) == pytest.approx([0.0279, 0.2827, 1.4267, 2.8679], abs=1e-4)


def test_the_insertion_loss_metric_corrects_the_mismatch():
    s = np.zeros((1, 2, 2), complex)
    s[0, 0, 0], s[0, 1, 0] = 0.3, np.sqrt(0.9 * (1 - 0.09))
    assert p4d.il_metric(s)[0] == pytest.approx(-10 * np.log10(0.9))


def test_the_debye_weight_and_the_usb_slowdown():  # design 5.3; D-3
    assert p4d.weight(200.0, 50.0, 0.28) == pytest.approx(1 + 3 / 0.28)  # R 4 on a 28 % share
    assert p4d.slowdown(11.714, 0.281) == pytest.approx(1 + 0.281 * 10.714)


def test_the_p4d_decisions():  # design 5.11's fallbacks; D-3, D-5
    def m(short=1.0, tall=1.0, dc=0.001, accurate=True, dc_loss=0.0, w=11.0, f_usb=0.281, measured=None, invalid=()):
        return {"ports": {"si_pad_coupon": {"h": 50.0, "v": 50.0 * short},
                          "si_pad_coupon_tall": {"h": 48.0, "v": 48.0 * tall}},
                "dc": {"x": dc}, "invalid": list(invalid),
                "debye": {"il_ok": accurate, "dc_loss": dc_loss, "w": w, "f_usb": f_usb, "measured": measured}}
    d = p4d.decide(m())
    assert (d["port"], d["dielectric"], d["verdict"]["value"]) == ("kept", "lossless", "pass")  # 3.8x predicted
    assert p4d.decide(m(tall=1.0151))["port"] == "graded" and p4d.decide(m(short=1.0151))["port"] == "ruling"
    assert p4d.decide(m(dc=0.0101))["verdict"]["value"] == "fail"  # a lossless DC miss: the controller's
    near = p4d.decide(m(w=2.4))  # 1.39 predicted: inside [1.25, 1.75], so usb2_hs runs with Debye
    assert (near["dielectric"], near["debye"]["run_usb"]) == (None, True)
    assert p4d.decide(m(w=2.4, measured=1.5))["dielectric"] == "debye"
    assert p4d.decide(m(w=2.4, measured=1.51))["dielectric"] == "lossless"
    assert p4d.decide(m(w=1.5))["dielectric"] == "debye"  # 1.14 predicted: outside, the prediction decides
    assert p4d.decide(m(w=1.5, accurate=False))["dielectric"] == "lossless"
    assert p4d.decide(m(w=1.5, dc_loss=0.0051))["dielectric"] == "lossless"
    assert p4d.decide(m(invalid=["si_line100-debye"]))["verdict"]["fails"] == ["si_line100-debye: valid"]
    tall = p4d.decide(m(invalid=["si_pad_coupon_tall-v"]))  # R-5: a pad coupon's invalid v run is its port's miss
    assert (tall["port"], tall["dielectric"], tall["verdict"]) == ("graded", "lossless", {"value": "fallback",
                                                                                          "fails": []})
    short = p4d.decide(m(invalid=["si_pad_coupon-v"]))
    assert (short["port"], short["verdict"]) == ("ruling", {"value": "fail", "fails": ["si_pad_coupon: port"]})
    assert p4d.decide(m(invalid=["si_line100"]))["verdict"] == {"value": "fail", "fails": ["si_line100: valid"]}


def test_the_committed_references_hold_the_curve_and_the_projectors():  # G-1; D-2: judged against them
    refs = json.loads(p4d.REFERENCES.read_text(encoding="utf-8"))
    assert refs["il_ref"]["db"][-1] == pytest.approx(2.8679, abs=1e-3) and refs["il_ref"]["f_hz"][0] >= 1e8
    assert set(refs["dc"]) == {"si_pad_coupon", "si_pad_coupon_tall", "si_line100", "usb2_hs", "usb2_hs_neck",
                               "usb2_hs_gap"}
    assert np.abs(refs["dc"]["usb2_hs"]["s"]) == pytest.approx(np.abs(USB_DC), abs=1e-12)


def test_p4d_runs_its_steps_and_writes_its_report(gates, monkeypatch):  # design 5.11: the tool on the network fake
    monkeypatch.setattr(p4, "RULE", "dfill")  # as P4-D ran: its usb2_hs Debye model holds no λ/40 cell (p4.settings)
    steps = "si_pad_coupon-h,si_pad_coupon-v,si_line100,si_line100-debye,si_line100-n3"
    assert p4d.main(["--out", str(gates), "--steps", steps]) == 1  # no such step
    vertical = load_project(gates / "projects" / "si_pad_coupon-n2-dfill-v" / "project.json")["ports"]
    assert {(q["rule"], q["reference"]["plane"]) for q in vertical} == {("plane", "In1.Cu")}
    with pytest.raises(SystemExit, match="never regenerated"):
        p4d.main(["--references"])
    assert p4d.main(["--out", str(gates)]) == 0
    text = (gates / "p4d" / "p4d.json").read_text(encoding="utf-8")
    result = json.loads(text)
    assert sorted(result["runs"]) == ["si_line100", "si_line100-debye", "si_pad_coupon-h", "si_pad_coupon-v"]
    assert sorted(result["dc"]) == ["si_line100-n2-dfill", "si_pad_coupon-n2-dfill",
                                    "si_pad_coupon-n2-dfill-v"]  # no Debye
    assert result["port"] is None and result["verdict"]["value"] == "fail"  # the star network's DC point, 0.9025
    debye = result["debye"]
    assert {"w", "f_usb", "predicted", "measured", "il_ok", "il_worst", "dc_loss"} <= set(debye)
    assert (debye["w"], debye["il_ok"], debye["measured"]) == (1.0, False, None)  # one speed and one S, lossless or not
    assert '"reading"' not in text and '"project"' not in text
    md = (gates / "p4d" / "p4d.md").read_text(encoding="utf-8")
    assert md.startswith("## P4D-1 The ports") and "| v | v_valid | v_over_h |" in md  # R-5: the v run's validity
    name = p4.name("si_line100", dielectric="debye")  # P4-D's Debye step, run above
    m = p4.measure(gates, name)
    assert m["debye_cells"] > 0 and m["worst_s"] is not None
    monkeypatch.setattr(runs, "DEBYE_WEIGHT", 50.0)
    assert p4.measure(gates, name)["worst_s"] == m["worst_s"]  # the run's own Debye weight (G-2)
