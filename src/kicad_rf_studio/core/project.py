# SPDX-License-Identifier: GPL-3.0-or-later
"""project.json, schema 1 for a matching chain, schema 2 for an antenna (Stage 3 design 5.1), schema 3 for an SI
project (Stage 4 design 5.1) and schema 4 for an emission project (Stage 5 design 5.6): the project and the job spec in
one file. Its board path is relative to the project file and has forward slashes, so a project folder and its board can
move together.

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
from kicad_rf_studio.core.model.csx import EMISSION_NF2FF_MAX, NF2FF_MAX
from kicad_rf_studio.core.post.si import LOCAL_RISE

if TYPE_CHECKING:  # the types only: project.py imports no board code
    from kicad_rf_studio.core.kicad.stackup import Stackup
    from kicad_rf_studio.core.kicad.tracer import Classes

SCHEMA = 1
SCHEMA_ANTENNA = 2  # an antenna project (Stage 3 design 5.1); v1's stay SCHEMA
SCHEMA_SI = 3  # an SI project (Stage 4 design 5.1)
SCHEMA_EMISSION = 4  # an emission project (Stage 5 design 5.6)
# part B's no-go (design 5.13): the record of the gate the kind failed, gate E-A's, which W_EMISSION_UNVALIDATED names
EMISSION_UNVALIDATED = "docs/validation/2026-11-17-e-a.md"
FAR_FIELD_STEP = 5  # the far field's full sphere is sampled every 5° (Stage 3 design 5.5)
NEAR_FIELD_MAX = 11  # the carrier's harmonics an emission project's near-field plane records, at most (AR-9)
# an antenna's copper model (Stage 3 design 5.3): Stage 1 5.3's solid copper, or every copper layer a sheet, for the
# whole model
COPPER_MODELS = ("solid", "sheet")
ANTENNA_COPPER = "solid"  # `new`'s, which gate P3-C kept over sheet (docs/validation/2026-11-01-p3-c.md)
# `new`'s absorber past an air gap of λ/4 at f_lo (air_gap), the setting gate P3-C tested and kept (the same record)
ANTENNA_BOUNDARY = "pml_8"
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
GATES_SI = {"fit2d_limit": 0.03, "dt_floor": 0.6}  # an SI project's: SI's timestep floor 0.6, Stage 4 design 5.3, A-43
SI_F_MAX = 10e9  # the presets' band, for the localising TDR, design 5.1
SI_TOLERANCE = 0.1  # the target impedance's ± fraction, every interface's (design 5.1)
DIELECTRICS = ("lossless", "debye")  # an SI project's dielectric models (design 5.3), never v1's constant κ
SI_DIELECTRIC = "lossless"  # lossless, the default gate P4-D kept, Debye an option (docs/validation/2026-11-07-p4-d.md)
LINE_ROLES = ("measured", "victim")  # an SI line's role (design 5.1): the measured line or a pair's leg, or a victim
# Stage 4 design 5.1: each target from a public application note; rise_s the edge the link's driver makes, marker_hz the
# link's Nyquist frequency or its clock; every preset runs to SI_F_MAX
INTERFACES = {
    "usb2-hs": {"target_ohm": 90.0, "rise_s": 500e-12, "marker_hz": 240e6, "pair": True},  # TI SPRAAR7J Table A-1
    "100base-tx": {"target_ohm": 100.0, "rise_s": 3e-9, "marker_hz": 62.5e6, "pair": True},  # TI SNLA387, ANSI X3.263
    "se50": {"target_ohm": 50.0, "rise_s": 1e-9, "marker_hz": 133e6, "pair": False}}  # QSPI, SDIO, SPI, a clock


def antenna(data: dict) -> bool:
    """Whether project.json `data` is an antenna's, schema SCHEMA_ANTENNA (Stage 3 design 5.1)."""
    return data.get("schema") == SCHEMA_ANTENNA


def si(data: dict) -> bool:
    """Whether project.json `data` is an SI project's, schema SCHEMA_SI (Stage 4 design 5.1)."""
    return data.get("schema") == SCHEMA_SI


def emission(data: dict) -> bool:
    """Whether project.json `data` is an emission project's, schema SCHEMA_EMISSION (Stage 5 design 5.6)."""
    return data.get("schema") == SCHEMA_EMISSION


def default_gates(data: dict) -> dict:
    """The gate limits project.json `data`'s verdicts are built for: GATES_SI for an SI project (Stage 4 design 5.3),
    else GATES."""
    return GATES_SI if si(data) else GATES


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


