# SPDX-License-Identifier: GPL-3.0-or-later
"""Part values and frequencies as plain SI floats: `10uF/16V` is (1e-05, "F"), `915MHz` is 915e6."""
import math
import re
import unicodedata

from kicad_rf_studio.core.messages import KrsError

# parse_value folds its text with NFKC, which turns the micro sign (U+00B5) into the Greek mu and
# the ohm sign (U+2126) into the Greek omega, so only those two are spelled here. They are written
# by name because the look-alikes cannot be told apart on screen.
_MU = "\N{GREEK SMALL LETTER MU}"
_OMEGA = "\N{GREEK CAPITAL LETTER OMEGA}"
_NUMBER = r"\d+(?:\.\d+)?|\.\d+"  # not \d*\.?\d+: its two digit loops backtrack quadratically
# A value ends at a space, a "/" or the end of the text, or at a "," that follows a letter: after a
# digit the "," may be a decimal comma (4,7uF), and 4 would be wrong.
_VALUE = re.compile(rf"({_NUMBER})((?i:meg)|[pnu{_MU}mkKMG])?((?i:[FHR]|ohm)|{_OMEGA})?"
                    r"(?=[/\s]|$|(?<=\D),)")
# "100 nF" is "100nF": a space between the number and a letter is dropped. That word must then be a
# prefix and unit, or the text is None. A word that starts with a digit or sign ("100 50V") is left
# alone and ignored, like any text after the value.
_SPACED = re.compile(rf"^({_NUMBER})\s+(?=[^\W\d_])")
# A decimal comma, 4,7uF, is a point when 1 to 3 digits and then a prefix or unit letter follow it
_COMMA = re.compile(rf"^(\d+),(\d{{1,3}})(?=(?i:meg|ohm|[fhr])|[pnu{_MU}mkKMG{_OMEGA}])")
# RKM notation, where the letter stands for the point: 4n7 is 4.7n, 4R7 is 4.7R, 2k2 is 2.2k. At most 3
# digits follow the letter, and no more, so 1n4148 (a diode) is no value.
_RKM = re.compile(rf"^(\d+)([pnu{_MU}mkKMGRr])(\d{{1,3}})(?!\d)")
_EXP = {"": 0, "p": -12, "n": -9, "u": -6, _MU: -6, "m": -3, "k": 3, "K": 3, "M": 6, "G": 9,
        "meg": 6}
_UNIT = {"C": "F", "L": "H", "R": "R"}  # a part kind and the unit its value may name
# at most 3 exponent digits, so that int() never meets the 4300 it refuses
_FREQUENCY = re.compile(rf"({_NUMBER})(?:e([+-]?\d{{1,3}}))?\s*([kmg])?(?:hz)?", re.IGNORECASE)
_FREQUENCY_EXP = {"": 0, "k": 3, "m": 6, "g": 9}


def parse_value(text: str) -> tuple[float, str] | None:
    """A part value such as `10uF/16V`, `100 nF`, `4k7`, `0R` or `1meg` as (SI value, kind), or
    None when the text is not one.

    The value is a number with an optional prefix and unit, and a space between the number and a
    letter is dropped. It ends at a space, "/" or "," (or the end), and what follows is ignored;
    anything else stuck to it makes the text None, so that no value is invented. The kind is
    "F", "H" or "R" when the value names a unit (F, H and R in any case, Ω, ohm in any case, and
    the R of `4R7`), else "". Prefixes keep their case, so m is milli and M is mega, except that
    k and K are both kilo and meg is mega in any case. A decimal comma followed by a prefix or unit
    is a point (`4,7uF`, `0,047uF`), but not after a whole number other than 0 when 3 digits follow,
    where it may be a thousands separator: `1,000pF` is None."""
    s = unicodedata.normalize("NFKC", text).lstrip()
    m = _COMMA.match(s)
    if m and len(m[2]) == 3 and m[1] != "0":
        return None
    s = _COMMA.sub(r"\1.\2", s)
    # the RKM letter goes first: "4 k7" must not become 4.7k
    m = _VALUE.match(_SPACED.sub(r"\1", _RKM.sub(r"\1.\3\2", s)))
    if not m:
        return None
    num, prefix, unit = (g or "" for g in m.groups())
    exp = _EXP[prefix if prefix in _EXP else prefix.lower()]  # the lower() is for MEG and Meg
    unit = unit.upper()
    # the exponent goes into the text, so "100n" is exactly 100e-9, where 100 * 1e-9 would be
    # 1.0000000000000001e-07 and show up in project.json
    return float(f"{num}e{exp}"), unit if unit in ("", "F", "H") else "R"


def part_kind(ref: str) -> str | None:
    """The kind of part a reference names, when its leading letters are exactly "C", "L" or "R": C12 is
    "C", while CN1 (a connector) and RF1 are None."""
    letters = re.match(r"[A-Za-z]*", ref)[0]
    return letters if letters in _UNIT else None


def part_value(ref: str, text: str) -> float | None:
    """The SI value of a capacitor, inductor or resistor (`part_kind`) whose text reads with that part's
    unit, F, H or R, or with none: 100n on C1 is 1e-07, while 15nH on C1 and any text on D1 are None."""
    kind, value = part_kind(ref), parse_value(text)
    return value[0] if kind and value and value[1] in ("", _UNIT[kind]) else None


def port_value(ref: str, text: str) -> float | None:
    """`part_value`, but None for a C of 0: an open, whose infinite impedance would make every output NaN."""
    value = part_value(ref, text)
    return None if value == 0 and part_kind(ref) == "C" else value


def parse_frequency(text: str) -> float:
    """A frequency such as `915MHz`, `0.915 GHz` or `915e6` in Hz. Text that is not one, or whose
    value is not finite and above zero, raises E_BAD_FREQUENCY. The k, M and G prefixes and the Hz
    unit are case-insensitive, so `915mhz` is 915 MHz: nobody means millihertz here."""
    m = _FREQUENCY.fullmatch(text.strip())
    if m:
        mantissa, exp, prefix = m.groups()
        hz = float(f"{mantissa}e{int(exp or 0) + _FREQUENCY_EXP[(prefix or '').lower()]}")
        if 0 < hz < math.inf:
            return hz
    raise KrsError("E_BAD_FREQUENCY", text=text)


# IEC 60063's E12 and E24 series, one decade each
E12 = (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)
E24 = (1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
       3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1)


def snap(value: float, series: str) -> float:
    """The `series` value ("E12" or "E24", IEC 60063) nearest to `value` (> 0) in log space, as the decimal it is
    written as; a tie goes to the lower (Stage 2 design 5.2 item 8)."""
    decade = math.floor(math.log10(value))
    candidates = [float(f"{m}e{e}") for m in {"E12": E12, "E24": E24}[series] for e in range(decade - 1, decade + 2)]
    return min(candidates, key=lambda c: (abs(math.log(c / value)), c))


def value_text(value: float, kind: str | None) -> str:
    """`value` (> 0) as a part value that port_value reads back exactly: an engineering prefix from p to G, and F for a
    C or H for an L (4.7pF, 15nH, 4.7k); how snapping writes a value back (Stage 2 design 5.3)."""
    exp = min(max(3 * math.floor(math.log10(value) / 3 + 1e-9), -12), 9)  # the 1e-9 keeps a decade exact
    prefix = {-12: "p", -9: "n", -6: "u", -3: "m", 0: "", 3: "k", 6: "M", 9: "G"}[exp]
    unit = {"C": "F", "L": "H"}.get(kind, "")
    return f"{value / 10 ** exp:g}{prefix}{unit}"
