# SPDX-License-Identifier: GPL-3.0-or-later
import functools
import json
import math

import pytest
import shapely

from kicad_rf_studio import pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_si import FIX

PAIR90 = ["--start", "TP1.1", "--end", "TP2.1", "--interface", "usb2-hs", "--pair-with", "TP3.1:TP4.1"]
NET = ["--start", "TP1.1", "--end", "TP2.1", "--interface", "se50"]
USB = ["--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--pair", "--victim", "TP1.1:TP2.1"]
P4_NEW = {**{b: PAIR90 for b in ("p4b_ms90", "p4b_ms90_45", "p4b_ms90_cut", "p4b_sl90", "p4c_l90", "p4e_shift",
                                 "p4e_gapp", "p4e_gapm", "p4e_null", "p4e_shift3", "p4e_gapp3", "p4e_gapm3")},
          **{b: [*PAIR90, "--victim", "TP5.1:TP6.1"] for b in ("p4b_ms90_vic", "p4e_vshift", "p4e_vshift3")},
          **{b: [*PAIR90[:5], "100base-tx", *PAIR90[6:]] for b in ("p4b_ms100", "p4b_ms100_45")},
          **{b: NET for b in ("p4c_step75", "p4c_step35", "si_pad_coupon_tall", "si_line100")},
          "si_pad_coupon": ["--start", "U1.11", "--end", "U2.3", "--interface", "se50"],
          **{b: USB for b in ("usb2_hs", "usb2_hs_neck", "usb2_hs_gap")}}
# the architect's text replica through the product (cells at n 2 with new's max_cell, dt reference in s): ±10 %, ±5 %;
# p4b_sl90's is its own board's, generated again with ruling R-8's stitching grid
ESTIMATE = {"p4b_ms90": (1369368, 9.0894e-14), "p4b_ms100": (1339954, 8.9893e-14), "p4b_sl90": (5872338, 7.0840e-14),
            "p4b_ms90_45": (10122497, 8.6984e-14), "p4b_ms100_45": (9934463, 8.7257e-14),
            "p4b_ms90_vic": (1571724, 8.8960e-14), "p4b_ms90_cut": (1374758, 9.0894e-14),
            "p4c_l90": (1686608, 8.3873e-14), "p4c_step75": (1955330, 5.9104e-14), "p4c_step35": (1414490, 8.2747e-14),
            "si_pad_coupon": (1201200, 8.0901e-14), "si_pad_coupon_tall": (435418, 1.1064e-13),
            "si_line100": (1216138, 9.3604e-14), "p4e_shift": (1375374, 9.0888e-14), "p4e_gapp": (1351812, 9.2521e-14),
            "p4e_gapm": (1647052, 6.6392e-14), "p4e_null": (1369368, 9.0888e-14), "p4e_shift3": (1375374, 9.0888e-14),
            "p4e_gapp3": (1316700, 9.6952e-14), "p4e_gapm3": (1502732, 8.0539e-14),
            "p4e_vshift": (1578600, 8.8954e-14), "p4e_vshift3": (1578600, 8.8954e-14)}  # vic's, scaled as shift's
# Step 6: each board's (nx, ny, nz, max_cell_mm) at n 2, recorded once from the generated boards
LINES = {"p4b_ms100": (226, 77, 77, 0.433199), "p4b_ms100_45": (406, 317, 77, 0.433084),
         "p4b_ms90": (228, 78, 77, 0.429232), "p4b_ms90_45": (406, 323, 77, 0.429232),
         "p4b_ms90_cut": (226, 79, 77, 0.429232), "p4b_ms90_vic": (252, 81, 77, 0.429232),
         "p4b_sl90": (562, 129, 81, 0.361432), "p4c_l90": (148, 148, 77, 0.429232),
         "p4c_step35": (334, 55, 77, 0.413575), "p4c_step75": (338, 65, 89, 0.427164),
         "p4e_gapm": (242, 82, 83, 0.429232), "p4e_gapm3": (238, 82, 77, 0.429232),
         "p4e_gapp": (228, 77, 77, 0.429232), "p4e_gapp3": (228, 75, 77, 0.429232),
         "p4e_null": (228, 78, 77, 0.429232), "p4e_shift": (229, 78, 77, 0.429232),
         "p4e_shift3": (229, 78, 77, 0.429232), "p4e_vshift": (253, 81, 77, 0.429232),
         "p4e_vshift3": (253, 81, 77, 0.429232), "si_line100": (298, 53, 77, 0.427164),
         "si_pad_coupon": (195, 81, 77, 0.427164), "si_pad_coupon_tall": (166, 61, 43, 0.409006)}


