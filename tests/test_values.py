# SPDX-License-Identifier: GPL-3.0-or-later
import time

import pytest

from kicad_rf_studio.core.kicad.values import parse_frequency, parse_value
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


@pytest.mark.parametrize("text", [
    "DNP", "", "   ", "RFIC", "R47", "/5k",      # no number first
    "3.3V", "74HC04", "1N4148", "10uFx", "1e3",  # a number, then text that is no prefix or unit
    "4n7n", "1.5k2", "4R7F", "1kk", "1.2.3"])    # a prefix, unit or point in the wrong place
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
    "nan", "inf", "1_000", "915 e6", "1e", "9 15"])
def test_bad_frequency_reports_the_text(text):
    with pytest.raises(KrsError) as e:
        parse_frequency(text)
    assert e.value.code == "E_BAD_FREQUENCY" and e.value.params == {"text": text}
    assert f'"{text}"' in str(e.value)  # the message renders, with the text as typed