def copper_model(data: dict) -> str:
    """project.json's copper, else "solid": an antenna made before plan 4 has none."""
    return data.get("copper", "solid")


def parts(data: dict) -> dict[str, dict]:
    """project.json's parts by ref: chain.series, chain.shunt, then others; an SI project's (Stage 4 design 5.1) every
    line's chain series, then every line's chain shunt, then others. The dicts are the ones `data` holds, not copies,
    so an edit through them is an edit of `data`."""
    chains = [line["chain"] for line in data["lines"]] if si(data) else [data["chain"]]
    return {q["ref"]: q for q in (*(q for key in ("series", "shunt") for c in chains for q in c[key]), *data["others"])}


def shown_reference(ref: dict | None) -> str:
    """A port's stored reference as the port map shows it: the pad's name, the point on its layer (KiCad's frame, as
    stored), "plane LAYER" for an SI port's vertical reference (Stage 4 design 5.5), or "none"."""
    if ref is None:
        return "none"
    if "pad" in ref:
        return ref["pad"]
    if "plane" in ref:
        return f"plane {ref['plane']}"
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


def far_field_hz(f_lo: float, f_hi: float) -> list[float]:
    """An antenna's far-field frequencies as `new` writes them (Stage 3 design 5.5): f0, the band's centre, then 10
    evenly from f_lo to f_hi."""
    return [(f_lo + f_hi) / 2, *(f_lo + (f_hi - f_lo) * k / 9 for k in range(10))]


def make_antenna_project(board_path: str, board_sha256: str, f_lo_hz: float, f_hi_hz: float, stackup: Stackup,
                         classes: Classes, chain: dict, others: list[dict], ports: list[dict], ref: str,
                         join: list[str], *, t_max_s: float, air_gap_mm: float, preset: str = DEFAULT_PRESET,
                         lid_height_mm: float | None = None) -> dict:
    """project.json of an antenna (schema 2, Stage 3 design 5.1) as `new --antenna` writes it: make_project's dict but
    harmonics and band_factor, with schema SCHEMA_ANTENNA, f0_hz the band's centre, `t_max_s`, region {"expand_h":
    REACH_H} (the measured region reaches as far as the protected set) and lid true (every shield gets its lid, 5.3);
    then kind, band, antenna {"ref", "join"}, `air_gap_mm`, boundary ANTENNA_BOUNDARY, far_field {"f_hz":
    far_field_hz(f_lo, f_hi), "step_deg": FAR_FIELD_STEP} and copper ANTENNA_COPPER."""
    f0 = (f_lo_hz + f_hi_hz) / 2
    data = make_project(board_path, board_sha256, f0, stackup, classes, chain, others, ports, preset=preset,
                        lid_height_mm=lid_height_mm)
    del data["harmonics"], data["band_factor"]
    data.update(schema=SCHEMA_ANTENNA, t_max_s=t_max_s, region={"expand_h": REACH_H}, lid=True)  # in their places
    data.update(kind="antenna", band={"f_lo_hz": f_lo_hz, "f_hi_hz": f_hi_hz}, antenna={"ref": ref, "join": join},
                air_gap_mm=air_gap_mm, boundary=ANTENNA_BOUNDARY,
                far_field={"f_hz": far_field_hz(f_lo_hz, f_hi_hz), "step_deg": FAR_FIELD_STEP},
                copper=ANTENNA_COPPER)  # appended, in this order
    return data


def si_interface(name: str, f_max: float | None, target: float | None, paired: bool) -> dict:
    """An SI project's interface fields (Stage 4 design 5.1): a preset's at SI_F_MAX, or custom's from `f_max` (Hz) and
    `target` (Ω), its rise time LOCAL_RISE/f_max, the localising TDR's, and its marker 0.35/that, the rise time's
    bandwidth; tolerance SI_TOLERANCE. E_SI_CUSTOM unless custom has both `f_max` and `target` and a preset neither;
    E_SI_NEEDS_PAIR for a pair's preset without `paired`, E_SI_NOT_PAIR for a net's with it."""
    custom = name == "custom"
    if (f_max is not None, target is not None) != (custom, custom):
        raise KrsError("E_SI_CUSTOM")
    if custom:
        # ponytail: custom's rise time and marker are derived; project.json holds them for an edit
        rise = LOCAL_RISE / f_max
        fields = {"f_max_hz": f_max, "rise_s": rise, "marker_hz": 0.35 / rise, "target_ohm": target}
    else:
        preset = INTERFACES[name]
        if preset["pair"] != paired:
            raise KrsError("E_SI_NEEDS_PAIR" if preset["pair"] else "E_SI_NOT_PAIR", interface=name)
        fields = {"f_max_hz": SI_F_MAX, "rise_s": preset["rise_s"], "marker_hz": preset["marker_hz"],
                  "target_ohm": preset["target_ohm"]}
    return {"interface": name, **fields, "tolerance": SI_TOLERANCE}


