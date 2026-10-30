# SPDX-License-Identifier: GPL-3.0-or-later
"""project.json, schema 1 for a matching chain and schema 2 for an antenna (Stage 3 design 5.1): the project and the
job spec in one file. Its board path is relative to the project file and has forward slashes, so a project folder and
its board can move together.

Coordinates in it are in KiCad's frame: mm, with y pointing down, as KiCad shows them and as a user types them in. The
board as read (core.kicad) has y up, so a point [x, y] here is (x, -y) there, and the other way round.

Every key that make_project writes is required, `region` and `mesh` too, but `mesh.reach_h` and `region.margin_scale`
(D-12): a file from plan 4 lacks them and reads today's defaults, so since D-37 (reach 6) its results read stale
(E_RESULTS_STALE). `results` is optional as well. read_project names the first field that is missing or of the wrong
kind (E_PROJECT_FIELD), so a file that lacks any other key, written by an older `new`, is re-created with `new`, never
read with defaults."""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING

from kicad_rf_studio.core.messages import KrsError, reason
from kicad_rf_studio.core.model.csx import NF2FF_MAX

if TYPE_CHECKING:  # the types only: project.py imports no board code
    from kicad_rf_studio.core.kicad.stackup import Stackup
    from kicad_rf_studio.core.kicad.tracer import Classes

SCHEMA = 1
SCHEMA_ANTENNA = 2  # an antenna project (Stage 3 design 5.1); v1's stay SCHEMA
FAR_FIELD_STEP = 5  # the far field's full sphere is sampled every 5° (Stage 3 design 5.5)
EXPAND_H = 3.0  # substrate heights the ROI grows by past the chain (spec 5.1)
MARGIN_SCALE = 1.0  # the factor on the walls' margin past the ROI, WALL_MM + WALL_CELLS·coarse (D-12)
MESH_N = {"draft": 2, "normal": 2, "strict": 3}  # the mesh rule's n by preset (spec 5.4, plan 2 Decisions)
REACH_H = 6.0  # the protected set's reach in substrate heights (spec 5.4, D-12); P0-B raised it from 3 (D-37)
ROLES = ("port", "copper", "open", "grid", "curve_port")  # what a part is in the model (spec 5.7)
# ponytail: provisional constants, the same for every preset; the owner sets the time policy (spec 1.1) after P0-C.
DEFAULT_PRESET, HARMONICS, BAND_FACTOR, T_MAX_S = "normal", 3, 1.1, 40e-9
# P0-A confirmed the fit2d limit and the floor on 2026-10-24 and again under plan 6's mesh rule on 2026-10-26
# (docs/validation/2026-10-26-p0-a.md)
GATES = {"fit2d_limit": 0.03, "dt_floor": 0.8}


def antenna(data: dict) -> bool:
    """Whether project.json `data` is an antenna's, schema SCHEMA_ANTENNA (Stage 3 design 5.1)."""
    return data.get("schema") == SCHEMA_ANTENNA


def pulse_band(f_lo: float, f_hi: float) -> tuple[float, float]:
    """The pulse's band (f1, f2) of an antenna's band, in Hz (Stage 3 design 5.4): f_lo/1.3 rounded down and 1.2·f_hi
    rounded up, each to 3 significant digits, as floats."""
    def digits_3(v: float, to_whole) -> float:
        unit = 10 ** (math.floor(math.log10(v)) - 2)
        return float(to_whole(round(v / unit, 6)) * unit)  # round first: float noise cannot bump 300.0 to 301

    return digits_3(f_lo / 1.3, math.floor), digits_3(1.2 * f_hi, math.ceil)


def region_expand_h(data: dict) -> float:
    """project.json's region.expand_h, else EXPAND_H."""
    return data.get("region", {}).get("expand_h", EXPAND_H)


def region_margin_scale(data: dict) -> float:
    """project.json's region.margin_scale, else MARGIN_SCALE."""
    return data.get("region", {}).get("margin_scale", MARGIN_SCALE)


def mesh_reach_h(data: dict) -> float:
    """project.json's mesh.reach_h, else REACH_H."""
    return data.get("mesh", {}).get("reach_h", REACH_H)


def mesh_n(data: dict) -> int:
    """project.json's mesh.n, else its preset's (MESH_N)."""
    return data.get("mesh", {}).get("n") or MESH_N[data["preset"]]


