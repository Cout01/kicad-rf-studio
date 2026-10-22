# SPDX-License-Identifier: GPL-3.0-or-later
"""project.json, schema 1: the project and the job spec in one file. Its board path is relative to the project file
and has forward slashes, so a project folder and its board can move together.

Coordinates in it are in KiCad's frame: mm, with y pointing down, as KiCad shows them and as a user types them in. The
board as read (core.kicad) has y up, so a point [x, y] here is (x, -y) there, and the other way round.

Every key that make_project writes is required, `region` and `mesh` too, and only `results` is optional: read_project
names the first field that is missing or of the wrong kind (E_PROJECT_FIELD), so a file written by an older `new` is
re-created with `new`, never read with defaults."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING

from kicad_rf_studio.core.messages import KrsError, reason

if TYPE_CHECKING:  # the types only: project.py imports no board code
    from kicad_rf_studio.core.kicad.stackup import Stackup
    from kicad_rf_studio.core.kicad.tracer import Classes

SCHEMA = 1
EXPAND_H = 3.0  # substrate heights the ROI grows by past the chain (spec 5.1)
MESH_N = {"draft": 2, "normal": 2, "strict": 3}  # the mesh rule's n by preset (spec 5.4, plan 2 Decisions)
ROLES = ("port", "copper", "open", "grid", "curve_port")  # what a part is in the model (spec 5.7)
# ponytail: provisional constants, the same for every preset; the owner sets the time policy (spec 1.1) after P0-C.
DEFAULT_PRESET, HARMONICS, BAND_FACTOR, T_MAX_S = "normal", 3, 1.1, 40e-9
GATES = {"fit2d_limit": 0.03, "dt_floor": 0.8}  # ponytail: provisional until P0-A confirms them


def region_expand_h(data: dict) -> float:
    """project.json's region.expand_h, else EXPAND_H."""
    return data.get("region", {}).get("expand_h", EXPAND_H)


def mesh_n(data: dict) -> int:
    """project.json's mesh.n, else its preset's (MESH_N)."""
    return data.get("mesh", {}).get("n") or MESH_N[data["preset"]]


def parts(data: dict) -> dict[str, dict]:
    """project.json's parts by ref: chain.series, chain.shunt, then others. The dicts are the ones `data` holds, not
    copies, so an edit through them is an edit of `data`."""
    return {q["ref"]: q for q in (*data["chain"]["series"], *data["chain"]["shunt"], *data["others"])}


def shown_reference(ref: dict | None) -> str:
    """A port's stored reference as I_PORT and the port map show it: the pad's name, the point on its layer (KiCad's
    frame, as stored), or "none"."""
    if ref is None:
        return "none"
    if "pad" in ref:
        return ref["pad"]
    x, y = ref["point"]
    return f"({x:.3f}, {y:.3f}) on {ref['layer']}"


