# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import ctypes
import gettext
import locale
import os
import re
import string
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from kicad_rf_studio.core import messages
from kicad_rf_studio.core.kicad.sexpr import Quoted, atom, child, children, num, parse, repair
from kicad_rf_studio.core.messages import CATALOG, KrsError, reason, render


def test_parse_nested_quoted_and_escaped():
    root = parse('(a (b "x \\"y\\"") 1.5 sym)')
    assert root == ["a", ["b", 'x "y"'], "1.5", "sym"]
    assert isinstance(root[1][1], Quoted) and not isinstance(root[3], Quoted)


def test_helpers():
    root = parse('(pad "1" (at 1 -2 90) (size 0.5 0.6))')
    assert atom(root, "at") == "1" and num(root, "at", 3) == 90.0 and child(root, "drill") is None


def test_filter_ratio_repair():
    text, n = repair("(teardrop (curved_edges no)filter_ratio 0.9))")
    assert n == 1
    assert parse(text) == ["teardrop", ["curved_edges", "no"], ["filter_ratio", "0.9"]]


def test_unbalanced_reports_line():
    with pytest.raises(KrsError) as e:
        parse("(a\n (b\n")
    assert e.value.code == "E_PARSE_UNBALANCED" and e.value.params["line"] == 2


def test_every_template_formats():
    for code, template in CATALOG.items():
        fields = {f for _, f, _, _ in string.Formatter().parse(template) if f}
        assert render(code, **{f: "x" for f in fields})


# --- beyond the brief's five tests -------------------------------------------------------------


def test_brackets_need_no_spaces_and_empty_lists_are_kept():
    assert parse("(a(b)c ())") == ["a", ["b"], "c", []]


def test_quoted_text_is_not_tokenized_and_backslashes_resolve():
    root = parse(r'(s "b (c) d" "" "e\\f" "a\\")')
    assert root == ["s", "b (c) d", "", "e\\f", "a\\"]
    assert all(isinstance(x, Quoted) for x in root[1:])


def test_root_is_the_first_top_level_list():
    assert parse("(a 1) (b 2)") == ["a", "1"]


@pytest.mark.parametrize("text, line", [
    ("(a\n (b)\n (c)", 1),   # closed lists after the unclosed "(" do not count
    ("(a\r\n (b\r\n", 2),    # CRLF files
    ('(a "x\ny"\n (b', 3),   # a newline inside a string still counts
    ("(a\n b)\n )", 3),      # an extra ")" is reported where it appears
    ("(a))", 1),
])
def test_unbalanced_line(text, line):
    with pytest.raises(KrsError) as e:
        parse(text)
    assert e.value.code == "E_PARSE_UNBALANCED" and e.value.params["line"] == line


@pytest.mark.parametrize("text", ["", " \n ", "abc"])
def test_text_without_a_list_is_a_damaged_file(text):
    with pytest.raises(KrsError) as e:
        parse(text)
    assert e.value.code == "E_PARSE_UNBALANCED" and e.value.params["line"] == 1


def test_children_and_child_return_the_matching_sublists_in_order():
    root = parse("(m (n 1) x (n 2) (o))")
    assert children(root, "n") == [["n", "1"], ["n", "2"]]
    assert children(root, "zzz") == []
    assert child(root, "n") is children(root, "n")[0]


def test_atom_and_num_fall_back_to_the_default():
    root = parse('(m (o "x" 3.5) (p) (q (r 1)))')
    assert num(root, "o", 2) == 3.5 and num(root, "o", 2, default=0.0) == 3.5
    assert atom(root, "zzz") is None and atom(root, "zzz", default="d") == "d"
    assert num(root, "zzz") is None and num(root, "zzz", default=7.0) == 7.0
    assert atom(root, "p") is None and num(root, "o", 9, default=1.0) == 1.0  # index past the end
    assert atom(root, "q") is None   # a list is not an atom
    assert num(root, "o", 1) is None  # "x" is not a number


def test_atom_keeps_the_quoted_type():
    root = parse('(via (net 1 "SIG"))')
    assert not isinstance(atom(root, "net", 1), Quoted) and isinstance(atom(root, "net", 2), Quoted)


def test_repair_leaves_good_text_alone_and_keeps_the_whitespace():
    good = "(teardrops (curved_edges no) (filter_ratio 0.9))"
    assert repair(good) == (good, 0)
    assert repair("(t (c no)\n  filter_ratio 0.9)\n(t (c no)filter_ratio 1))") == (
        "(t (c no)\n  (filter_ratio 0.9)\n(t (c no)(filter_ratio 1))", 2)


