# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
import json
import re
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.sexpr import parse
from kicad_rf_studio.core.kicad.stackup import Layer, Stackup, from_board, kicad_default, preset
from kicad_rf_studio.core.messages import KrsError

FIX = Path(__file__).parent / "fixtures"


def test_kicad_default_rule():
    s = kicad_default(0.8)
    assert s.dielectric_thickness() == pytest.approx(0.71)
    assert (s.layers[0].kind, s.layers[0].thickness, s.layers[0].epsilon_r) == ("mask", 0.01, 3.3)


def test_board_stackup_is_read():
    s = load_board(FIX / "lpf915.kicad_pcb").stackup
    assert s.source == "board" and [l.kind for l in s.layers] == ["mask", "copper", "dielectric", "copper", "mask"]
    assert s.dielectric_thickness() == pytest.approx(0.71)


def test_board_without_stackup(mini_board):
    assert mini_board("").stackup is None


def test_jlcpcb_preset_records_its_source():
    d = json.loads(files("kicad_rf_studio").joinpath("data/stackups/jlcpcb-2l.json").read_text("utf-8"))
    assert d["source"].startswith("https://jlcpcb.com/") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["retrieved"])
    assert "spec_frequency_hz" in d and 3.5 <= d["dielectric"]["epsilon_r"] <= 5.0
    assert preset("jlcpcb-2l", 0.8).source == "jlcpcb-2l"


def test_unknown_preset():
    with pytest.raises(KrsError) as e:
        preset("nope", 0.8)
    assert e.value.code == "E_UNKNOWN_PRESET"


def test_presets_refuse_more_than_two_layers():
    with pytest.raises(KrsError) as e:
        preset("kicad-default", 1.6, copper_layers=4)
    assert e.value.code == "E_DEFAULT_RULE_LAYERS"


def test_nonstandard_copper_is_listed():
    s = kicad_default(0.8)
    heavy = Stackup("x", tuple(replace(l, thickness=0.07) if l.kind == "copper" else l for l in s.layers))
    assert s.nonstandard_copper() == [] and len(heavy.nonstandard_copper()) == 2


# --- beyond the brief's seven tests -------------------------------------------------------------
# --- KiCad's default rule ------------------------------------------------------------------------


def test_kicad_default_layers_top_to_bottom():
    s = kicad_default(0.8)
    assert s.source == "kicad-default"
    assert [(l.name, l.kind) for l in s.layers] == [
        ("F.Mask", "mask"), ("F.Cu", "copper"), ("dielectric 1", "dielectric"), ("B.Cu", "copper"), ("B.Mask", "mask")]
    assert [l.thickness for l in s.layers] == pytest.approx([0.01, 0.035, 0.71, 0.035, 0.01])
    assert [l.epsilon_r for l in s.layers] == [3.3, None, 4.5, None, 3.3]
    assert [l.loss_tangent for l in s.layers] == [0, None, 0.02, None, 0]


@pytest.mark.parametrize("name", ["kicad-default", "jlcpcb-2l"])
@pytest.mark.parametrize("thickness", [0.4, 0.8, 1.6, 2.0])
def test_a_rule_fills_the_board_thickness(name, thickness):
    s = preset(name, thickness)
    assert sum(l.thickness for l in s.layers) == pytest.approx(thickness)
    assert 0 < s.dielectric_thickness() < thickness


def test_the_kicad_default_preset_is_the_kicad_default_rule():
    assert preset("kicad-default", 1.6) == kicad_default(1.6)


@pytest.mark.parametrize("build", [lambda n: kicad_default(1.6, n), lambda n: preset("kicad-default", 1.6, n),
                                   lambda n: preset("jlcpcb-2l", 1.6, n)], ids=["default", "kicad", "jlcpcb"])
@pytest.mark.parametrize("count", [1, 4, 6])
def test_every_rule_refuses_a_board_without_exactly_two_copper_layers(build, count):
    with pytest.raises(KrsError) as e:
        build(count)
    assert e.value.code == "E_DEFAULT_RULE_LAYERS" and e.value.params == {"count": count}
    assert str(e.value).startswith(f"Stackup presets are implemented for 2 copper layers, and this board has {count}.")