def board_hash(path: str | Path) -> str:
    """The SHA-256 of the file's bytes, in hex."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_project(board_path: str, board_sha256: str, f0_hz: float, stackup: Stackup, classes: Classes, chain: dict,
                 others: list[dict], ports: list[dict], *, harmonics: int = HARMONICS, preset: str = DEFAULT_PRESET,
                 lid_height_mm: float | None = None) -> dict:
    """project.json as `new` writes it, every key in its place: `chain` holds start, end, nets, series and shunt, its
    parts and `others` as project_parts gives them; the classes are written as computed, sorted (classify() reads any
    list that is present, even an empty one, as a replacement); the rest are the defaults, `lid` null (on when
    harmonics > 1) and `gates` a copy of GATES."""
    return {
        "schema": SCHEMA, "board": {"path": board_path, "sha256": board_sha256},
        "f0_hz": f0_hz, "harmonics": harmonics, "preset": preset, "band_factor": BAND_FACTOR, "t_max_s": T_MAX_S,
        "region": {"expand_h": EXPAND_H}, "mesh": {"n": MESH_N[preset]},
        "stackup": stackup.to_json(), "lid_height_mm": lid_height_mm, "lid": None,
        "classes": {"gnd_nets": sorted(classes.gnd), "power_nets": sorted(classes.power),
                    "connectors": sorted(classes.connectors), "shields": sorted(classes.shields)},
        "chain": chain, "others": others, "ports": ports, "gates": dict(GATES), "allow_curve_port": False}


def save_project(path: Path, data: dict) -> None:
    """Writes UTF-8 JSON, indented by 2 and with its non-ASCII text as it is. Lines end in "\\n" on every platform. The
    text goes to a temporary file next to `path`, which then replaces it, so a failed write never leaves half a
    project. It creates no folder."""
    # ponytail: one temporary name per target, so two writers of one project at once would clash; mkstemp if that
    # can happen
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def load_project(path: Path) -> dict:
    """The project as stored. Raises KrsError: E_PROJECT_UNREADABLE for a path that is not a file, or a file that is
    not UTF-8 JSON (a hand edit can break it); E_PROJECT_SCHEMA for a file that is not of this schema."""
    try:
        if not path.is_file():  # Windows reads a folder as PermissionError, so look before reading (as load_board)
            raise IsADirectoryError() if path.exists() else FileNotFoundError()
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig: an editor may have put a byte order mark in
    except (OSError, ValueError) as e:  # ValueError: UnicodeError or json.JSONDecodeError
        raise KrsError("E_PROJECT_UNREADABLE", path=str(path), reason=reason(e)) from None
    found = data.get("schema") if isinstance(data, dict) else None
    if found != SCHEMA:
        raise KrsError("E_PROJECT_SCHEMA", path=str(path), found=found, expected=SCHEMA)
    return data


def _number(v) -> bool:
    """A finite JSON number; a bool is none (json reads NaN and Infinity too)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _names(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _model(v) -> bool:
    """None, or a package preset as model_of gives it."""
    return v is None or (isinstance(v, dict) and isinstance(v.get("package"), str)
                         and all(_number(v.get(k)) and v[k] >= 0 for k in ("esl_h", "esr_ohm", "cp_f")))


def _reference(v) -> bool:
    """None, a pad ({"pad", "uuid"}, the uuid "" for a pad by its name alone) or a point on a layer ({"point": [x, y],
    "layer"}), as `new` writes them."""
    if v is None:
        return True
    if not isinstance(v, dict):
        return False
    if "pad" in v:
        return isinstance(v["pad"], str) and isinstance(v.get("uuid"), str)
    point = v.get("point")
    return (isinstance(point, list) and len(point) == 2 and all(map(_number, point))
            and isinstance(v.get("layer"), str))


# What check_project requires, in the file's order. A (test, text) pair is a field and the text says what it must be;
# a dict is an object with those fields; a (dict, text) pair is a list of such objects.
_TEXT = (lambda v: isinstance(v, str), "text")
_ABOVE_0 = (lambda v: _number(v) and v > 0, "a number above 0")
_FLAG = (lambda v: isinstance(v, bool), "true or false")
_TWO_NAMES = (lambda v: _names(v) and len(v) == 2, "two names")
_CLASS = (lambda v: v is None or _names(v), "a list of names, or null (computed from the board)")
_PARTS = ({"ref": _TEXT, "pads": _TWO_NAMES, "nets": _TWO_NAMES, "value": _TEXT, "dnp": _FLAG,
           "role": (lambda v: v in ROLES, "port, copper, open, grid or curve_port"),
           "model": (_model, "null, or package (text) with esl_h, esr_ohm and cp_f (numbers of 0 or more)"),
           "s2p": (lambda v: v is None or (isinstance(v, dict) and isinstance(v.get("file"), str)
                                           and v.get("connection") in ("series", "shunt")),
                   "null, or file (text) and connection (series or shunt)")},
          "a list of parts")
_FIELDS = {
    "board": {"path": _TEXT, "sha256": _TEXT},
    "f0_hz": _ABOVE_0,
    "harmonics": (lambda v: type(v) is int and v > 0, "a whole number above 0"),  # not isinstance: 3.0 and True fail
    "preset": (lambda v: v in tuple(MESH_N), "draft, normal or strict"),  # in a dict, a list would raise TypeError
    "band_factor": _ABOVE_0,
    "t_max_s": _ABOVE_0,
    "region": {"expand_h": _ABOVE_0},
    "mesh": {"n": (lambda v: type(v) is int and v >= 2, "a whole number of 2 or more")},
    "stackup": {"source": _TEXT, "layers": ({
        "name": _TEXT, "kind": (lambda v: v in ("mask", "copper", "dielectric"), "mask, copper or dielectric"),
        "thickness_mm": (lambda v: _number(v) and v >= 0, "a number of 0 or more"),
        "epsilon_r": (lambda v: v is None or _number(v) and v > 0, "a number above 0, or null"),
        "loss_tangent": (lambda v: v is None or _number(v) and v >= 0, "a number of 0 or more, or null")},
        "a list of layers")},
    "lid_height_mm": (lambda v: v is None or _number(v) and v > 0,
                      'a number above 0, or null ("lid": false leaves the lid out)'),
    "lid": (lambda v: v is None or isinstance(v, bool), "true, false or null"),
    "classes": dict.fromkeys(("gnd_nets", "power_nets", "connectors", "shields"), _CLASS),
    "chain": {"start": _TEXT, "end": _TEXT, "nets": (_names, "a list of names"), "series": _PARTS, "shunt": _PARTS},
    "others": _PARTS,
    "ports": ({"name": _TEXT, "signal": _TEXT, "signal_uuid": _TEXT, "layer": _TEXT,
               "rule": (lambda v: v in (None, "connector", "ic", "copper"), "connector, ic, copper or null"),
               "reference": (_reference, "a pad, a point or null")}, "a list of ports"),
    "gates": {"fit2d_limit": _ABOVE_0, "dt_floor": (lambda v: _number(v) and 0 < v <= 1,
                                                    "a number above 0 and at most 1")},
    "allow_curve_port": _FLAG}
_MISSING = object()  # a key that is not there, which no field accepts (null is a value)


def _check(value, spec, field: str, path: Path) -> None:
    """Raises E_PROJECT_FIELD for the first field of `value` that `spec` (_FIELDS or a part of it) refuses."""
    if isinstance(spec, dict):  # an object with these fields
        if not isinstance(value, dict):
            raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected="an object")
        for key, sub in spec.items():
            _check(value.get(key, _MISSING), sub, f"{field}.{key}" if field else key, path)
        return
    test, expected = spec
    if isinstance(test, dict) and isinstance(value, list):  # a list of objects with these fields
        for i, item in enumerate(value):
            _check(item, test, f"{field}[{i}]", path)
    elif isinstance(test, dict) or value is _MISSING or not test(value):
        raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected=expected)


def check_project(data: dict, path: Path) -> dict:
    """`data`, the project read from `path`, when each field has the kind and range that `new` writes (_FIELDS); else
    E_PROJECT_FIELD names the first that is missing or has not, with dots and [index] as in ports[0].reference (C-3).
    So a hand edit never ends in E_INTERNAL further on, nor in a field read as something it is not. `results` is
    optional, and an object."""
    _check(data, _FIELDS, "", path)
    if not isinstance(data.get("results", {}), dict):
        raise KrsError("E_PROJECT_FIELD", path=str(path), field="results", expected="an object")
    return data


def read_project(path: Path) -> dict:
    """The project at `path`, read (load_project) and checked (check_project)."""
    return check_project(load_project(path), path)


def board_file(path: Path, data: dict) -> Path:
    """The board file of the project at `path`. Its stored path is relative to the project file, not to the working
    directory; `load_project` leaves it as stored, so that a saved project keeps a relative path."""
    return (path.parent / data["board"]["path"]).resolve()