def parts(data: dict) -> dict[str, dict]:
    """project.json's parts by ref: chain.series, chain.shunt, then others. The dicts are the ones `data` holds, not
    copies, so an edit through them is an edit of `data`."""
    return {q["ref"]: q for q in (*data["chain"]["series"], *data["chain"]["shunt"], *data["others"])}


def shown_reference(ref: dict | None) -> str:
    """A port's stored reference as the port map shows it: the pad's name, the point on its layer (KiCad's frame, as
    stored), or "none"."""
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
        "region": {"expand_h": EXPAND_H, "margin_scale": MARGIN_SCALE},
        "mesh": {"n": MESH_N[preset], "reach_h": REACH_H},
        "stackup": stackup.to_json(), "lid_height_mm": lid_height_mm, "lid": None,
        "classes": {"gnd_nets": sorted(classes.gnd), "power_nets": sorted(classes.power),
                    "connectors": sorted(classes.connectors), "shields": sorted(classes.shields)},
        "chain": chain, "others": others, "ports": ports, "gates": dict(GATES), "allow_curve_port": False}


def make_antenna_project(board_path: str, board_sha256: str, f_lo_hz: float, f_hi_hz: float, stackup: Stackup,
                         classes: Classes, chain: dict, others: list[dict], ports: list[dict], ref: str,
                         join: list[str], *, t_max_s: float, air_gap_mm: float, preset: str = DEFAULT_PRESET,
                         lid_height_mm: float | None = None) -> dict:
    """project.json of an antenna (schema 2, Stage 3 design 5.1) as `new --antenna` writes it: make_project's dict but
    harmonics and band_factor, with schema SCHEMA_ANTENNA, f0_hz the band's centre, `t_max_s`, region {"expand_h":
    REACH_H} (the measured region reaches as far as the protected set) and lid true (every shield gets its lid, 5.3);
    then kind, band, antenna {"ref", "join"}, `air_gap_mm`, boundary "pml_8" and far_field {"f_hz": f0 then 10
    frequencies evenly from f_lo to f_hi, "step_deg": FAR_FIELD_STEP}."""
    f0 = (f_lo_hz + f_hi_hz) / 2
    data = make_project(board_path, board_sha256, f0, stackup, classes, chain, others, ports, preset=preset,
                        lid_height_mm=lid_height_mm)
    del data["harmonics"], data["band_factor"]
    data.update(schema=SCHEMA_ANTENNA, t_max_s=t_max_s, region={"expand_h": REACH_H}, lid=True)  # in their places
    data.update(kind="antenna", band={"f_lo_hz": f_lo_hz, "f_hi_hz": f_hi_hz}, antenna={"ref": ref, "join": join},
                air_gap_mm=air_gap_mm, boundary="pml_8",
                far_field={"f_hz": [f0, *(f_lo_hz + (f_hi_hz - f_lo_hz) * k / 9 for k in range(10))],
                           "step_deg": FAR_FIELD_STEP})  # appended, in this order
    return data


def save_project(path: Path, data: dict) -> None:
    """Writes UTF-8 JSON, indented by 2 and with its non-ASCII text as it is. Lines end in "\\n" on every platform. The
    text goes to a temporary file next to `path`, which then replaces it, so a failed write never leaves half a
    project; an OSError on the way removes the temporary file and is raised again. It creates no folder."""
    # ponytail: one temporary name per target, so two writers of one project at once would clash; mkstemp if that
    # can happen
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    except OSError:
        with contextlib.suppress(OSError):  # never made, or held as well
            os.remove(temporary)
        raise


def load_project(path: Path) -> dict:
    """The project as stored. Raises KrsError: E_PROJECT_UNREADABLE for a path that is not a file, or a file that is
    not UTF-8 JSON (a hand edit can break it); E_PROJECT_SCHEMA for a file of neither SCHEMA nor SCHEMA_ANTENNA, its
    `expected` SCHEMA_ANTENNA, the newest it reads."""
    try:
        if not path.is_file():  # Windows reads a folder as PermissionError, so look before reading (as load_board)
            raise IsADirectoryError() if path.exists() else FileNotFoundError()
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig: an editor may have put a byte order mark in
    except (OSError, ValueError) as e:  # ValueError: UnicodeError or json.JSONDecodeError
        raise KrsError("E_PROJECT_UNREADABLE", path=str(path), reason=reason(e)) from None
    found = data.get("schema") if isinstance(data, dict) else None
    if found not in (SCHEMA, SCHEMA_ANTENNA):
        raise KrsError("E_PROJECT_SCHEMA", path=str(path), found=found, expected=SCHEMA_ANTENNA)
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


