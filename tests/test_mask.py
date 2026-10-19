# SPDX-License-Identifier: GPL-3.0-or-later
import math
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, box
from shapely.ops import unary_union

from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.mask import mask_openings

FIX = Path(__file__).parent / "fixtures"


def opening_hits(m, *polys): return [g for g in m.geoms if any(g.intersects(p) for p in polys)]


def test_web_between_0402_pads_is_kept():
    b = load_board(FIX / "lpf915.kicad_pcb")
    a, c = b.pads("C1.1")[0].polygon, b.pads("C1.2")[0].polygon
    hit = opening_hits(mask_openings(b, "F"), a)
    assert len(hit) == 1 and not hit[0].intersects(c)


def test_min_width_closes_narrow_webs():
    b = load_board(FIX / "lpf915.kicad_pcb")
    b.solder_mask_min_width = 0.6
    a, c = b.pads("C1.1")[0].polygon, b.pads("C1.2")[0].polygon
    assert any(g.intersects(a) and g.intersects(c) for g in mask_openings(b, "F").geoms)


def test_margin_precedence(mini_board):
    fp = ('(footprint "X:Y" (layer "F.Cu") (at 0 0) (property "Reference" "U9") (property "Value" "x") '
          '(solder_mask_margin 0.1) '
          '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask") (solder_mask_margin 0.05) (uuid "p1")) '
          '(pad "2" smd rect (at 5 0) (size 1 1) (layers "F.Cu" "F.Mask") (uuid "p2")))')
    m = mask_openings(mini_board(fp, clearance=0.2), "F")
    areas = sorted(g.area for g in m.geoms)
    assert areas == pytest.approx([1 + 4 * 0.05 + math.pi * 0.05**2, 1 + 4 * 0.1 + math.pi * 0.1**2], rel=1e-3)


# --- beyond the brief's three tests: the rules they leave open ---------------------------------------


def margin_of(m): return "" if m is None else f"(solder_mask_margin {m})"


def pad(number, x, layers='"F.Cu" "F.Mask"', margin=None, kind="smd"):
    """A 1 x 1 mm rectangular pad of U9 at (x, 0)."""
    return (f'(pad "{number}" {kind} rect (at {x} 0) (size 1 1) (layers {layers}) {margin_of(margin)} '
            f'(uuid "p{number}"))')


def footprint(*pads, margin=None, attr=""):
    """U9, at the origin, with its own `margin` and `attr` if given."""
    return ('(footprint "X:Y" (layer "F.Cu") (uuid "f1") (at 0 0) (property "Reference" "U9") (property "Value" "x") '
            f'{attr} {margin_of(margin)} {"".join(pads)})')


@pytest.mark.parametrize("attr", ["", "(attr smd dnp)"], ids=["fitted", "dnp"])
def test_a_pad_opens_the_masks_it_lists_and_no_others(mini_board, attr):
    hole = '(pad "6" np_thru_hole circle (at 15 0) (size 1 1) (drill 1) (layers "*.Cu" "*.Mask") (uuid "p6"))'
    b = mini_board(footprint(
        pad(1, 0), pad(2, 3, '"B.Cu" "B.Mask"'), pad(3, 6, '"F.Cu" "B.Cu" "F.Mask" "B.Mask"'),
        pad(4, 9, '"F.Cu" "F.Paste"'),  # copper, but it lists no mask
        pad(5, 12, '"F.Paste"'),  # paste only: no copper either
        hole,  # the hole covers its whole pad, so it has no copper, yet the file lists both masks
        attr=attr))
    fp = b.footprints["U9"]
    assert [p.number for p in fp.pads if not p.layers] == ["5", "6"] and fp.dnp is bool(attr)

    def opened(side): return [p.number for p in fp.pads if opening_hits(mask_openings(b, side), p.polygon)]

    # the openings belong to the board, so a part left off (dnp) keeps its own
    assert opened("F") == ["1", "3", "6"] and opened("B") == ["2", "3", "6"]


@pytest.mark.parametrize("pad_margin, fp_margin, margin", [(0, 0.1, 0), (None, 0, 0), (None, None, 0.2)],
                         ids=["pad-zero", "footprint-zero", "board"])
def test_the_first_margin_that_is_set_applies_even_when_it_is_zero(mini_board, pad_margin, fp_margin, margin):
    b = mini_board(footprint(pad(1, 0, margin=pad_margin), margin=fp_margin), clearance=0.2)
    (m,) = mask_openings(b, "F").geoms
    assert m.area == pytest.approx(1 + 4 * margin + math.pi * margin**2, rel=1e-3)