def test_krs_error_carries_its_code_and_params_and_renders_them():
    err = KrsError("E_BOARD_VERSION", version=20231120)
    assert err.code == "E_BOARD_VERSION" and err.params == {"version": 20231120}
    assert str(err) == render("E_BOARD_VERSION", version=20231120)
    assert "20231120" in str(err) and "{" not in str(err)


@pytest.mark.parametrize("error, code, text", [
    (FileNotFoundError(2, "x"), "T_FILE_NOT_FOUND", "file not found"),
    (IsADirectoryError(21, "x"), "T_NOT_A_FILE", "not a file"),
    (PermissionError(13, "x"), "T_PERMISSION_DENIED", "permission denied"),
    (FileExistsError(17, "x"), "T_EXISTS_AS_FILE", "already exists as a file"),
    (NotADirectoryError(20, "x"), "T_EXISTS_AS_FILE", "already exists as a file"),  # a folder on the way is a file
    (UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid continuation byte"), "T_NOT_UTF8", "not UTF-8 text"),
    (OSError(22, "x"), "T_CANNOT_READ", "cannot be read"), (OSError(), "T_CANNOT_READ", "cannot be read")])
def test_a_file_error_has_a_short_reason_by_its_class(error, code, text):  # a code, rendered when shown
    assert reason(error) == code and render(code) == text


def test_render_falls_back_to_the_english_template():
    assert render("I_WROTE", path="out.json") == "Wrote out.json."


def test_render_translates_the_template_and_then_fills_it_in(monkeypatch):
    class Translation:
        def gettext(self, msgid):  # a translation catalog is keyed by the English template
            return {"Wrote {path}.": "[translated] Wrote {path}."}.get(msgid, msgid)

    monkeypatch.setattr(messages, "_translation", Translation())
    assert render("I_WROTE", path="out.json") == "[translated] Wrote out.json."


GETTEXT_VARIABLES = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")


@pytest.fixture
def no_gettext_variable(monkeypatch):
    for name in GETTEXT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(("ui", "chosen"), [
    (0x0416, ["pt_BR"]),  # Portuguese (Brazil)
    (0x0816, ["en"]),  # Portuguese (Portugal) is not pt-BR (design 3)
    (0x0409, ["en"]),  # an English Windows, whatever its regional format (Review Focus 5)
    (0, ["en"])])  # not Windows
def test_with_no_gettext_variable_windows_display_language_picks_the_language(no_gettext_variable, monkeypatch, ui,
                                                                              chosen):  # pt-BR design 4
    monkeypatch.setattr(messages, "_ui_language", lambda: ui)
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("pt_BR", "cp1252"))  # the regional format is never read
    assert messages._languages() == chosen


@pytest.mark.parametrize("name", GETTEXT_VARIABLES)
def test_a_gettext_variable_wins_over_windows_display_language(no_gettext_variable, monkeypatch, name):
    monkeypatch.setattr(messages, "_ui_language", lambda: 0x0416)
    monkeypatch.setenv(name, "")  # empty is unset, as gettext reads it
    assert messages._languages() == ["pt_BR"]
    monkeypatch.setenv(name, "C")
    assert messages._languages() is None  # gettext reads it itself (Task 4 runs C and pt_BR.UTF-8)


def test_language_names_the_catalog_that_loaded(monkeypatch):  # pt-BR design 4: for Qt's translator and the tests
    class PtBr(gettext.NullTranslations):
        def info(self):
            return {"language": "pt_BR"}

    monkeypatch.setattr(messages, "_translation", gettext.NullTranslations())
    assert messages.language() == "en"
    monkeypatch.setattr(messages, "_translation", PtBr())
    assert messages.language() == "pt_BR"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' display language")
def test_windows_display_language_is_read_through_ctypes():
    assert 0 < messages._ui_language() <= 0xFFFF  # a LANGID


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' display language")
def test_windows_display_language_keeps_only_the_langids_16_bits(monkeypatch):  # final review
    monkeypatch.setattr(ctypes.windll.kernel32, "GetUserDefaultUILanguage", lambda: 0x7FFF0416)  # stray high bits
    assert messages._ui_language() == 0x0416


def test_the_suite_pins_its_language_before_anything_reads_it():  # pt-BR design 4, 7.2
    assert os.environ["LANGUAGE"] == (os.environ.get("KRS_TEST_LANGUAGE") or "en")
    assert messages.language() == os.environ["LANGUAGE"]  # a misplaced pin loads Windows' pt-BR here


ROOT = Path(__file__).resolve().parents[1]