def make_si_project(board_path: str, board_sha256: str, stackup: Stackup, classes: Classes, lines: list[dict],
                    pair: dict | None, others: list[dict], ports: list[dict], interface: dict, *, t_max_s: float,
                    window_s: float, max_cell_mm: float | None, preset: str = DEFAULT_PRESET,
                    lid_height_mm: float | None = None) -> dict:
    """project.json of an SI project (schema 3, Stage 4 design 5.1) as `new --interface` writes it: make_project's dict
    without f0_hz, harmonics, band_factor and chain, with schema SCHEMA_SI, `t_max_s`, region {"expand_h": REACH_H,
    "margin_scale": MARGIN_SCALE} (the protected set's reach, design 5.2), mesh {"n", "reach_h", "max_cell_mm"}, lid
    true and gates GATES_SI in their places; then kind, the `interface` fields, dielectric SI_DIELECTRIC, `window_s`,
    `lines` and `pair`."""
    data = make_project(board_path, board_sha256, 0.0, stackup, classes, {}, others, ports, preset=preset,
                        lid_height_mm=lid_height_mm)
    del data["f0_hz"], data["harmonics"], data["band_factor"], data["chain"]
    data.update(schema=SCHEMA_SI, t_max_s=t_max_s, region={"expand_h": REACH_H, "margin_scale": MARGIN_SCALE},
                mesh={**data["mesh"], "max_cell_mm": max_cell_mm}, lid=True, gates=dict(GATES_SI))  # in their places
    data.update(kind="si", **interface, dielectric=SI_DIELECTRIC, window_s=window_s, lines=lines,
                pair=pair)  # appended, in this order
    return data


def harmonics_hz(f0: float, f_max: float) -> list[float]:
    """The carrier `f0`'s harmonics n·f0 for n = 2, 3, … while n·f0 ≤ f_max, in Hz (Stage 5 design 5.8)."""
    # ponytail: one entry per harmonic up to f_max, so a carrier of a few Hz under a GHz band makes billions; a
    # generator from f_lo's n if such a carrier is ever meant
    # n runs one past f_max/f0, which rounding can leave a hair short of an n whose n·f0 ≤ f_max
    return [n * f0 for n in range(2, math.floor(f_max / f0) + 2) if n * f0 <= f_max]


def emission_far_field_hz(f0: float | None, f_lo: float, f_max: float) -> list[float]:
    """An emission project's far-field frequencies as `new` writes them (Stage 5 design 5.8; BC3, AR-8), ascending: the
    carrier's harmonics in [f_lo, f_max] (none without `f0`), then the 100 MHz grid from 1 to 6 GHz in [f_lo, f_max],
    a grid point within 1 MHz of a harmonic left out; at most EMISSION_NF2FF_MAX, the lowest harmonics kept first,
    then the lowest grid points."""
    harmonics = [f for f in harmonics_hz(f0, f_max) if f >= f_lo][:EMISSION_NF2FF_MAX] if f0 else []
    grid = [f for f in (1e9 + 1e8 * k for k in range(51))
            if f_lo <= f <= f_max and all(abs(f - h) > 1e6 for h in harmonics)]
    return sorted([*harmonics, *grid][:EMISSION_NF2FF_MAX])


def emission_band(data: dict) -> tuple[float, float]:
    """The band an emission project's model is built for, in Hz (Stage 5 design 5.7): the pulse's f1 of its band
    (pulse_band of band.f_lo_hz and band.f_max_hz), and band.f_max_hz."""
    f_lo, f_max = data["band"]["f_lo_hz"], data["band"]["f_max_hz"]
    return pulse_band(f_lo, f_max)[0], f_max