@pytest.mark.parametrize("kind", ["smd", "thru_hole", "connect"])
def test_a_pad_with_no_copper_layer_takes_no_margin(mini_board, kind):
    """As in pcbnew, whatever the margins say. A copper pad beside it keeps the chain."""
    b = mini_board(footprint(pad(1, 0, '"F.Mask"', margin=0.05, kind=kind), pad(2, 3, margin=0.05), margin=0.1),
                   clearance=0.2)
    bare, copper = b.footprints["U9"].pads
    assert bare.layers == () and copper.layers == ("F.Cu",)
    m = mask_openings(b, "F")
    (own,) = opening_hits(m, bare.polygon)
    (grown,) = opening_hits(m, copper.polygon)
    assert own.symmetric_difference(bare.polygon).area < 1e-9  # exactly its own outline
    assert grown.area == pytest.approx(1 + 4 * 0.05 + math.pi * 0.05**2, rel=1e-3)  # the pad's 0.05, not 0.1 or 0.2


def test_a_hole_that_covers_its_pad_still_takes_the_margin(mini_board):
    """Its `layers` is empty, but the file lists copper, and pcbnew gives it the margin (here the footprint's 0.1)."""
    hole = '(pad "1" np_thru_hole circle (at 0 0) (size 1 1) (drill 1) (layers "*.Cu" "*.Mask") (uuid "p1"))'
    b = mini_board(footprint(hole, margin=0.1), clearance=0.2)
    assert b.footprints["U9"].pads[0].layers == ()
    (m,) = mask_openings(b, "F").geoms
    assert m.area == pytest.approx(math.pi * 0.6**2, rel=5e-3)  # a 1 mm circle grown by 0.1


@pytest.mark.parametrize("margin, area", [(-0.1, 0.8**2), (-0.6, 0)], ids=["shrinks", "vanishes"])
def test_a_negative_margin_shrinks_the_opening(mini_board, margin, area):
    m = mask_openings(mini_board(footprint(pad(1, 0, margin=margin))), "F")
    assert isinstance(m, MultiPolygon) and m.area == pytest.approx(area)


def test_mask_graphics_open_the_mask_as_drawn_and_merge_with_the_pads(mini_board):
    b = mini_board(footprint(pad(1, 0)), clearance=0.2)
    b.mask_graphics["F"] += [box(0.25, -0.25, 3, 0.25), box(10, 0, 11, 1)]  # one over the pad, one apart
    b.mask_graphics["B"] += [box(20, 0, 21, 1)]
    front = sorted(g.bounds for g in mask_openings(b, "F").geoms)
    assert front == [pytest.approx((-0.7, -0.7, 3, 0.7)), pytest.approx((10, 0, 11, 1))]  # the 0.2 mm is the pad's
    assert [g.bounds for g in mask_openings(b, "B").geoms] == [pytest.approx((20, 0, 21, 1))]
    assert [len(b.mask_graphics[s]) for s in "FB"] == [2, 1]  # the board's own lists are left as they were


@pytest.mark.parametrize("min_width, openings", [(0.3, 2), (0.5, 1)], ids=["web-wide-enough", "web-too-narrow"])
def test_min_width_closes_only_webs_narrower_than_it(mini_board, min_width, openings):
    b = mini_board(footprint(pad(1, 0), pad(2, 1.4)))  # 0.4 mm of mask between the pads
    b.solder_mask_min_width = min_width
    assert len(mask_openings(b, "F").geoms) == openings


@pytest.mark.parametrize("min_width", [0, 0.6])
@pytest.mark.parametrize("side", ["F", "B"])
def test_nothing_to_open_gives_an_empty_multipolygon(mini_board, side, min_width):
    b = mini_board("")
    b.solder_mask_min_width = min_width
    m = mask_openings(b, side)
    assert isinstance(m, MultiPolygon) and m.is_empty


def test_a_coupon_open_over_the_whole_board_and_its_masked_twin():
    bare, masked = (load_board(FIX / f"{name}.kicad_pcb") for name in ("coupon_ms", "coupon_ms_masked"))
    (whole,) = mask_openings(bare, "F").geoms
    assert whole.area == pytest.approx(bare.outline.area) and mask_openings(bare, "B").is_empty
    assert mask_openings(masked, "F").is_empty and mask_openings(masked, "B").is_empty


@pytest.mark.parametrize("side", ["F", "B"])
@pytest.mark.parametrize("name", ["lpf915", "pads_zoo"])
def test_with_no_margin_the_openings_are_the_pad_outlines_and_the_graphics(name, side):
    """Every kind of pad outline of the fixtures, on both sides, comes through the margin and the union unchanged."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    outlines = [p.polygon for fp in b.footprints.values() for p in fp.pads if side in p.mask_sides]
    got = mask_openings(b, side)
    assert got.is_valid and got.symmetric_difference(unary_union(outlines + b.mask_graphics[side])).area < 1e-9