def test_an_unknown_preset_names_the_known_ones():
    with pytest.raises(KrsError) as e:
        preset("nope", 0.8)
    assert e.value.params == {"name": "nope", "known": "kicad-default, jlcpcb-2l"}
    assert str(e.value) == 'Unknown stackup preset "nope". Known presets: kicad-default, jlcpcb-2l.'


# --- the JLCPCB preset ---------------------------------------------------------------------------


def jlcpcb_file():
    return json.loads(files("kicad_rf_studio").joinpath("data/stackups/jlcpcb-2l.json").read_text("utf-8"))


def has_values_unless_copper(stackup):
    """Ruling R29: a mask or dielectric always has an epsilon_r and a loss_tangent; only copper has none."""
    return all((l.epsilon_r is None and l.loss_tangent is None) if l.kind == "copper"
               else (l.epsilon_r is not None and l.loss_tangent is not None) for l in stackup.layers)


def test_the_jlcpcb_file_has_the_documented_shape():
    d = jlcpcb_file()
    assert d["name"] == "jlcpcb-2l" and datetime.date.fromisoformat(d["retrieved"])
    assert set(d) == {"name", "source", "retrieved", "spec_frequency_hz", "copper_mm", "mask", "dielectric", "notes"}
    assert set(d["mask"]) == {"thickness_mm", "epsilon_r", "loss_tangent"}
    assert set(d["dielectric"]) == {"material", "epsilon_r", "loss_tangent"}


def test_a_null_in_the_jlcpcb_file_is_explained_in_its_notes():
    d = jlcpcb_file()  # a value the pages do not publish is null, never a guess
    fields = {"spec_frequency_hz": d["spec_frequency_hz"], "mask thickness_mm": d["mask"]["thickness_mm"],
              "mask epsilon_r": d["mask"]["epsilon_r"], "mask loss_tangent": d["mask"]["loss_tangent"],
              "dielectric epsilon_r": d["dielectric"]["epsilon_r"],
              "dielectric loss_tangent": d["dielectric"]["loss_tangent"]}
    assert d["notes"] and all(name in d["notes"] for name, value in fields.items() if value is None)


def test_the_jlcpcb_build_uses_the_published_values():
    s = preset("jlcpcb-2l", 0.8)
    assert [(l.name, l.kind) for l in s.layers] == [
        ("F.Mask", "mask"), ("F.Cu", "copper"), ("dielectric 1", "dielectric"), ("B.Cu", "copper"), ("B.Mask", "mask")]
    top, copper, core, _, bottom = s.layers
    assert (top.thickness, top.epsilon_r, top.loss_tangent) == (0.01524, 3.8, 0.0)  # 0.6 mil of mask on copper
    assert replace(bottom, name="F.Mask") == top
    assert (copper.thickness, core.epsilon_r, core.loss_tangent) == (0.035, 4.5, 0.02)
    assert core.thickness == pytest.approx(0.8 - 2 * (0.035 + 0.01524))  # the rest of the board
    assert s.nonstandard_copper() == []


def test_a_null_in_the_preset_file_takes_kicads_default_and_stays_null_in_the_file():
    assert jlcpcb_file()["mask"]["loss_tangent"] is None  # the file records what JLCPCB publishes: no loss tangent
    top = preset("jlcpcb-2l", 0.8).layers[0]
    assert (top.epsilon_r, top.loss_tangent) == (3.8, 0.0)  # its own epsilon_r, KiCad's loss tangent for a mask


@pytest.mark.parametrize("name", ["kicad-default", "jlcpcb-2l"])
def test_no_preset_leaves_a_mask_or_dielectric_without_values(name):
    assert has_values_unless_copper(preset(name, 1.6))


