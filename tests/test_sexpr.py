# SPDX-License-Identifier: GPL-3.0-or-later
import string

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


@pytest.mark.parametrize("error, text", [
    (FileNotFoundError(2, "x"), "file not found"), (IsADirectoryError(21, "x"), "not a file"),
    (PermissionError(13, "x"), "permission denied"), (FileExistsError(17, "x"), "already exists as a file"),
    (NotADirectoryError(20, "x"), "already exists as a file"),  # a folder on the way is a file
    (UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid continuation byte"), "not UTF-8 text"),
    (OSError(22, "x"), "cannot be read"), (OSError(), "cannot be read")])
def test_a_file_error_has_a_short_reason_by_its_class(error, text):
    assert reason(error) == text


def test_render_falls_back_to_the_english_template():
    assert render("I_WROTE", path="out.json") == "Wrote out.json."


def test_render_translates_the_template_and_then_fills_it_in(monkeypatch):
    class Translation:
        def gettext(self, msgid):  # a translation catalog is keyed by the English template
            return {"Wrote {path}.": "[translated] Wrote {path}."}.get(msgid, msgid)

    monkeypatch.setattr(messages, "_translation", Translation())
    assert render("I_WROTE", path="out.json") == "[translated] Wrote out.json."
