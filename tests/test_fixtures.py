# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import pytest

from kicad_rf_studio.core.kicad.sexpr import atom, child, children, parse, repair

FIX = Path(__file__).parent / "fixtures"
NAMES = ["lpf915", "lpf915-45", "coupon_ms", "coupon_ms_masked", "coupon_gcpw", "coupon_gcpw_masked",
         "coupon_gcpw_pads", "coupon_dense", "coupon_gcpw_45", "coupon_gcpw_arc", "pads_zoo", "ifa2g4", "ifa2g4_pi",
         "meander915", "ifa2g4_pi_shift", "ifa2g4_pi_dxp", "ifa2g4_pi_dxm", "ifa2g4_pi_pour", "usb2_hs", "usb2_hs_neck",
         "usb2_hs_gap", "usb2_hs_45", "qspi_clk", "p4b_ms90", "p4b_ms100", "p4b_sl90", "p4b_ms90_45", "p4b_ms100_45",
         "p4b_ms90_vic", "p4b_ms90_cut", "p4c_l90", "p4c_step75", "p4c_step35", "si_pad_coupon", "si_pad_coupon_tall",
         "si_line100", "p4e_shift", "p4e_gapp", "p4e_gapm", "p4e_null", "p4e_vshift", "p4e_shift3", "p4e_gapp3",
         "p4e_gapm3", "p4e_vshift3"]


@pytest.mark.parametrize("name", NAMES)
def test_fixture_parses_and_has_pad_truth(name):
    root = parse(repair((FIX / f"{name}.kicad_pcb").read_text(encoding="utf-8"))[0])
    assert root[0] == "kicad_pcb" and int(atom(root, "version")) >= 20241229
    truth = json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8"))
    uuids = {atom(p, "uuid") for fp in children(root, "footprint") for p in children(fp, "pad")}
    assert set(truth) == uuids
    # later readers rely on every board having a stackup and an outline
    assert child(child(root, "setup"), "stackup") is not None
    assert any(atom(g, "layer") == "Edge.Cuts" for g in children(root, "gr_rect"))