# --- reading the board's own stackup -------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(FIX.glob("*.kicad_pcb")), ids=lambda p: p.stem)
def test_every_fixture_board_carries_its_generators_stackup(path):
    b = load_board(path)
    # Stage 4's four layers: make_fixtures' STACKUP_4L, or p4b_sl90's STACKUP_SL; the tall pad coupon's two at 1.6 mm
    if path.stem.startswith(("usb2_hs", "qspi_clk", "p4", "si_")) and path.stem != "si_pad_coupon_tall":
        assert [l.kind for l in b.stackup.layers] == ["mask", "copper", "dielectric", "copper", "dielectric", "copper",
                                                      "dielectric", "copper", "mask"]
        assert b.stackup.dielectric_thickness() == pytest.approx(b.thickness - 0.16)
    else:  # KiCad's default two layers
        assert [l.kind for l in b.stackup.layers] == ["mask", "copper", "dielectric", "copper", "mask"]
        assert b.stackup.dielectric_thickness() == pytest.approx(b.thickness - 0.09)


def test_board_stackup_values_come_from_the_file():
    s = load_board(FIX / "lpf915.kicad_pcb").stackup
    # KiCad writes epsilon_r and loss_tangent only for a layer with a material, so the file gives the masks none
    # and KiCad's default applies to them: 3.3 and 0
    assert [(l.name, l.thickness, l.epsilon_r, l.loss_tangent) for l in s.layers] == [
        ("F.Mask", 0.01, 3.3, 0.0), ("F.Cu", 0.035, None, None), ("dielectric 1", 0.71, 4.5, 0.02),
        ("B.Cu", 0.035, None, None), ("B.Mask", 0.01, 3.3, 0.0)]


@pytest.mark.parametrize("path", sorted(FIX.glob("*.kicad_pcb")), ids=lambda p: p.stem)
def test_no_fixture_stackup_leaves_a_mask_or_dielectric_without_values(path):
    assert has_values_unless_copper(load_board(path).stackup)


def layer(name, type_, thickness="", extra=""):
    return f'(layer "{name}" (type "{type_}") {thickness} {extra})'


FR4 = '(material "FR4") (epsilon_r {}) (loss_tangent {})'
FOUR_LAYERS = "".join([
    layer("F.SilkS", "Top Silk Screen"), layer("F.Paste", "Top Solder Paste"),
    layer("F.Mask", "Top Solder Mask", "(thickness 0.01)", '(material "Epoxy") (epsilon_r 3.8) (loss_tangent 0.01)'),
    layer("F.Cu", "copper", "(thickness 0.035)"),
    layer("dielectric 1", "prepreg", "(thickness 0.2104 locked)", FR4.format(4.4, 0.02)),
    layer("In1.Cu", "copper", "(thickness 0.0152)"),
    layer("dielectric 2", "core", "(thickness 1.065)", FR4.format(4.6, 0.018)),
    layer("In2.Cu", "copper", "(thickness 0.0152)"),
    layer("dielectric 3", "prepreg", "(thickness 0.2104)", FR4.format(4.4, 0.02)),
    layer("B.Cu", "copper", "(thickness 0.035)"),
    layer("B.Mask", "Bottom Solder Mask", "(thickness 0.01)"), layer("B.Paste", "Bottom Solder Paste"),
    layer("B.SilkS", "Bottom Silk Screen"), '(copper_finish "ENIG") (dielectric_constraints no)'])


def board_with(stackup):
    return parse(f"(kicad_pcb (version 20241229) (setup (stackup {stackup}) (pad_to_mask_clearance 0)))")


def test_types_become_kinds_and_silkscreen_and_paste_are_dropped():
    s = from_board(board_with(FOUR_LAYERS))
    assert [(l.name, l.kind) for l in s.layers] == [
        ("F.Mask", "mask"), ("F.Cu", "copper"), ("dielectric 1", "dielectric"), ("In1.Cu", "copper"),
        ("dielectric 2", "dielectric"), ("In2.Cu", "copper"), ("dielectric 3", "dielectric"), ("B.Cu", "copper"),
        ("B.Mask", "mask")]
    assert s.layers[0] == Layer("F.Mask", "mask", 0.01, 3.8, 0.01)
    assert s.layers[2] == Layer("dielectric 1", "dielectric", 0.2104, 4.4, 0.02)  # "locked" is no part of the value
    assert s.dielectric_thickness() == pytest.approx(0.2104 + 1.065 + 0.2104)


