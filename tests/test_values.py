# SPDX-License-Identifier: GPL-3.0-or-later
import time

import pytest

from kicad_rf_studio.core.kicad.values import parse_frequency, parse_value, part_kind, part_value
from kicad_rf_studio.core.messages import KrsError


@pytest.mark.parametrize("text, expected", [
    ("10uF/16V", (10e-6, "F")), ("0R", (0.0, "R")), ("0Ω", (0.0, "R")), ("1meg", (1e6, "")),
    ("4n7", (4.7e-9, "")), ("4R7", (4.7, "R")), ("2k2", (2200.0, "")), ("3.3pF", (3.3e-12, "F")),
    ("15nH", (15e-9, "H")), ("100n", (100e-9, "")), ("47pF 50V", (47e-12, "F")), ("DNP", None), ("", None)])
def test_parse_value(text, expected):
    got = parse_value(text)
    if expected is None:
        assert got is None
    else:
        assert got[1] == expected[1] and got[0] == pytest.approx(expected[0])

@pytest.mark.parametrize("text", ["915MHz", "0.915 GHz", "915e6", "915mhz"])
def test_parse_frequency(text):
    assert parse_frequency(text) == pytest.approx(915e6)

def test_bad_frequency():
    with pytest.raises(KrsError) as e:
        parse_frequency("abc")
    assert e.value.code == "E_BAD_FREQUENCY"


# --- beyond the brief's tests -------------------------------------------------------------------


def assert_reads(text, value, kind):
    got = parse_value(text)
    assert got is not None and got[1] == kind and got[0] == pytest.approx(value)


@pytest.mark.parametrize("text, value", [
    ("1p", 1e-12), ("1n", 1e-9), ("1u", 1e-6), ("1m", 1e-3), ("1k", 1e3), ("1K", 1e3),
    ("1M", 1e6), ("1G", 1e9), ("1meg", 1e6), ("1MEG", 1e6), ("1Meg", 1e6)])
def test_prefix_case_counts_except_for_k_and_meg(text, value):
    assert_reads(text, value, "")  # m milli, M mega; k and K kilo; meg is mega in any case


@pytest.mark.parametrize("text, value, kind", [  # named, because the look-alikes print the same
    ("10\N{MICRO SIGN}F", 10e-6, "F"), ("10\N{GREEK SMALL LETTER MU}F", 10e-6, "F"),
    ("1k\N{GREEK CAPITAL LETTER OMEGA}", 1e3, "R"), ("1k\N{OHM SIGN}", 1e3, "R"),
    ("47m\N{GREEK CAPITAL LETTER OMEGA}", 47e-3, "R"), ("47m\N{OHM SIGN}", 47e-3, "R")])
def test_look_alike_unicode_letters_read_the_same(text, value, kind):
    assert_reads(text, value, kind)


@pytest.mark.parametrize("text, value", [
    ("1kohm", 1e3), ("1kOhm", 1e3), ("1kOHM", 1e3), ("1Mohm", 1e6), ("1mOhm", 1e-3),
    ("1megOHM", 1e6)])
def test_ohm_is_read_in_any_case(text, value):
    assert_reads(text, value, "R")


@pytest.mark.parametrize("text, value, kind", [
    ("4k7", 4.7e3, ""), ("1M5", 1.5e6, ""), ("4u7", 4.7e-6, ""), ("4p7", 4.7e-12, ""),
    ("4u7F", 4.7e-6, "F"), ("4k7R", 4.7e3, "R"), ("0R5", 0.5, "R"), ("47R", 47.0, "R")])
def test_rkm_letter_replaces_the_point_and_r_is_the_ohm_unit(text, value, kind):
    assert_reads(text, value, kind)


@pytest.mark.parametrize("text, value, kind", [
    ("0.5pF", 0.5e-12, "F"), (".5pF", 0.5e-12, "F"), ("10", 10.0, ""), ("0", 0.0, "")])
def test_decimals_and_bare_numbers(text, value, kind):
    assert_reads(text, value, kind)


@pytest.mark.parametrize("text, value, kind", [
    ("  10uF  ", 10e-6, "F"), ("0.1uF X7R", 0.1e-6, "F"), ("1k 1%", 1e3, ""),
    ("1uH/2A", 1e-6, "H")])
def test_only_the_first_word_is_read(text, value, kind):
    assert_reads(text, value, kind)


@pytest.mark.parametrize("text, value, kind", [
    ("100 nF", 100e-9, "F"), ("3.3 pF", 3.3e-12, "F"), ("4.7 k", 4700.0, ""),
    ("10 uF/16V", 10e-6, "F"), ("100 nF 50V", 100e-9, "F"), ("100   nF", 100e-9, "F"),
    ("100\tnF", 100e-9, "F"), ("100\N{NO-BREAK SPACE}nF", 100e-9, "F"), ("1 Meg", 1e6, ""),
    ("0 R", 0.0, "R"), ("2.2 uH", 2.2e-6, "H"), ("47 m\N{GREEK CAPITAL LETTER OMEGA}", 47e-3, "R")])
def test_a_space_between_the_number_and_its_prefix_or_unit_is_ignored(text, value, kind):
    assert_reads(text, value, kind)


@pytest.mark.parametrize("text", ["100 50V", "100 1%", "100 (typ)", "100 +/-5%"])
def test_a_spaced_word_that_does_not_start_with_a_letter_is_not_part_of_the_value(text):
    assert_reads(text, 100.0, "")


@pytest.mark.parametrize("text, value, kind", [
    ("100nf", 100e-9, "F"), ("10uf", 10e-6, "F"), ("1nh", 1e-9, "H"), ("1uh", 1e-6, "H"),
    ("0r", 0.0, "R"), ("10r", 10.0, "R"), ("4r7", 4.7, "R"), ("4k7r", 4.7e3, "R"),
    ("1mf", 1e-3, "F"), ("1Mr", 1e6, "R")])  # the unit letter may be any case, the prefix may not
