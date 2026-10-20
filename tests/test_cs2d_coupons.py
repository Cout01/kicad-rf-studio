# SPDX-License-Identifier: GPL-3.0-or-later
"""CI tier (a) (spec 9.1): the ported KiCad line formulas pinned to KiCad 9's line calculator, and cs2d against them on
the mask-free coupons, through the full pipeline."""
from pathlib import Path

import pytest
from shapely.geometry import box

from kicad_lines import cpwg, microstrip
from kicad_rf_studio.core.cs2d import solve
from kicad_rf_studio.core.geometry.copper import copper_pieces
from kicad_rf_studio.core.geometry.mask import mask_model
from kicad_rf_studio.core.geometry.sections import cross_section, sections
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import load_board

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
BIG = box(-1000, -1000, 1000, 1000)  # a crop that holds every coupon

# Read by the owner from KiCad 9's PCB Calculator (TransLine), ledger R-P2-11 to R-P2-13. Inputs common to all three:
# εr 4.5, H 0.76 mm, T 0.035 mm, f 1 MHz, ρ 1.72e-8 Ω·m, roughness 0, μr 1 (tan δ does not enter Z0 or εeff).
KICAD_MS_Z, KICAD_MS_E = 51.0627, 3.30392  # microstrip W 1.35 mm, no cover: H(top) 1000 cm (the port's ht = 1e20)
KICAD_MS_COVER_Z, KICAD_MS_COVER_E = 52.3843, 3.13931  # the same microstrip under a cover, H(top) 2 mm (ht = 2.0)
KICAD_CPWG_Z, KICAD_CPWG_E = 52.2403, 2.36716  # coplanar wave guide with ground plane, W 0.6 mm, S 0.15 mm


def coupon_cross_section(name, mask):
    """The section of `name`'s LINE and its cross-section in mask mode `mask`, through the pipeline: the board, its
    z-stack, its copper pieces, its section (cut, width and gap as `sections` finds them) and the cut across it."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    zs = zstack(b.stackup, b.copper_layers)
    pieces, _ = copper_pieces(b, BIG, {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.kind == "copper"})
    (sec,), _ = sections(b, ("LINE",), pieces)
    return sec, cross_section(sec, pieces, zs, mask_model(b, pieces, zs, BIG, "F"), mask)


def coupon_stackup_values(name):
    """h, t and εr as `name`'s stackup gives them: its dielectric and the copper on it (the coupons have 2 layers)."""
    layers = load_board(FIX / f"{name}.kicad_pcb").stackup.layers
    cu, d = (next(x for x in layers if x.kind == kind) for kind in ("copper", "dielectric"))
    return d.thickness, cu.thickness, d.epsilon_r


def test_kicad_microstrip_reference_point():  # values read from KiCad 9's line calculator, same inputs
    z, e = microstrip(1.35, 0.76, 0.035, 4.5)
    assert z == pytest.approx(KICAD_MS_Z, rel=1e-3) and e == pytest.approx(KICAD_MS_E, rel=1e-3)


def test_kicad_microstrip_cover_reference_point():  # R-P2-11: KiCad's cover terms, a cover 1.24 mm over the strip
    z, e = microstrip(1.35, 0.76, 0.035, 4.5, ht=2.0)
    assert z == pytest.approx(KICAD_MS_COVER_Z, rel=1e-3) and e == pytest.approx(KICAD_MS_COVER_E, rel=1e-3)


def test_kicad_microstrip_cover_at_or_under_the_substrate_raises():  # R-P2-12
    # KiCad's own reading at H(top) = 0 (63.98 Ω, εeff 2.10) is no test vector: its cover factor turns to −1 there
    for ht in (0.0, 0.76):
        with pytest.raises(ValueError, match="cover"):
            microstrip(1.35, 0.76, 0.035, 4.5, ht=ht)


def test_kicad_cpwg_reference_point():
    z, e = cpwg(0.6, 0.15, 0.76, 0.035, 4.5)
    assert z == pytest.approx(KICAD_CPWG_Z, rel=1e-3) and e == pytest.approx(KICAD_CPWG_E, rel=1e-3)


# Task 8 ruling: on 35 µm copper KiCad's CPWG formula narrows each gap by 1.25t/π·(1 + ln(4πw/t)) and reads Z0 over
# cs2d (Task 7 ruling); coupon_gcpw's cs2d is 3.1 % under it, so the GCPW coupon takes spec 9.2's 5 % budget.
@pytest.mark.parametrize("name,formula,tol", [("coupon_ms", "ms", 0.02), ("coupon_gcpw", "cpwg", 0.05)])
def test_cs2d_matches_kicad_on_coupons(name, formula, tol):  # CI tier (a): mask-free, through the full pipeline
    sec, cs = coupon_cross_section(name, mask="none")
    h, t, er = coupon_stackup_values(name)
    z, _ = microstrip(sec.width, h, t, er) if formula == "ms" else cpwg(sec.width, sec.gap, h, t, er)
    assert solve(cs).z0 == pytest.approx(z, rel=tol)


def test_notice_lists_third_party():
    text = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "SmoothMeshLines" in text and "LGPL-3.0-or-later" in text and "KiCad" in text and "GPL" in text