def test_inner_copper_of_half_an_ounce_is_not_standard():
    assert from_board(board_with(FOUR_LAYERS)).nonstandard_copper() == ["In1.Cu", "In2.Cu"]


def test_nonstandard_copper_names_the_layers_and_tolerates_half_a_micron():
    copper = (Layer("F.Cu", "copper", 0.0355, None, None), Layer("In1.Cu", "copper", 0.0152, None, None),
              Layer("core", "dielectric", 0.0152, 4.5, 0.02), Layer("B.Cu", "copper", 0.07, None, None))
    assert Stackup("x", copper).nonstandard_copper() == ["In1.Cu", "B.Cu"]


def test_dielectric_sublayers_are_layers_of_their_own():
    other = '(thickness 0.4) (material "Other") (epsilon_r 3.6) (loss_tangent 0.004)'
    sublayers = f"{FR4.format(4.5, 0.02)} addsublayer {other}"
    core = layer("dielectric 1", "core", "(thickness 0.3 locked)", sublayers)
    copper = '(thickness 0.035)'
    s = from_board(board_with(layer("F.Cu", "copper", copper) + core + layer("B.Cu", "copper", copper)))
    assert [(l.kind, l.thickness, l.epsilon_r, l.loss_tangent) for l in s.layers[1:3]] == [
        ("dielectric", 0.3, 4.5, 0.02), ("dielectric", 0.4, 3.6, 0.004)]
    assert len(s.layers) == 4 and s.dielectric_thickness() == pytest.approx(0.7)


def test_type_names_are_matched_without_regard_to_case():
    s = from_board(board_with(layer("F.Mask", "top solder mask", "(thickness 0.02)")
                              + layer("dielectric 1", "Core", "(thickness 0.5)")))
    assert [(l.kind, l.thickness) for l in s.layers] == [("mask", 0.02), ("dielectric", 0.5)]


@pytest.mark.parametrize("setup", [
    "", "(setup)", "(setup (pad_to_mask_clearance 0))", "(setup (stackup))",
    '(setup (stackup (copper_finish "None")))', '(setup (stackup (layer "F.SilkS" (type "Top Silk Screen"))))',
], ids=["no setup", "empty setup", "no stackup", "empty stackup", "no layers", "only silkscreen"])
def test_a_board_with_no_usable_stackup_layer_has_none(setup):
    assert from_board(parse(f"(kicad_pcb (version 20241229) {setup})")) is None


def test_a_missing_thickness_reads_as_zero_and_copper_has_no_permittivity():
    (copper,) = from_board(board_with('(layer "F.Cu" (type "copper"))')).layers
    assert copper == Layer("F.Cu", "copper", 0.0, None, None)


# --- KiCad's defaults for what a mask or dielectric leaves out (ruling R29) ---------------------------


def test_a_board_that_gives_its_masks_and_dielectric_no_values_gets_kicads_defaults(mini_board):
    copper = "(thickness 0.035)"
    stackup = ("(stackup " + layer("F.Mask", "Top Solder Mask", "(thickness 0.01)") + layer("F.Cu", "copper", copper)
               + layer("dielectric 1", "core", "(thickness 0.7)") + layer("B.Cu", "copper", copper)
               + layer("B.Mask", "Bottom Solder Mask", "(thickness 0.01)") + ")")
    s = mini_board(stackup=stackup).stackup
    assert [(l.kind, l.epsilon_r, l.loss_tangent) for l in s.layers] == [
        ("mask", 3.3, 0.0), ("copper", None, None), ("dielectric", 4.5, 0.02), ("copper", None, None),
        ("mask", 3.3, 0.0)]