def test_every_template_is_its_own_msgid_and_a_term_takes_no_field():  # pt-BR design 5.1: gettext keys on it
    assert len(set(CATALOG.values())) == len(CATALOG)  # T_NONE takes G_NONE's "none"
    assert [code for code in CATALOG if code.startswith("T_") and "{" in CATALOG[code]] == []  # rendered bare


def test_a_term_parameter_renders_in_the_language_and_none_as_unknown(monkeypatch):  # pt-BR design 5.1
    assert render("E_UNKNOWN_PAD", name="X", candidates="T_NONE") == render("E_UNKNOWN_PAD", name="X",
                                                                            candidates="none")
    assert render("E_LOCKED", lock="L", run=None, started=None) == render("E_LOCKED", lock="L", run="unknown",
                                                                           started="unknown")
    assert render("I_WROTE", path="T_max") == "Wrote T_max."  # only a code of CATALOG is a term

    class Translation:
        def gettext(self, msgid):
            return {"none": "—"}.get(msgid, msgid)

    monkeypatch.setattr(messages, "_translation", Translation())
    assert render("E_UNKNOWN_PAD", name="X", candidates="T_NONE").endswith(": —.")


def test_every_literal_reason_fallback_and_job_name_is_a_term():  # pt-BR design 5.1; Review Focus 3
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "src").rglob("*.py")))
    words = r'reason\(\w+, "(?!T_)[^"]*"|reason="(?!T_)[^"]*"|check_job\(.*?, "(?!T_)[^"]*"'
    assert re.findall(words, text) == []  # each found with its call: make the word a T_ code


PT_PO = ROOT / "po" / "pt_BR.po"
PT_MO = messages.LOCALE / "pt_BR" / "LC_MESSAGES" / "kicad_rf_studio.mo"


def po_pairs(text):
    """A .po's msgid → msgstr pairs, its header's ("") among them: each string's quoted lines joined (Babel escapes only
    the backslash, tab, CR, LF and double quote, which literal_eval reads alike)."""
    def join(block):
        return "".join(ast.literal_eval(line) for line in block.splitlines())
    return {join(i): join(s) for i, s in re.findall(r'^msgid ((?:".*"\n)+)msgstr ((?:".*"\n)+)', text, re.M)}


def mo_pairs(path=PT_MO):
    """A compiled catalog's msgid → msgstr pairs, its header left out."""
    with path.open("rb") as f:  # ponytail: GNUTranslations' private _catalog, stable since Python 2: no public list
        return {k: v for k, v in gettext.GNUTranslations(f)._catalog.items() if k}


def fields(text):
    """Each replacement field of `text` as (name, format spec, conversion); None for a brace str.format refuses."""
    try:
        return {(name, spec, conv) for _, name, spec, conv in string.Formatter().parse(text) if name is not None}
    except ValueError:  # an unbalanced brace: a mismatch, named by its msgid
        return None


def test_the_compiled_catalog_is_its_po_translated_and_ships_in_the_wheel():  # pt-BR design 7.1, 7.2; RF 2
    text = PT_PO.read_text(encoding="utf-8")
    assert set(po_pairs(text)) - {""} == set(CATALOG.values())  # after a change to CATALOG, run tools/catalog.py
    assert mo_pairs() == {i: s for i, s in po_pairs(text).items() if i and s}  # after a .po edit, the same
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]
    assert "locale/*/LC_MESSAGES/*.mo" in data["kicad_rf_studio"]  # the wheel compiles nothing (design 7.1)


def test_every_translation_keeps_its_fields_and_line_breaks_with_no_spec_or_conversion():  # design 3, 7.2; RF 1
    assert [m for m, s in mo_pairs().items() if (fields(s), s.count("\n")) != (fields(m), m.count("\n"))] == []


@pytest.mark.parametrize(("env", "shown"), [
    ({"LANG": "pt_BR.UTF-8"}, "pt_BR"),  # a Linux desktop's: no code (design 4)
    ({"LANGUAGE": "en", "LANG": "pt_BR.UTF-8"}, "en"),  # LANGUAGE first: the README's way to keep English
    ({"LANG": "C"}, "en"), ({"LC_ALL": "C.UTF-8"}, "en"),  # Review Focus 5
    ({"LANG": "pt_PT.UTF-8"}, "en")])  # pt-PT is not pt-BR (design 3)
def test_the_package_catalog_follows_the_gettext_variables(env, shown):  # pt-BR design 4, 7.1
    base = {k: v for k, v in os.environ.items() if k not in GETTEXT_VARIABLES}
    probe = "from kicad_rf_studio.core import messages; print(messages.language())"
    out = subprocess.run([sys.executable, "-I", "-c", probe], env={**base, **env}, capture_output=True, text=True)
    assert out.stdout.strip() == shown, out.stderr