def built(tmp_path, board, **edits):
    """The board's project by `new` with P4_NEW's arguments, at the gates' first settings (mesh n 2, lossless, LINES'
    λ/40 cell once recorded), so a default Task 16 moves leaves it as it is, then `edits` (mesh keys), and its model."""
    assert main(["new", str(FIX / f"{board}.kicad_pcb"), *P4_NEW[board], "-o", str(tmp_path / board)]) == 0
    pj = tmp_path / board / "project.json"
    d = load_project(pj)
    d["mesh"] |= {"n": 2, **({"max_cell_mm": LINES[board][3]} if board in LINES else {}), **edits}
    save_project(pj, {**d, "dielectric": "lossless"})
    project, board_, geom, notes = pipeline.load(pj)
    return project, board_, geom, notes, pipeline.build_model(project, board_, geom)


@pytest.fixture(scope="module")
def build(tmp_path_factory):
    """built() once a board for the module, at the gates' first settings."""
    return functools.cache(lambda board: built(tmp_path_factory.mktemp(board), board))


@pytest.mark.parametrize("board", sorted(ESTIMATE))
def test_each_p4_board_builds_unblocked_near_its_estimate(build, board):  # G-4: the schedule's real cells
    *_, model = build(board)
    lines = (len(model.mesh.x), len(model.mesh.y), len(model.mesh.z))
    cells, (estimate, dt) = math.prod(lines), ESTIMATE[board]
    assert model.blocked == [] and abs(cells / estimate - 1) <= 0.10 and abs(model.dt_ref / dt - 1) <= 0.05
    assert LINES.get(board, lines)[:3] == lines


def test_the_coupons_hit_their_targets_in_the_2d_table(build):  # B-1, C-3, D-1: set through the product's table
    want = {"p4b_ms90": 90.25, "p4b_ms100": 99.81, "p4b_sl90": 90.27, "p4b_ms90_vic": 90.21, "p4e_gapp": 95.17,
            "p4e_gapm": 81.04}
    for board, z in want.items():
        project, b, geom, _, _ = build(board)
        rows = [p for c, p in pipeline.si_readout(b, geom, project) if c == "I_SI_2D_PAIR" and p["length_mm"] == "60.000"]
        assert len(rows) == 2 and all(float(p["z_diff"]) == pytest.approx(z, abs=0.02) for p in rows), board
    for board, z in {"p4c_step75": 75.07, "p4c_step35": 34.94, "si_pad_coupon": 49.96, "si_line100": 51.96,
                     "si_pad_coupon_tall": 48.32}.items():
        project, b, geom, _, _ = build(board)
        lines = {float(p["z0"]) for c, p in pipeline.si_readout(b, geom, project) if c == "I_SI_2D_LINE"}
        assert any(v == pytest.approx(z, abs=0.02) for v in lines), board  # the steps' leads read 49.96


def test_the_ports_take_the_kinds_the_gates_compare(build):  # B-1, D-1
    want = {"p4b_ms90": {"plane"}, "p4b_sl90": {"copper"}, "si_pad_coupon": {"ic"}, "si_pad_coupon_tall": {"copper"},
            "si_line100": {"plane"}, "p4b_ms90_vic": {"plane"}}
    for board, rules in want.items():
        assert {q["rule"] for q in build(board)[0]["ports"]} == rules, board
    assert [c for c, _ in build("p4b_ms90_45")[3]].count("W_STAIRCASED") == 2  # each leg's staircased diagonal


def test_p4es_variants_move_one_thing(build):  # E-1: the shift, the gap ± d, the null edit
    def centres(name):
        return {v["name"]: v["center"] for v in json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8")).values()}
    for name, d, of in (("p4e_shift", 0.1, "p4b_ms90"), ("p4e_shift3", 0.066667, "p4b_ms90"),
                        ("p4e_vshift", 0.1, "p4b_ms90_vic"), ("p4e_vshift3", 0.066667, "p4b_ms90_vic")):
        c, base = centres(name), centres(of)
        assert all(abs(c[k][0] - base[k][0] - d) <= 1e-6 and abs(c[k][1] - base[k][1] + d) <= 1e-6 for k in base)
    base = centres("p4b_ms90")
    assert centres("p4e_gapp") == centres("p4e_gapm") == base  # the jogs take the gap's change
    a, b = build("p4b_ms90")[1], build("p4e_null")[1]
    for key in {(t.layer, t.net) for g in (a, b) for t in g.tracks}:
        ta, tb = (shapely.union_all([t.polygon() for t in g.tracks if (t.layer, t.net) == key]) for g in (a, b))
        assert ta.symmetric_difference(tb).area <= 1e-9, key  # the split adds no copper to the board
    # clean()'s simplification draws D-'s split edge up to 8.6 µm off (under SIMPLIFY), so the null's spec hash
    # differs and P4-E runs its pair
