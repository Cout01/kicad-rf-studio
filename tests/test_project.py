# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import os
from pathlib import Path

import pytest

from kicad_rf_studio.core.geometry.region import air_gap
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model.spec import antenna_t_max
from kicad_rf_studio.core.project import (INTERFACES, SCHEMA, SCHEMA_SI, antenna, board_file, board_hash,
                                          check_project, copper_model, far_field_hz, load_project,
                                          make_antenna_project, make_si_project, pulse_band, read_project,
                                          save_project, si, si_interface)
from test_cli_new import FIX, run_new


def test_schema_mismatch(tmp_path):
    p = tmp_path / "project.json"; p.write_text('{"schema": 99}', encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_project(p)
    assert e.value.code == "E_PROJECT_SCHEMA"


# --- beyond the brief's test: what the error says, and the rest of the file interface -------------------


def test_schema_mismatch_names_the_file_and_both_versions(tmp_path):
    p = tmp_path / "project.json"; p.write_text('{"schema": 99}', encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_project(p)
    assert e.value.params == {"path": str(p), "found": 99, "expected": SCHEMA_SI}  # the newest it reads (Stage 4)
    assert "schema 99" in str(e.value) and "schema 3" in str(e.value)
    p.write_text('{"schema": 3}', encoding="utf-8")
    assert load_project(p) == {"schema": 3}  # an SI project (Stage 4 design 5.1); check_project reads its fields


@pytest.mark.parametrize("text", ["{}", '{"board": {}}', "[]", "null", "7"])
def test_a_file_with_no_schema_is_refused(tmp_path, text):
    p = tmp_path / "project.json"; p.write_text(text, encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_project(p)
    assert e.value.code == "E_PROJECT_SCHEMA" and e.value.params["found"] is None


def test_board_hash_is_the_sha256_of_the_bytes(tmp_path):
    p = tmp_path / "board.kicad_pcb"; p.write_bytes(b"abc")
    assert board_hash(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"  # FIPS 180-2 test vector
    raw = b"(kicad_pcb)\r\n\xff\x00 \xc3\xa7\r\n"  # CRLF, a byte that is not UTF-8, a NUL: bytes, not decoded text
    p.write_bytes(raw)
    assert board_hash(p) == hashlib.sha256(raw).hexdigest()


def test_save_then_load_keeps_the_data_and_the_non_ascii_text(tmp_path):
    data = {"schema": SCHEMA, "note": "ação — Ω", "values": [1.5, None, True]}
    p = tmp_path / "project.json"
    save_project(p, data)
    assert load_project(p) == data
    raw = p.read_bytes()
    assert "ação — Ω".encode("utf-8") in raw  # ensure_ascii=False: the text itself, not \u escapes
    assert raw.startswith(b'{\n  "schema": 1,\n  "note"')  # indent=2
    assert b"\r" not in raw  # the same bytes on every platform


def test_load_accepts_a_byte_order_mark(tmp_path):
    p = tmp_path / "project.json"; p.write_bytes(b'\xef\xbb\xbf{"schema": 1}')  # what an older Notepad writes
    assert load_project(p) == {"schema": 1}


def test_board_file_follows_the_project_file_not_the_working_directory(tmp_path, monkeypatch):
    (tmp_path / "boards").mkdir()
    board = tmp_path / "boards" / "x.kicad_pcb"; board.write_text("x", encoding="utf-8")
    project = tmp_path / "proj" / "project.json"
    monkeypatch.chdir(tmp_path)  # neither the project's folder nor the board's
    assert board_file(project, {"board": {"path": "../boards/x.kicad_pcb"}}) == board.resolve()
    assert board_file(project, {"board": {"path": board.as_posix()}}) == board.resolve()  # an absolute path stays


# --- plan 3, task 4: the complete schema ----------------------------------------------------------------------
DELETE = object()


def edit(data, where, value):
    *path, last = where
    for key in path:
        data = data[key]
    if value is DELETE:
        del data[last]
    else:
        data[last] = value


@pytest.mark.parametrize(("where", "value", "field", "expected"), [
    (["lid_height_mm"], 0, "lid_height_mm", 'a number above 0, or null ("lid": false leaves the lid out)'),
    (["chain"], DELETE, "chain", "an object"),
    (["harmonics"], "3", "harmonics", "a whole number above 0"),
    (["preset"], "Strict", "preset", "draft, normal or strict"),
    (["mesh", "n"], 3.0, "mesh.n", "a whole number of 2 or more"),
    (["mesh", "reach_h"], 0, "mesh.reach_h", "a number above 0"),
    (["region", "margin_scale"], "2", "region.margin_scale", "a number above 0"),
    (["classes", "shields"], "SH1", "classes.shields", "a list of names, or null (computed from the board)"),
    (["ports", 0, "reference"], DELETE, "ports[0].reference", "a pad, a point or null"),
    (["stackup", "layers", 1, "thickness_mm"], DELETE, "stackup.layers[1].thickness_mm", "a number of 0 or more"),
    (["f0_hz"], -915e6, "f0_hz", "a number above 0"),
    (["t_max_s"], 0, "t_max_s", "a number above 0"),
    (["gates", "dt_floor"], 1.5, "gates.dt_floor", "a number above 0 and at most 1"),
    (["chain", "series", 0, "role"], "lumped", "chain.series[0].role", "port, copper, open, grid or curve_port"),
    (["lid"], "yes", "lid", "true, false or null"),
    (["allow_curve_port"], 1, "allow_curve_port", "true or false")])
def test_a_bad_field_is_named_never_internal(tmp_path, where, value, field, expected):  # S-1, S-7, L-2
    _, pj = run_new(tmp_path, "--lid-height", "2.5")
    d = load_project(pj)
    edit(d, where, value)
    save_project(pj, d)
    with pytest.raises(KrsError) as e:
        read_project(pj)
    assert (e.value.code, {**e.value.params, "expected": render(e.value.params["expected"])}) == (
        "E_PROJECT_FIELD", {"path": str(pj), "field": field, "expected": expected})


# --- beyond the brief's tests ---------------------------------------------------------------------------------
MODEL = "null, or package (text) with esl_h, esr_ohm and cp_f (numbers of 0 or more)"


@pytest.mark.parametrize(("where", "value", "field", "expected"), [
    (["f0_hz"], float("inf"), "f0_hz", "a number above 0"),  # json reads Infinity (and NaN): no number here
    (["band_factor"], True, "band_factor", "a number above 0"),  # a bool is never a number
    (["harmonics"], True, "harmonics", "a whole number above 0"),
    (["board"], "lpf915.kicad_pcb", "board", "an object"),
    (["ports", 1], "P2", "ports[1]", "an object"),
    (["ports"], {}, "ports", "a list of ports"),
    (["ports", 0, "reference"], {"pad": "U1.2"}, "ports[0].reference", "a pad, a point or null"),
    (["ports", 0, "reference"], {"point": [1.0], "layer": "F.Cu"}, "ports[0].reference", "a pad, a point or null"),
    (["chain", "shunt", 0, "model", "esl_h"], -1e-9, "chain.shunt[0].model", MODEL),
    (["others", 0, "model"], {"package": "0603"}, "others[0].model", MODEL),
    (["others", 0, "pads"], ["C4.1"], "others[0].pads", "two names"),
    (["chain", "nets", 1], 7, "chain.nets", "a list of names"),
    (["stackup", "layers", 2, "epsilon_r"], 0, "stackup.layers[2].epsilon_r", "a number above 0, or null"),
    (["results"], [], "results", "an object")])
def test_every_kind_of_field_is_checked(tmp_path, where, value, field, expected):
    _, pj = run_new(tmp_path, "--lid-height", "2.5")
    d = load_project(pj)
    edit(d, where, value)
    save_project(pj, d)
    with pytest.raises(KrsError) as e:
        read_project(pj)
    assert (e.value.code, e.value.params["field"], render(e.value.params["expected"])) == (
        "E_PROJECT_FIELD", field, expected)
    assert str(e.value) == (f"{pj}: {field} is missing or is not {expected}. Fix it in a text editor, or re-create "
                            "the project with `new`.")


def test_nulls_where_allowed_and_results_read(tmp_path):
    _, pj = run_new(tmp_path)  # no --lid-height: lid_height_mm is null
    d = load_project(pj)
    for where, value in [(["classes", "shields"], None), (["lid"], False), (["chain", "series", 0, "model"], None),
                         (["ports", 0, "reference"], {"pad": "U1.2", "uuid": ""}),  # a pad by its name alone
                         (["ports", 1, "reference"], {"point": [110.0, 100.5], "layer": "F.Cu"}),
                         (["ports", 1, "rule"], None), (["stackup", "layers", 0, "epsilon_r"], None),
                         (["results"], {"runs": []})]:
        edit(d, where, value)
    save_project(pj, d)
    assert read_project(pj) == d


def test_a_save_that_fails_leaves_the_file_as_it_was_and_makes_no_folder(tmp_path, monkeypatch):
    p = tmp_path / "project.json"
    save_project(p, {"schema": SCHEMA, "n": 1})

    def crash(src, dst):
        raise OSError("the disk is full")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError):
        save_project(p, {"schema": SCHEMA, "n": 2})
    assert load_project(p) == {"schema": SCHEMA, "n": 1}
    monkeypatch.undo()
    with pytest.raises(FileNotFoundError):
        save_project(tmp_path / "missing" / "project.json", {"schema": SCHEMA})
    assert not (tmp_path / "missing").exists()


# --- plan 4, task 3: a part's S2P file ------------------------------------------------------------------------


@pytest.mark.parametrize(("value", "ok"), [
    (None, True), ({"file": "../parts/l1.s2p", "connection": "series"}, True),
    ({"file": "l1.s2p", "connection": "Series"}, False), ({"file": 3, "connection": "shunt"}, False), (DELETE, False)])
def test_a_parts_s2p_is_null_or_a_file_and_its_fixture(tmp_path, value, ok):  # C-18
    _, pj = run_new(tmp_path, "--lid-height", "2.5")  # tests/test_cli_new.py
    d = load_project(pj)
    edit(d, ["chain", "series", 0, "s2p"], value)
    save_project(pj, d)
    if ok:
        assert read_project(pj)["chain"]["series"][0]["s2p"] == value
        return
    with pytest.raises(KrsError) as e:
        read_project(pj)
    assert (e.value.code, {**e.value.params, "expected": render(e.value.params["expected"])}) == (
        "E_PROJECT_FIELD", {"path": str(pj), "field": "chain.series[0].s2p",
                            "expected": "null, or file (text) and connection (series or shunt)"})


# --- Stage 3 plan 2, task 3: schema 2, an antenna project -----------------------------------------------------


@pytest.mark.parametrize(("f_lo", "f_hi", "f1", "f2"), [(2.4e9, 2.4835e9, 1.84e9, 2.99e9), (902e6, 928e6, 693e6, 1.12e9),
                                                        (863e6, 870e6, 663e6, 1.05e9), (2.4e9, 2.5e9, 1.84e9, 3.0e9)])
def test_the_pulse_band_rounds_out_to_3_significant_digits(f_lo, f_hi, f1, f2):  # design 5.4
    assert pulse_band(f_lo, f_hi) == (f1, f2) and all(type(v) is float for v in pulse_band(f_lo, f_hi))


def antenna_dict():
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    chain = {"start": "U1.1", "end": "AE1.1", "nets": ["RF"], "series": [], "shunt": []}
    port = {"name": "P1", "signal": "U1.1", "signal_uuid": "u", "layer": "F.Cu", "rule": "ic",
            "reference": {"pad": "U1.2", "uuid": ""}}
    return make_antenna_project("ifa2g4.kicad_pcb", "0" * 64, 2.4e9, 2.4835e9, b.stackup, classify(b), chain, [],
                                [port], "AE1", ["AE1.2"], t_max_s=30e-9, air_gap_mm=air_gap(2.4e9))


def test_an_antenna_project_holds_the_design_fields():  # design 5.1, 5.2, 5.5
    d = antenna_dict()
    assert (d["schema"], d["kind"], d["band"], d["f0_hz"], d["t_max_s"]) == (
        2, "antenna", {"f_lo_hz": 2.4e9, "f_hi_hz": 2.4835e9}, 2.44175e9, 30e-9)
    assert "harmonics" not in d and "band_factor" not in d and d["lid"] is True and d["region"] == {"expand_h": 6.0}
    assert (d["antenna"], d["boundary"], d["air_gap_mm"]) == ({"ref": "AE1", "join": ["AE1.2"]}, "pml_8", 31.228381)
    f = d["far_field"]["f_hz"]
    assert (len(f), f[0], f[1], f[-1], d["far_field"]["step_deg"]) == (11, 2.44175e9, 2.4e9, 2.4835e9, 5)
    assert antenna(d) and not antenna({**d, "schema": 1}) and check_project(d, Path("p.json")) is d


@pytest.mark.parametrize(("change", "field", "expected"), [
    ({"kind": "chain"}, "kind", "T_EXPECT_ANTENNA"),
    ({"band": {"f_lo_hz": 2.4e9, "f_hi_hz": 2.3e9}}, "band.f_hi_hz", "T_EXPECT_BAND"),
    ({"band": {"f_lo_hz": 868e6, "f_hi_hz": 2.4835e9}}, "band.f_hi_hz", "T_EXPECT_BAND"),  # two bands: one a run
    ({"f0_hz": 2.5e9}, "f0_hz", "T_EXPECT_F0_BAND"),
    ({"boundary": "MUR"}, "boundary", "T_EXPECT_BOUNDARY"),
    ({"far_field": {"f_hz": [3.1e9], "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ"),
    ({"far_field": {"f_hz": [2.44e9] * 12, "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ"),
    ({"far_field": {"f_hz": [2.4e9, 2.44175e9], "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ"),  # f0 first
    ({"far_field": {"f_hz": [2.44e9], "step_deg": 7}}, "far_field.step_deg", "T_EXPECT_STEP"),
    ({"air_gap_mm": 0}, "air_gap_mm", "T_EXPECT_ABOVE_0"),
    ({"antenna": {"ref": "AE1"}}, "antenna.join", "T_EXPECT_NAMES"),
    ({"copper": "foil"}, "copper", "T_EXPECT_COPPER"),
    ({"flat_s": 0}, "flat_s", "T_EXPECT_ABOVE_0")])
def test_a_schema_2_field_out_of_its_range_is_named(change, field, expected):  # design 5.1; RF 5
    with pytest.raises(KrsError) as e:
        check_project({**antenna_dict(), **change}, Path("p.json"))
    assert (e.value.code, e.value.params["field"], e.value.params["expected"]) == ("E_PROJECT_FIELD", field, expected)


def test_an_antenna_projects_lid_is_true_or_false(tmp_path):  # final review G1: a null lid read harmonics
    p = tmp_path / "project.json"
    with pytest.raises(KrsError) as e:
        check_project({**antenna_dict(), "lid": None}, p)
    assert (e.value.code, e.value.params) == ("E_PROJECT_FIELD", {"path": str(p), "field": "lid",
                                                                  "expected": "T_EXPECT_FLAG"})
    assert check_project({**antenna_dict(), "lid": False}, p)["lid"] is False


def test_an_antennas_copper_is_solid_or_sheet_and_optional():  # design 5.3; ruling 3
    d = antenna_dict()
    assert d["copper"] == "solid" and copper_model(d) == "solid" and "flat_s" not in d
    assert check_project({**d, "copper": "sheet", "flat_s": 4.4e-8}, Path("p.json"))["copper"] == "sheet"
    old = {k: v for k, v in d.items() if k != "copper"}  # a project made before this version
    assert check_project(old, Path("p.json")) is old and copper_model(old) == "solid"


# --- Stage 3 plan 5, task 1: the band's defaults --------------------------------------------------------------


def test_the_bands_defaults_are_new_antennas():  # Stage 3 design 5.4, 5.5; the GUI's Advanced shows them (plan 5)
    assert far_field_hz(2.4e9, 2.4835e9) == [  # as <GATES>' verified pour holds them: compare's fingerprint
        2441750000.0, 2400000000.0, 2409277777.7777777, 2418555555.5555553, 2427833333.3333335, 2437111111.111111,
        2446388888.888889, 2455666666.6666665, 2464944444.4444447, 2474222222.2222223, 2483500000.0]
    bands = ((863e6, 870e6), (902e6, 928e6), (2.4e9, 2.4835e9))
    assert [antenna_t_max(*band) for band in bands] == [85e-9, 79e-9, 30e-9]


# --- Stage 4 plan 1, task 4: schema 3, an SI project ----------------------------------------------------------


def test_schema_3_is_an_si_project_whose_fields_are_checked(tmp_path):  # Stage 4 design 5.1
    assert (SCHEMA_SI, si({"schema": 3}), si({"schema": 2}), antenna({"schema": 3})) == (3, True, False, False)
    p = tmp_path / "project.json"
    p.write_text('{"schema": 3, "kind": "si"}', encoding="utf-8")
    assert load_project(p) == {"schema": 3, "kind": "si"}
    with pytest.raises(KrsError) as e:
        read_project(p)
    assert (e.value.code, e.value.params["field"]) == ("E_PROJECT_FIELD", "board")


# --- Stage 4 plan 2, task 2: schema 3's fields, the interfaces ------------------------------------------------


def si_dict():
    """A schema 3 dict for usb2_hs's pair and victim, as new_si wrote it before the d fill (a set cell), its parts left
    out."""
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    lines = [{"role": role, "chain": {"start": s, "end": e, "nets": nets, "series": [], "shunt": []}}
             for role, s, e, nets in (("measured", "J1.3", "U1.3", ["USB_D+", "MCU_D+"]),
                                      ("measured", "J1.2", "U1.2", ["USB_D-", "MCU_D-"]),
                                      ("victim", "TP1.1", "TP2.1", ["AUX"]))]
    ports = [{"name": f"P{k}", "signal": s, "signal_uuid": "", "layer": "F.Cu", "rule": "plane",
              "reference": {"plane": "In1.Cu"}}
             for k, s in enumerate(("J1.3", "J1.2", "U1.3", "U1.2", "TP1.1", "TP2.1"), 1)]
    return make_si_project("usb2_hs.kicad_pcb", "0" * 64, b.stackup, classify(b), lines,
                           {"p": "USB_D+", "n": "USB_D-", "by": "rule"}, [], ports,
                           si_interface("usb2-hs", None, None, True), t_max_s=9e-9, window_s=2e-9, max_cell_mm=0.414)


def test_an_si_project_holds_the_design_fields():  # Stage 4 design 5.1, 5.3, 5.4
    d = si_dict()
    assert (d["schema"], d["kind"], d["interface"], d["f_max_hz"], d["rise_s"], d["marker_hz"], d["target_ohm"],
            d["tolerance"]) == (3, "si", "usb2-hs", 10e9, 5e-10, 2.4e8, 90.0, 0.1)
    assert (d["dielectric"], d["t_max_s"], d["window_s"], d["lid"]) == ("lossless", 9e-9, 2e-9, True)
    assert d["gates"] == {"fit2d_limit": 0.03, "dt_floor": 0.6}  # SI's floor (design 5.3, A-43)
    assert d["mesh"] == {"n": 2, "reach_h": 6.0, "max_cell_mm": 0.414} and d["region"] == {"expand_h": 6.0,
                                                                                            "margin_scale": 1.0}
    assert not {"f0_hz", "harmonics", "band_factor", "chain"} & set(d) and check_project(d, Path("p.json")) is d
    assert {k: (v["target_ohm"], v["rise_s"], v["marker_hz"], v["pair"]) for k, v in INTERFACES.items()} == {
        "usb2-hs": (90.0, 5e-10, 2.4e8, True), "100base-tx": (100.0, 3e-9, 62.5e6, True),
        "se50": (50.0, 1e-9, 133e6, False)}


def test_the_custom_interface_and_the_presets_refusals():  # design 5.1
    c = si_interface("custom", 5e9, 85.0, True)
    assert (c["interface"], c["f_max_hz"], c["target_ohm"], c["tolerance"]) == ("custom", 5e9, 85.0, 0.1)
    assert c["rise_s"] == pytest.approx(2.5e-10) and c["marker_hz"] == pytest.approx(1.4e9)  # 1.25/f_max, 0.35/rise
    for args, code, params in [(("usb2-hs", None, None, False), "E_SI_NEEDS_PAIR", {"interface": "usb2-hs"}),
                               (("se50", None, None, True), "E_SI_NOT_PAIR", {"interface": "se50"}),
                               (("custom", None, 85.0, True), "E_SI_CUSTOM", {}),
                               (("se50", 5e9, None, False), "E_SI_CUSTOM", {})]:
        with pytest.raises(KrsError) as e:
            si_interface(*args)
        assert (e.value.code, e.value.params) == (code, params)


@pytest.mark.parametrize(("change", "field", "expected"), [
    ({"kind": "antenna"}, "kind", "T_EXPECT_SI"),
    ({"interface": "usb3"}, "interface", "T_EXPECT_INTERFACE"),
    ({"rise_s": 1e-10}, "rise_s", "T_EXPECT_RISE"),  # faster than 1.25/f_max, the localising TDR's 125 ps
    ({"dielectric": "kappa"}, "dielectric", "T_EXPECT_DIELECTRIC"),  # never v1's κ (design 3)
    ({"mesh": {"n": 2, "reach_h": 6.0, "max_cell_mm": 0}}, "mesh.max_cell_mm", "T_EXPECT_ABOVE_0_OR_NULL"),
    ({"pair": None}, "pair", "T_EXPECT_SI_PAIR"),  # two measured lines are a pair
    (lambda d: {"lines": d["lines"][::-1]}, "lines", "T_EXPECT_SI_LINES"),  # the measured lines come first
    (lambda d: {"lines": [{**d["lines"][0], "role": "aggressor"}, *d["lines"][1:]]}, "lines[0].role",
     "T_EXPECT_LINE_ROLE"),
    (lambda d: {"ports": d["ports"][1:] + d["ports"][:1]}, "ports", "T_EXPECT_SI_PORTS"),  # se2gmm reads this order
    (lambda d: {"ports": [{**d["ports"][0], "rule": "vertical"}, *d["ports"][1:]]}, "ports[0].rule",
     "T_EXPECT_SI_RULE"),
    (lambda d: {"ports": [{**d["ports"][0], "reference": {"plane": 3}}, *d["ports"][1:]]}, "ports[0].reference",
     "T_EXPECT_SI_REFERENCE")])
def test_an_si_field_out_of_its_range_is_named(change, field, expected):  # design 5.1; Review Focus (ports by hand)
    d = si_dict()
    with pytest.raises(KrsError) as e:
        check_project({**d, **(change(d) if callable(change) else change)}, Path("p.json"))
    assert (e.value.code, e.value.params["field"], e.value.params["expected"]) == ("E_PROJECT_FIELD", field, expected)