@pytest.mark.parametrize("type_, given, expected", [
    ("Top Solder Mask", "", (3.3, 0.0)),
    ("Top Solder Mask", "(epsilon_r 4)", (4.0, 0.0)),
    ("Top Solder Mask", "(loss_tangent 0.01)", (3.3, 0.01)),
    ("core", "", (4.5, 0.02)),
    ("prepreg", "(epsilon_r 3.6)", (3.6, 0.02)),
    ("core", "(loss_tangent 0.004)", (4.5, 0.004)),
    ("core", "(epsilon_r 3.6) (loss_tangent 0)", (3.6, 0.0)),  # a zero the file writes is a value, not a gap
    ("copper", "", (None, None)),
], ids=["mask", "mask epsilon_r only", "mask loss_tangent only", "core", "prepreg epsilon_r only",
        "core loss_tangent only", "lossless core", "copper"])
def test_each_value_a_layer_leaves_out_takes_kicads_default_on_its_own(type_, given, expected):
    (got,) = from_board(board_with(layer("L", type_, "(thickness 0.1)", given))).layers
    assert (got.epsilon_r, got.loss_tangent) == expected


def test_a_sublayer_without_values_takes_the_default_too():
    core = layer("dielectric 1", "core", "(thickness 0.3)", f"{FR4.format(3.6, 0.004)} addsublayer (thickness 0.4)")
    sublayers = from_board(board_with(core)).layers
    assert [(l.epsilon_r, l.loss_tangent) for l in sublayers] == [(3.6, 0.004), (4.5, 0.02)]


def test_a_layer_built_with_none_gets_the_default_of_its_kind():
    assert Layer("m", "mask", 0.01, None, None) == Layer("m", "mask", 0.01, 3.3, 0.0)
    assert Layer("d", "dielectric", 0.5, None, None) == Layer("d", "dielectric", 0.5, 4.5, 0.02)
    assert replace(Layer("m", "mask", 0.01, 3.8, 0.01), thickness=0.02) == Layer("m", "mask", 0.02, 3.8, 0.01)
    assert Layer("c", "copper", 0.035, None, None).epsilon_r is None


# --- JSON ----------------------------------------------------------------------------------------


def test_json_format():
    d = kicad_default(0.8).to_json()
    assert set(d) == {"source", "layers"} and d["source"] == "kicad-default"
    assert d["layers"][0] == {"name": "F.Mask", "kind": "mask", "thickness_mm": 0.01, "epsilon_r": 3.3,
                              "loss_tangent": 0}
    assert d["layers"][1] == {"name": "F.Cu", "kind": "copper", "thickness_mm": 0.035, "epsilon_r": None,
                              "loss_tangent": None}


def test_json_round_trips_through_text():
    for s in (kicad_default(0.8), preset("jlcpcb-2l", 1.6), load_board(FIX / "lpf915.kicad_pcb").stackup,
              from_board(board_with(FOUR_LAYERS))):
        assert Stackup.from_json(json.loads(json.dumps(s.to_json()))) == s


def test_json_may_leave_out_epsilon_and_loss_tangent():
    s = Stackup.from_json({"source": "x", "layers": [{"name": "F.Cu", "kind": "copper", "thickness_mm": 0.035}]})
    assert s == Stackup("x", (Layer("F.Cu", "copper", 0.035, None, None),))


def test_json_gives_a_mask_or_dielectric_that_leaves_out_its_values_kicads_defaults():
    layers = [{"name": "F.Mask", "kind": "mask", "thickness_mm": 0.01},
              {"name": "F.Cu", "kind": "copper", "thickness_mm": 0.035},
              {"name": "dielectric 1", "kind": "dielectric", "thickness_mm": 0.7, "epsilon_r": None,
               "loss_tangent": 0.01}]
    s = Stackup.from_json({"source": "x", "layers": layers})
    assert [(l.epsilon_r, l.loss_tangent) for l in s.layers] == [(3.3, 0.0), (None, None), (4.5, 0.01)]