QUOTED = {  # a G_ message that names a widget, and that widget's label codes (design 6.2 rule 4)
    "G_LOCKED": ("G_STOP",), "G_RUN_START": ("G_STOP",), "G_WHAT_IF": ("G_VERIFY",), "G_NO_COST": ("G_RUN",),
    "G_COST_REUSED": ("G_RUN",), "G_PROJECT_EXISTS": ("G_OPEN",), "G_LID_HEIGHT_MISSING": ("G_TAB_ADVANCED",),
    "G_NO_REFERENCE": ("G_TAB_ADVANCED",), "G_PART_NO_MODEL": ("G_TAB_RESULTS",), "G_VERIFY_NONE": ("G_VERIFY",),
    "G_VERIFY_STALE": ("G_VERIFY",), "G_APPLY_FIRST": ("G_VERIFY", "G_APPLY"),
    "G_VERIFY_VALUE": ("G_VERIFY", "G_TAB_ADVANCED", "G_TAB_RESULTS", "G_APPLY"),
    "G_PROJECT_FIELD": ("G_TAB_ADVANCED", "G_NEW")}
# what a msgstr keeps of its msgid (design 3, 6.2 rule 3): a command in backticks, quoted JSON, an option, a file-dialog
# filter, a dotted number, and a file, field or variable name (project.json, mesh.n, ports[].reference, t_max_s, STOP)
KEEP = re.compile(r'`[^`]+`|"[^"]*"|--[a-z][\w-]*|\(\*\.\w+\)|\d+(?:\.\d+)+|\w+(?:\[\])?(?:\.\w+)+|\w*_\w+|\bSTOP\b')


def test_the_pt_br_catalog_translates_every_template_and_nothing_else():  # pt-BR design 7.2; Review Focus 2
    assert set(mo_pairs()) == set(CATALOG.values())


def test_a_label_quoted_in_a_message_is_its_widgets_label_and_kicads_labels_are_kicads():  # design 6.1, 6.2; RF 4
    pt = mo_pairs()
    for text in (CATALOG.get, lambda code: pt[CATALOG[code]]):  # English, then pt-BR
        assert [code for code, labels in QUOTED.items() if not all(text(label) in text(code) for label in labels)] == []
    for code in ("E_KICAD_UNREACHABLE", "I_PLUGIN_NEXT"):
        assert "Preferências › Plug-ins › Ativar a API do KiCad" in pt[CATALOG[code]], code
    assert "Configuração da placa › Empilhamento físico" in pt[CATALOG["E_DIELECTRIC_THICKNESS"]]
    assert [m for m in CATALOG.values() if "(B)" in m and "Preencher todas as zonas (B)" not in pt[m]] == []


def test_the_pt_br_catalog_keeps_the_glossarys_nevers():  # design 6.1 (preencher, executar, gate), 6.2 rule 1
    pt = mo_pairs()
    never = re.compile(r"\b(recarreg\w*|rod(?:a|am|amos|ando|ar|ará|arão|aria|ariam|aram|ava|avam|e|em|ou)|tu|favor"
                       r"|o usuário)\b", re.I)
    assert all(never.search(w) for w in ("rodar", "roda", "rodam", "rodou", "rodando")) and not never.search("rodapé")
    assert [msgid for msgid, msgstr in pt.items() if never.search(msgstr)] == []
    gates = [CATALOG[code] for code in ("I_GATES_PASSED", "I_GATES_PASSED_PML", "G_END_BLOCKED")
             if CATALOG[code] in pt]  # a gate, in prose
    assert [m for m in gates if "checage" not in pt[m].lower() or "verifica" in pt[m].lower()] == []


def test_every_translation_keeps_the_identifiers_numbers_filters_and_ellipses():  # design 3, 6.2 rules 3, 6; RF 1
    assert KEEP.findall("project.json, mesh.n, ports[].reference, t_max_s, STOP") == [
        "project.json", "mesh.n", "ports[].reference", "t_max_s", "STOP"]
    pt = mo_pairs()
    assert [m for m, s in pt.items()
            if any(k not in s for k in KEEP.findall(m)) or m.endswith("…") != s.endswith("…")] == []
    filters = [CATALOG[code] for code in ("G_OPEN_FILTER", "G_BOARD_FILTER", "G_S2P_FILTER") if CATALOG[code] in pt]
    assert [m for m in filters if not pt[m].endswith(m.split()[-1])] == []  # Qt reads the filter at the end