# What check_project requires, in the file's order. A (test, expected) pair is a field and `expected`, a T_EXPECT_ code,
# says what it must be; a dict is an object with those fields; a (dict, expected) pair is a list of such objects.
_TEXT = (lambda v: isinstance(v, str), "T_EXPECT_TEXT")
_ABOVE_0 = (lambda v: _number(v) and v > 0, "T_EXPECT_ABOVE_0")
_OPTIONAL_ABOVE_0 = (lambda v: v is _MISSING or _number(v) and v > 0, "T_EXPECT_ABOVE_0")  # missing reads the default
_FLAG = (lambda v: isinstance(v, bool), "T_EXPECT_FLAG")
_TWO_NAMES = (lambda v: _names(v) and len(v) == 2, "T_EXPECT_TWO_NAMES")
_CLASS = (lambda v: v is None or _names(v), "T_EXPECT_CLASS")
_PARTS = ({"ref": _TEXT, "pads": _TWO_NAMES, "nets": _TWO_NAMES, "value": _TEXT, "dnp": _FLAG,
           "role": (lambda v: v in ROLES, "T_EXPECT_ROLE"),
           "model": (_model, "T_EXPECT_MODEL"),
           "s2p": (lambda v: v is None or (isinstance(v, dict) and isinstance(v.get("file"), str)
                                           and v.get("connection") in ("series", "shunt")),
                   "T_EXPECT_S2P")},
          "T_EXPECT_PARTS")
_FIELDS = {
    "board": {"path": _TEXT, "sha256": _TEXT},
    "f0_hz": _ABOVE_0,
    "harmonics": (lambda v: type(v) is int and v > 0, "T_EXPECT_WHOLE_ABOVE_0"),  # not isinstance: 3.0 and True fail
    "preset": (lambda v: v in tuple(MESH_N), "T_EXPECT_PRESET"),  # in a dict, a list would raise TypeError
    "band_factor": _ABOVE_0,
    "t_max_s": _ABOVE_0,
    "region": {"expand_h": _ABOVE_0, "margin_scale": _OPTIONAL_ABOVE_0},
    "mesh": {"n": (lambda v: type(v) is int and v >= 2, "T_EXPECT_MESH_N"), "reach_h": _OPTIONAL_ABOVE_0},
    "stackup": {"source": _TEXT, "layers": ({
        "name": _TEXT, "kind": (lambda v: v in ("mask", "copper", "dielectric"), "T_EXPECT_KIND"),
        "thickness_mm": (lambda v: _number(v) and v >= 0, "T_EXPECT_0_OR_MORE"),
        "epsilon_r": (lambda v: v is None or _number(v) and v > 0, "T_EXPECT_ABOVE_0_OR_NULL"),
        "loss_tangent": (lambda v: v is None or _number(v) and v >= 0, "T_EXPECT_0_OR_MORE_OR_NULL")},
        "T_EXPECT_LAYERS")},
    "lid_height_mm": (lambda v: v is None or _number(v) and v > 0, "T_EXPECT_LID_HEIGHT"),
    "lid": (lambda v: v is None or isinstance(v, bool), "T_EXPECT_LID"),
    "classes": dict.fromkeys(("gnd_nets", "power_nets", "connectors", "shields"), _CLASS),
    "chain": {"start": _TEXT, "end": _TEXT, "nets": (_names, "T_EXPECT_NAMES"), "series": _PARTS, "shunt": _PARTS},
    "others": _PARTS,
    "ports": ({"name": _TEXT, "signal": _TEXT, "signal_uuid": _TEXT, "layer": _TEXT,
               "rule": (lambda v: v in (None, "connector", "ic", "copper"), "T_EXPECT_RULE"),
               "reference": (_reference, "T_EXPECT_REFERENCE")}, "T_EXPECT_PORTS"),
    "gates": {"fit2d_limit": _ABOVE_0, "dt_floor": (lambda v: _number(v) and 0 < v <= 1, "T_EXPECT_DT_FLOOR")},
    "allow_curve_port": _FLAG}