def test_unit_letters_are_read_in_any_case(text, value, kind):
    assert_reads(text, value, kind)


@pytest.mark.parametrize("text, value, kind", [
    ("100nF,50V", 100e-9, "F"), ("10uF, 16V", 10e-6, "F"), ("100 nF,50V", 100e-9, "F"),
    ("4k7,5%", 4700.0, ""), ("1k,1%", 1e3, ""), ("0R,DNP", 0.0, "R")])
def test_a_comma_ends_the_value_like_a_slash(text, value, kind):
    assert_reads(text, value, kind)


@pytest.mark.parametrize("text", [
    "DNP", "", "   ", "RFIC", "R47", "/5k",      # no number first
    "3.3V", "74HC04", "1N4148", "10uFx", "1e3",  # a number, then text that is no prefix or unit
    "4n7n", "1.5k2", "4R7F", "1kk", "1.2.3",     # a prefix, unit or point in the wrong place
    "10UF", "100NF",                             # prefixes keep their case
    "100 mA", "100 NF", "5 V", "100 ohms", "100 X7R", "4 k7",  # a spaced word that is no unit
    "100,50V"])                                  # a decimal comma does not end a value
def test_text_that_is_not_a_value_gives_none(text):
    assert parse_value(text) is None


def test_values_are_the_exact_float_of_the_text():
    # a product of floats gives 1.0000000000000001e-07 for "100n", which would clutter project.json
    assert parse_value("100n") == (100e-9, "")
    assert parse_value("4.7u") == (4.7e-6, "")
    assert parse_value("3.3pF") == (3.3e-12, "F")
    assert parse_value("2k2") == (2200.0, "")


def test_a_long_run_of_digits_does_not_stall_the_parsers():
    junk = "1" * 20_000 + "x"  # two adjacent digit loops in a pattern need seconds for this
    start = time.perf_counter()
    assert parse_value(junk) is None
    with pytest.raises(KrsError):
        parse_frequency(junk)
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("text, hz", [
    ("915 MHZ", 915e6), ("915Mhz", 915e6), ("915mHz", 915e6), ("915M", 915e6),  # m: mega, not milli
    ("2.4GHz", 2.4e9), ("2.4g", 2.4e9), ("100kHz", 1e5), ("100 K", 1e5), ("433.92MHz", 433.92e6),
    ("868.3 MHz", 868.3e6), (".915GHz", 915e6), ("1e9", 1e9), ("1E9", 1e9), ("2.4e9 Hz", 2.4e9),
    ("915000000", 915e6), ("915 Hz", 915.0), ("  915MHz  ", 915e6),
    ("2.14GHz", 2.14e9), ("2.11 GHz", 2.11e9)])  # 2.14 * 1e9 is 2140000000.0000002 in floats
def test_frequency_forms(text, hz):
    assert parse_frequency(text) == hz


@pytest.mark.parametrize("text", [
    "abc", "", "   ", "MHz", "Hz", "915 XHz", "915MHzz", "915M Hz", "-915MHz", "+915MHz",
    "nan", "inf", "1_000", "915 e6", "1e", "9 15",
    "0", "0Hz", "0.0 MHz", "1e-999",                 # not above zero
    "1e999", "1e308 kHz", "1e9999"])                 # not finite
def test_bad_frequency_reports_the_text(text):
    with pytest.raises(KrsError) as e:
        parse_frequency(text)
    assert e.value.code == "E_BAD_FREQUENCY" and e.value.params == {"text": text}
    assert f'"{text}"' in str(e.value)  # the message renders, with the text as typed


def test_a_giant_exponent_is_a_bad_frequency_and_not_a_crash():
    with pytest.raises(KrsError):  # int() refuses more than 4300 digits, so the pattern must
        parse_frequency("1e" + "9" * 5000)


# --- plan 3, task 2: decimal commas, RKM and part kinds ------------------------------------------


@pytest.mark.parametrize(("text", "value"), [
    ("4,7uF", 4.7e-6), ("4,7µF", 4.7e-6), ("2,2k", 2200.0), ("1,5nH", 1.5e-9), ("0,047uF", 4.7e-8),
    ("4n7", 4.7e-9), ("2k21", 2210.0), ("4R7", 4.7), ("1u0", 1e-6)])  # µ: the micro sign NFKC folds
def test_a_decimal_comma_and_rkm_read(text, value):  # C-2
    assert parse_value(text)[0] == pytest.approx(value, rel=1e-12)


@pytest.mark.parametrize("text", ["1,000", "1,000pF", "4,700pF", "4,7", "100,50V", "1n4148", "3.3.3pF"])
def test_ambiguous_values_stay_unreadable(text):
    assert parse_value(text) is None


@pytest.mark.parametrize(("ref", "text", "value"), [
    ("C1", "100n", 1e-7), ("L1", "15n", 1.5e-8), ("R1", "0R", 0.0), ("R2", "4k7", 4700.0), ("C12", "4,7uF", 4.7e-6),
    ("C1", "15nH", None), ("D1", "1N4148", None), ("FB1", "BLM18", None), ("CN1", "100n", None)])
def test_a_part_value_takes_its_kind_from_the_designator(ref, text, value):  # C-2, M-5
    assert part_value(ref, text) == (None if value is None else pytest.approx(value, rel=1e-12))


def test_part_kind():
    assert [part_kind(r) for r in ("C1", "L2", "R10", "D1", "CN1", "RF1")] == ["C", "L", "R", None, None, None]
