# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest
import shapely
from shapely.geometry import Point, box

from kicad_rf_studio.core.geometry.copper import copper_pieces
from kicad_rf_studio.core.geometry.mask import mask_model, smeared_epsilon
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.stackup import kicad_default

FIX = Path(__file__).parent / "fixtures"
T = {"F.Cu": .035, "B.Cu": .035}
BIG = box(-1000, -1000, 1000, 1000)  # a crop that holds every test board


def model(b, side="F", zs=None):
    """`b`'s mask on `side` over BIG, with its own stackup unless `zs` is given."""
    zs = zs or zstack(b.stackup, b.copper_layers)
    return mask_model(b, copper_pieces(b, BIG, T)[0], zs, BIG, side)


def test_smeared_epsilon():
    assert smeared_epsilon(0.010, 3.3, 0.025) == pytest.approx((0.033 + 0.015) / 0.025)
    assert smeared_epsilon(0.010, 3.3, 0.010) == pytest.approx(3.3)
    with pytest.raises(ValueError):
        smeared_epsilon(0.02, 3.3, 0.01)


def test_openings_are_honoured():
    # R-P2-5: lpf915's pads open its masks (J1.1 among them); coupon_gcpw_pads has no J1 and opens its whole board.
    # Task 5 ruling: the gap fill is on the 1e-6 mm grid, up to 0.7e-6 mm off an arc pad's outline, so it is checked
    # against each pad less one grid step
    b = load_board(FIX / "lpf915.kicad_pcb")
    for side in "FB":
        m = model(b, side)
        for pad in [p.polygon for p in b.all_pads() if side in p.mask_sides]:
            assert m.coat.intersection(pad.buffer(-0.01)).area == 0
            assert m.gap_fill.intersection(pad.buffer(-1e-6)).area < 1e-9


def test_gap_fill_is_between_conductors():
    # coupon_gcpw_masked: the 0.6 mm LINE at y = -100 and the F.Cu GND pours 0.1505 mm either side, all under the mask
    b = load_board(FIX / "coupon_gcpw_masked.kicad_pcb")
    pieces, _ = copper_pieces(b, BIG, T)
    m = mask_model(b, pieces, zstack(b.stackup, b.copper_layers), BIG, "F")
    (signal_piece,) = [pc for pc in pieces if (pc.layer, pc.net) == ("F.Cu", "LINE")]
    assert m.gap_fill.intersection(signal_piece.polygon).area < 1e-9
    assert m.gap_fill.contains(Point(110, -99.625)) and m.gap_fill.contains(Point(110, -100.375))  # the gaps' middles
    copper = shapely.union_all([pc.polygon for pc in pieces if pc.layer == "F.Cu"])
    assert m.gap_fill.intersection(copper).area < 1e-9 and m.coat.contains(copper)  # the coat lies on the copper too
    # the fill spans the outer copper's z-cell; the coat starts on its outer face (Task 5 ruling: on B it runs down)
    assert (m.side, m.z_fill, m.z_coat0) == ("F", (0.745, 0.78), 0.78)
    m = model(b, "B")
    assert (m.side, m.z_fill, m.z_coat0) == ("B", (0.0, 0.035), 0.0)


def test_mask_ends_at_the_board_edge():
    # Task 5 ruling: the mask lies on the board, so the crop is cut to the outline. coupon_gcpw_pads opens its whole
    # board (mask-free by construction) and has no mask at all; its masked twin is coated all over, to the edge
    bare, masked = (load_board(FIX / f"{name}.kicad_pcb") for name in ("coupon_gcpw_pads", "coupon_gcpw_masked"))
    m = model(bare)
    assert m.coat.is_empty and m.gap_fill.is_empty
    assert model(masked).coat.symmetric_difference(masked.outline).area < 1e-9


def test_mask_hash_input_is_order_independent(mini_board):
    # two 1 mm pads 0.2 mm apart, whose 0.2 mm margins merge their openings, and a track of another net under the mask
    pads = ['(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask") (net "A") (uuid "p1"))',
            '(pad "2" smd rect (at 1.2 0) (size 1 1) (layers "F.Cu" "F.Mask") (net "A") (uuid "p2"))']
    track = '(segment (start -3 2) (end 3 2) (width 0.5) (layer "F.Cu") (net "B") (uuid "t"))'
    zs = zstack(kicad_default(0.8), ("F.Cu", "B.Cu"))

    def board_with_pads_in_order(i, j):
        fp = f'(footprint "Lib:X" (layer "F.Cu") (uuid "f") (at 0 0) (property "Reference" "U1") {pads[i]} {pads[j]})'
        return mini_board(fp + track, clearance=0.2)

    a, b_ = (model(board_with_pads_in_order(i, j), zs=zs) for i, j in ((0, 1), (1, 0)))
    assert a.coat.wkb == b_.coat.wkb and a.gap_fill.wkb == b_.gap_fill.wkb
    assert len(a.coat.geoms[0].interiors) == 1 and a.gap_fill.area < a.coat.area  # one opening; the track is no gap
    # GEOS unions these the same in either order, so the hash input is checked as such too: on the grid, normalised
    for g in (a.coat, a.gap_fill):
        xy = shapely.get_coordinates(g)
        assert g.equals_exact(shapely.normalize(g), 0) and (xy == xy.round(6)).all()


def test_default_mask_values(mini_board):
    # a stackup mask layer without values falls back to 10 µm, εr 3.3; one with values keeps them; no B.Mask, no mask
    def stackup(mask):
        layers = [("F.Mask", "Top Solder Mask", mask), ("F.Cu", "copper", "(thickness 0.035)"),
                  ("dielectric 1", "core", "(thickness 0.71)"), ("B.Cu", "copper", "(thickness 0.035)")]
        return '(stackup ' + ''.join(f'(layer "{n}" (type "{t}") {v})' for n, t, v in layers) + ')'

    b = mini_board(stackup=stackup(""))
    m = model(b)
    assert (m.t_m, m.eps_m) == (0.010, 3.3) and model(b, "B") is None
    m = model(mini_board(stackup=stackup("(thickness 0.02) (epsilon_r 3.8)")))
    assert (m.t_m, m.eps_m) == (0.02, 3.8)