_FIELDS_ANTENNA = {  # schema 2 (Stage 3 design 5.1): no harmonics or band_factor, then the antenna's fields
    **{key: spec for key, spec in _FIELDS.items() if key not in ("harmonics", "band_factor")},
    "lid": _FLAG,  # find_lid reads harmonics for a null lid, and schema 2 has none (the one-lid ruling)
    "kind": (lambda v: v == "antenna", "T_EXPECT_ANTENNA"),
    "band": {"f_lo_hz": _ABOVE_0, "f_hi_hz": _ABOVE_0},
    "antenna": {"ref": _TEXT, "join": (_names, "T_EXPECT_NAMES")},
    "air_gap_mm": _ABOVE_0,
    "boundary": (lambda v: v in ("pml_8", "mur"), "T_EXPECT_BOUNDARY"),
    "far_field": {"f_hz": (lambda v: isinstance(v, list) and 0 < len(v) <= NF2FF_MAX and all(map(_number, v)),
                           "T_EXPECT_FAR_FIELD_HZ"),
                  "step_deg": (lambda v: type(v) is int and v > 0 and 180 % v == 0, "T_EXPECT_STEP")}}
_MISSING = object()  # a key that is not there, which only an optional field accepts (null is a value)


def _check(value, spec, field: str, path: Path) -> None:
    """Raises E_PROJECT_FIELD for the first field of `value` that `spec` (_FIELDS or a part of it) refuses."""
    if isinstance(spec, dict):  # an object with these fields
        if not isinstance(value, dict):
            raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected="T_EXPECT_OBJECT")
        for key, sub in spec.items():
            _check(value.get(key, _MISSING), sub, f"{field}.{key}" if field else key, path)
        return
    test, expected = spec
    if isinstance(test, dict) and isinstance(value, list):  # a list of objects with these fields
        for i, item in enumerate(value):
            _check(item, test, f"{field}[{i}]", path)
    elif isinstance(test, dict) or not test(value):  # every test but an optional one refuses _MISSING
        raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected=expected)


def check_project(data: dict, path: Path) -> dict:
    """`data`, the project read from `path`, when each field has the kind and range that `new` writes (_FIELDS, or
    _FIELDS_ANTENNA for an antenna); else E_PROJECT_FIELD names the first that is missing or has not, with dots and
    [index] as in ports[0].reference (C-3). So a hand edit never ends in E_INTERNAL further on, nor in a field read as
    something it is not. An antenna's band then holds f_lo < f_hi ≤ 2·f_lo (Stage 3 design 3: one band a run), its
    f0_hz lies in the band, and its far field's first frequency is f0_hz (the worker draws the cuts at the first) and
    each lies within pulse_band, in that order. `results` is optional, and an object."""
    _check(data, _FIELDS_ANTENNA if antenna(data) else _FIELDS, "", path)
    if antenna(data):
        f_lo, f_hi, f0, far = data["band"]["f_lo_hz"], data["band"]["f_hi_hz"], data["f0_hz"], data["far_field"]["f_hz"]
        f1, f2 = pulse_band(f_lo, f_hi)
        for field, expected, ok in (("band.f_hi_hz", "T_EXPECT_BAND", f_lo < f_hi <= 2 * f_lo),
                                    ("f0_hz", "T_EXPECT_F0_BAND", f_lo <= f0 <= f_hi),
                                    ("far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ",
                                     far[0] == f0 and all(f1 <= f <= f2 for f in far))):
            if not ok:
                raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected=expected)
    if not isinstance(data.get("results", {}), dict):
        raise KrsError("E_PROJECT_FIELD", path=str(path), field="results", expected="T_EXPECT_OBJECT")
    return data


def read_project(path: Path) -> dict:
    """The project at `path`, read (load_project) and checked (check_project)."""
    return check_project(load_project(path), path)


def relative_path(file: str | Path, folder: Path) -> tuple[str, bool]:
    """`file` as project.json stores a path, and whether it is absolute: relative to `folder` with forward slashes (a
    relative `file` read from the working directory), and False; on another drive, which relpath cannot cross, its
    absolute path, and True."""
    try:
        return Path(os.path.relpath(file, folder)).as_posix(), False
    except ValueError:
        return Path(file).absolute().as_posix(), True


def board_file(path: Path, data: dict) -> Path:
    """The board file of the project at `path`. Its stored path is relative to the project file, not to the working
    directory; `load_project` leaves it as stored, so that a saved project keeps a relative path."""
    return (path.parent / data["board"]["path"]).resolve()
