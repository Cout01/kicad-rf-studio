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
# RKM notation, where the letter stands for the point: 4n7 is 4.7n, 4R7 is 4.7R, 2k2 is 2.2k
_RKM = re.compile(rf"^(\d+)([pnu{_MU}mkKMGRr])(\d+)")
_EXP = {"": 0, "p": -12, "n": -9, "u": -6, _MU: -6, "m": -3, "k": 3, "K": 3, "M": 6, "G": 9,
        "meg": 6}
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
    k and K are both kilo and meg is mega in any case."""
    s = unicodedata.normalize("NFKC", text).lstrip()
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