def make_emission_project(board_path: str, board_sha256: str, f0_hz: float | None, f_lo_hz: float, f_max_hz: float,
                          stackup: Stackup, classes: Classes, chain: dict, others: list[dict], ports: list[dict], *,
                          t_max_s: float, air_gap_mm: float, preset: str = DEFAULT_PRESET,
                          lid_height_mm: float | None = None) -> dict:
    """project.json of an emission project (schema 4, Stage 5 design 5.6) as `new --emission` writes it: make_project's
    dict but harmonics and band_factor, with schema SCHEMA_EMISSION, f0_hz the carrier (None without one), `t_max_s`,
    region {"expand_h": REACH_H} and lid true, as an antenna's; then kind, band {"f_lo_hz", "f_max_hz"},
    `air_gap_mm`, boundary ANTENNA_BOUNDARY, far_field {"f_hz": emission_far_field_hz(f0, f_lo, f_max), "step_deg":
    FAR_FIELD_STEP} and near_field false. No overrides: `new` writes them only for a review's finding (5.9)."""
    data = make_project(board_path, board_sha256, f0_hz, stackup, classes, chain, others, ports, preset=preset,
                        lid_height_mm=lid_height_mm)
    del data["harmonics"], data["band_factor"]
    data.update(schema=SCHEMA_EMISSION, t_max_s=t_max_s, region={"expand_h": REACH_H}, lid=True)  # in their places
    data.update(kind="emission", band={"f_lo_hz": f_lo_hz, "f_max_hz": f_max_hz}, air_gap_mm=air_gap_mm,
                boundary=ANTENNA_BOUNDARY,
                far_field={"f_hz": emission_far_field_hz(f0_hz, f_lo_hz, f_max_hz), "step_deg": FAR_FIELD_STEP},
                near_field=False)  # appended, in this order
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
    not UTF-8 JSON (a hand edit can break it); E_PROJECT_SCHEMA for a file of none of SCHEMA, SCHEMA_ANTENNA, SCHEMA_SI
    and SCHEMA_EMISSION, its `expected` SCHEMA_EMISSION, the newest it reads."""
    try:
        if not path.is_file():  # Windows reads a folder as PermissionError, so look before reading (as load_board)
            raise IsADirectoryError() if path.exists() else FileNotFoundError()
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig: an editor may have put a byte order mark in
    except (OSError, ValueError) as e:  # ValueError: UnicodeError or json.JSONDecodeError
        raise KrsError("E_PROJECT_UNREADABLE", path=str(path), reason=reason(e)) from None
    found = data.get("schema") if isinstance(data, dict) else None
    if found not in (SCHEMA, SCHEMA_ANTENNA, SCHEMA_SI, SCHEMA_EMISSION):
        raise KrsError("E_PROJECT_SCHEMA", path=str(path), found=found, expected=SCHEMA_EMISSION)
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
    return _point(v.get("point")) and isinstance(v.get("layer"), str)


def _point(v) -> bool:
    """[x, y], two numbers."""
    return isinstance(v, list) and len(v) == 2 and all(map(_number, v))


def _override(entry) -> bool:
    """An override as `new` writes it (Stage 5 design 5.9): "kind" "fill" or "via", with "from" and "net" text. A fill
    has "layer" text and "polygon_mm" {"exterior": a ring, "holes": a list of rings}, a ring 3 or more [x, y]; a via
    has "at_mm" [x, y], "diameter_mm" and "drill_mm" above 0, "layers" two names and an optional "pitch_mm" above 0."""
    def ring(v) -> bool:
        return isinstance(v, list) and len(v) >= 3 and all(map(_point, v))

    def above_0(key: str) -> bool:
        return _number(entry.get(key)) and entry[key] > 0

    if not (isinstance(entry, dict) and isinstance(entry.get("from"), str) and isinstance(entry.get("net"), str)):
        return False
    if entry.get("kind") == "fill":
        polygon = entry.get("polygon_mm")
        return (isinstance(entry.get("layer"), str) and isinstance(polygon, dict) and ring(polygon.get("exterior"))
                and isinstance(polygon.get("holes"), list) and all(map(ring, polygon["holes"])))
    layers = entry.get("layers")
    return (entry.get("kind") == "via" and _point(entry.get("at_mm")) and above_0("diameter_mm") and above_0("drill_mm")
            and _names(layers) and len(layers) == 2 and ("pitch_mm" not in entry or above_0("pitch_mm")))


# What check_project requires, in the file's order. A (test, expected) pair is a field and `expected`, a T_EXPECT_ code,
# says what it must be; a dict is an object with those fields; a (dict, expected) pair is a list of such objects.
_TEXT = (lambda v: isinstance(v, str), "T_EXPECT_TEXT")
_ABOVE_0 = (lambda v: _number(v) and v > 0, "T_EXPECT_ABOVE_0")
_ABOVE_0_OR_NULL = (lambda v: v is None or _number(v) and v > 0, "T_EXPECT_ABOVE_0_OR_NULL")
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
        "epsilon_r": _ABOVE_0_OR_NULL,
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
                  "step_deg": (lambda v: type(v) is int and v > 0 and 180 % v == 0, "T_EXPECT_STEP")},
    "copper": (lambda v: v is _MISSING or v in COPPER_MODELS, "T_EXPECT_COPPER"),  # missing reads solid
    "flat_s": _OPTIONAL_ABOVE_0}
_FIELDS_SI = {  # schema 3 (Stage 4 design 5.1): no f0_hz, harmonics, band_factor or chain, then the SI project's fields
    **{key: spec for key, spec in _FIELDS.items() if key not in ("f0_hz", "harmonics", "band_factor", "chain")},
    "mesh": {**_FIELDS["mesh"], "max_cell_mm": _ABOVE_0_OR_NULL},
    "lid": _FLAG,  # as an antenna's: find_lid reads harmonics for a null lid, and schema 3 has none
    "ports": ({**_FIELDS["ports"][0],
               "rule": (lambda v: v in (None, "connector", "ic", "copper", "plane"), "T_EXPECT_SI_RULE"),
               "reference": (lambda v: _reference(v) or (isinstance(v, dict) and v.keys() == {"plane"}
                                                         and isinstance(v["plane"], str)), "T_EXPECT_SI_REFERENCE")},
              "T_EXPECT_PORTS"),
    "kind": (lambda v: v == "si", "T_EXPECT_SI"),
    "interface": (lambda v: v in (*INTERFACES, "custom"), "T_EXPECT_INTERFACE"),
    **dict.fromkeys(("f_max_hz", "rise_s", "marker_hz", "target_ohm", "tolerance"), _ABOVE_0),
    "dielectric": (lambda v: v in DIELECTRICS, "T_EXPECT_DIELECTRIC"),
    "window_s": _ABOVE_0,
    "lines": ({"role": (lambda v: v in LINE_ROLES, "T_EXPECT_LINE_ROLE"), "chain": _FIELDS["chain"]},
              "T_EXPECT_SI_LINES"),
    "pair": (lambda v: v is None or (isinstance(v, dict) and isinstance(v.get("p"), str) and isinstance(v.get("n"), str)
                                     and v.get("by") in ("rule", "alias", "given")), "T_EXPECT_SI_PAIR")}
_FIELDS_EMISSION = {  # schema 4 (Stage 5 design 5.6): no harmonics or band_factor, then the emission project's fields
    **{key: spec for key, spec in _FIELDS.items() if key not in ("harmonics", "band_factor")},
    "f0_hz": _ABOVE_0_OR_NULL,  # null: a band with no carrier
    "lid": _FLAG,  # as an antenna's: find_lid reads harmonics for a null lid, and schema 4 has none
    "ports": ({**_FIELDS["ports"][0], "R": _OPTIONAL_ABOVE_0}, "T_EXPECT_PORTS"),  # a termination's own R (AR-7)
    "kind": (lambda v: v == "emission", "T_EXPECT_EMISSION"),
    "band": {"f_lo_hz": _ABOVE_0, "f_max_hz": _ABOVE_0},
    "air_gap_mm": _ABOVE_0,
    "boundary": _FIELDS_ANTENNA["boundary"],
    "far_field": {"f_hz": (lambda v: isinstance(v, list) and 0 < len(v) <= EMISSION_NF2FF_MAX and all(map(_number, v)),
                           "T_EXPECT_EMISSION_FAR_FIELD_HZ"),
                  "step_deg": _FIELDS_ANTENNA["far_field"]["step_deg"]},
    "near_field": _FLAG,
    "overrides": (lambda v: v is _MISSING or isinstance(v, list) and all(map(_override, v)), "T_EXPECT_OVERRIDES")}
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
    """`data`, the project read from `path`, when each field has the kind and range that `new` writes (_FIELDS,
    _FIELDS_EMISSION for an emission project, _FIELDS_ANTENNA for an antenna, _FIELDS_SI for an SI project); else
    E_PROJECT_FIELD names the first that is missing or has not, with dots and [index] as in ports[0].reference (C-3).
    So a hand edit never ends in E_INTERNAL further on, nor in a field read as something it is not. An emission
    project's band then holds f_lo < f_max, each far-field frequency lies in the band, a near-field plane has a carrier
    (f0_hz) whose harmonics it records, and the first port, the driven one, a 50 Ω source, has no "R", in that order
    (Stage 5 design 5.6); `overrides` is optional in it and refused in any other project (Review Focus 5). An
    antenna's band then holds f_lo < f_hi ≤ 2·f_lo (Stage 3 design 3: one band a run), its f0_hz lies in the band, and
    its far field's first frequency is f0_hz (the worker draws the cuts at the first) and each lies within pulse_band,
    in that order. An SI project's rise_s is then at least LOCAL_RISE/f_max_hz, the localising TDR's (Stage 4 design
    5.1), its lines' roles are 1 or 2 measured, then 0 to 2 victims, its lines' nets each on one line (as `new` refuses
    with E_SI_LINE_SHARED), its pair is null with one measured line, else p and n are the two measured lines' first
    nets, and its ports' signals are each measured line's start, each one's end, then each victim's start and end (the
    order se2gmm reads a pair's ports in), checked in that order. An antenna's `copper` and `flat_s` are optional (a
    project made before plan 4 has neither): solid copper (copper_model) and flat_window's (excitation). `results` is
    optional, and an object."""
    _check(data, _FIELDS_EMISSION if emission(data) else _FIELDS_ANTENNA if antenna(data) else _FIELDS_SI if si(data)
           else _FIELDS, "", path)
    if emission(data):
        f_lo, f_max = data["band"]["f_lo_hz"], data["band"]["f_max_hz"]
        for field, expected, ok in (
                ("band.f_max_hz", "T_EXPECT_EMISSION_BAND", f_lo < f_max),
                ("far_field.f_hz", "T_EXPECT_EMISSION_FAR_FIELD_HZ",
                 all(f_lo <= f <= f_max for f in data["far_field"]["f_hz"])),
                ("near_field", "T_EXPECT_NEAR_FIELD", not data["near_field"] or data["f0_hz"] is not None),
                ("ports[0].R", "T_EXPECT_DRIVEN_R", all("R" not in port for port in data["ports"][:1]))):
            if not ok:
                raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected=expected)
    if antenna(data):
        f_lo, f_hi, f0, far = data["band"]["f_lo_hz"], data["band"]["f_hi_hz"], data["f0_hz"], data["far_field"]["f_hz"]
        f1, f2 = pulse_band(f_lo, f_hi)
        for field, expected, ok in (("band.f_hi_hz", "T_EXPECT_BAND", f_lo < f_hi <= 2 * f_lo),
                                    ("f0_hz", "T_EXPECT_F0_BAND", f_lo <= f0 <= f_hi),
                                    ("far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ",
                                     far[0] == f0 and all(f1 <= f <= f2 for f in far))):
            if not ok:
                raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected=expected)
    if si(data):
        lines, pair = data["lines"], data["pair"]
        roles = [line["role"] for line in lines]
        m, v = roles.count("measured"), roles.count("victim")
        measured, victims = [line["chain"] for line in lines[:m]], [line["chain"] for line in lines[m:]]
        ends = [*(c["start"] for c in measured), *(c["end"] for c in measured),
                *(end for c in victims for end in (c["start"], c["end"]))]
        nets = [n for line in lines for n in line["chain"]["nets"]]
        for field, expected, ok in (
                ("rise_s", "T_EXPECT_RISE", data["rise_s"] >= LOCAL_RISE / data["f_max_hz"] * (1 - 1e-9)),
                ("lines", "T_EXPECT_SI_LINES", m in (1, 2) and v <= 2 and roles == ["measured"] * m + ["victim"] * v),
                ("lines", "T_EXPECT_SI_OWN_NETS", len(nets) == len(set(nets))),
                ("pair", "T_EXPECT_SI_PAIR", pair is None if m == 1 else
                 pair is not None and [pair["p"], pair["n"]] == [n for c in measured for n in c["nets"][:1]]),
                ("ports", "T_EXPECT_SI_PORTS", [port["signal"] for port in data["ports"]] == ends)):
            if not ok:
                raise KrsError("E_PROJECT_FIELD", path=str(path), field=field, expected=expected)
    if "overrides" in data and not emission(data):
        raise KrsError("E_PROJECT_FIELD", path=str(path), field="overrides", expected="T_EXPECT_NO_OVERRIDES")
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
