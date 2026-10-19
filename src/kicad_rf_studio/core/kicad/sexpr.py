# SPDX-License-Identifier: GPL-3.0-or-later
"""Reader for KiCad's S-expression files: nested lists of atoms, plus helpers to pick nodes apart."""
import re

from kicad_rf_studio.core.messages import KrsError

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')
_ESCAPE = re.compile(r'\\(["\\])')
_FILTER_RATIO = re.compile(r"\)(\s*)filter_ratio\b")


class Quoted(str):
    """An atom that was written in double quotes."""


def repair(text: str) -> tuple[str, int]:
    """Fix KiCad 9's teardrop writer bug, which writes `filter_ratio` without its "(".
    Returns the text and the number of fixes."""
    return _FILTER_RATIO.subn(r")\1(filter_ratio", text)


def parse(text: str) -> list:
    """The root node: the first top-level list, whose first item is its head symbol.

    Atoms are str; quoted ones are Quoted, with the escapes for a quote and a backslash resolved
    (other escapes stay as written). Unbalanced brackets raise E_PARSE_UNBALANCED with the line of
    the last unclosed "(" or of an extra ")"; text with no list at all reports line 1."""
    cur = []  # the list being filled; the top level to begin with
    stack = []  # per open "(": the enclosing list and the offset of that "("
    for m in _TOKEN.finditer(text):
        tok = m[0]
        if tok == "(":
            new = []
            cur.append(new)
            stack.append((cur, m.start()))
            cur = new
        elif tok == ")":
            if not stack:
                raise _unbalanced(text, m.start())
            cur = stack.pop()[0]
        elif tok[0] == '"':
            cur.append(Quoted(_ESCAPE.sub(r"\1", tok[1:-1])))
        else:
            cur.append(tok)
    if stack:
        raise _unbalanced(text, stack[-1][1])
    for item in cur:
        if isinstance(item, list):
            return item
    raise _unbalanced(text, 0)


def _unbalanced(text: str, offset: int) -> KrsError:
    # lines are counted here, on the error path only, so the happy path never tracks them
    return KrsError("E_PARSE_UNBALANCED", line=text.count("\n", 0, offset) + 1)


def _with_head(node: list, head: str):
    return (c for c in node if isinstance(c, list) and c and c[0] == head)


def children(node: list, head: str) -> list[list]:
    """The sub-lists of `node` whose first item is `head`."""
    return list(_with_head(node, head))


def child(node: list, head: str) -> list | None:
    """The first sub-list of `node` whose first item is `head`, or None."""
    return next(_with_head(node, head), None)


def atom(node: list, head: str, i: int = 1, default: str | None = None) -> str | None:
    """Item `i` of the child `head` when that is an atom (Quoted stays Quoted), else `default`."""
    c = child(node, head)
    return c[i] if c and 0 <= i < len(c) and isinstance(c[i], str) else default


def num(node: list, head: str, i: int = 1, default: float | None = None) -> float | None:
    """Item `i` of the child `head` as a float, or `default` when it is missing or not a number."""
    try:
        return float(atom(node, head, i))
    except (TypeError, ValueError):
        return default
