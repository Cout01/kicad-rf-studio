# SPDX-License-Identifier: GPL-3.0-or-later
"""A KiCad board as plain data: copper, vias, zone fills, graphics and the outline, in mm with y up."""
from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from shapely import unary_union
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize

from kicad_rf_studio.core.kicad.sexpr import Quoted, atom, child, children, num, parse, repair
from kicad_rf_studio.core.kicad.shapes import XY, arc_points, circle
from kicad_rf_studio.core.messages import KrsError

OLDEST_SUPPORTED = 20241229  # the file version of KiCad 9.0
NEWEST_TESTED = 20241229  # moves up when CI tier (c) has read a KiCad 10 board
DEFAULT_THICKNESS = 1.6  # mm, what KiCad assumes for a board whose file gives none
OUTLINE_GRID = 1e-3  # mm, the grid Edge.Cuts lines are noded on: ends closer than this meet
_MASK = {"F.Mask": "F", "B.Mask": "B"}
_GRAPHICS = ("gr_poly", "gr_rect", "gr_circle", "gr_line", "gr_arc")


@dataclass(frozen=True)
class Track:
    """A copper segment, or an arc when `mid` is set."""
    layer: str
    net: str
    width: float
    start: XY
    end: XY
    mid: XY | None
    uuid: str

    def polygon(self) -> Polygon:
        """The track's copper, with round caps."""
        line = [self.start, self.end] if self.mid is None else arc_points(self.start, self.mid, self.end)
        return LineString(line).buffer(self.width / 2)


@dataclass(frozen=True)
class Via:
    """A via: `layers` are the two copper layers it joins."""
    at: XY
    diameter: float
    drill: float
    layers: tuple[str, str]
    net: str
    uuid: str


@dataclass(frozen=True)
class CopperArea:
    """A zone fill or a copper graphic."""
    layer: str
    net: str
    polygon: Polygon
    source: str  # "zone" or "graphic"
    uuid: str


@dataclass
class Board:
    """Everything the board holds that a simulation needs, as shapely polygons in mm with y up."""
    path: Path
    version: int
    thickness: float
    copper_layers: tuple[str, ...]  # top to bottom: F.Cu, In1.Cu, ..., B.Cu
    nets: tuple[str, ...]
    footprints: dict[str, Footprint]  # by reference; filled in Task 7
    tracks: list[Track]
    vias: list[Via]
    areas: list[CopperArea]
    outline: Polygon | None
    pad_to_mask_clearance: float
    solder_mask_min_width: float
    mask_graphics: dict[str, list[Polygon]]  # "F" / "B": shapes drawn on F.Mask / B.Mask
    stackup: Stackup | None  # filled in Task 9
    warnings: list[tuple[str, dict]]  # (message code, params)

    def pads(self, name: str) -> list[Pad]:
        """The pads called `name`, "REF.NUM": more than one when a footprint repeats a number."""
        return [p for fp in self.footprints.values() for p in fp.pads if p.name == name]


def _pt(x, y) -> XY:
    """A KiCad point as ours: the y axis points down in KiCad. `0.0 - y` keeps a zero from becoming -0.0."""
    return float(x), 0.0 - float(y)


def _xy(node: list, head: str) -> XY:
    c = child(node, head)
    return _pt(c[1], c[2])


def _text(node: list, head: str) -> str:
    return str(atom(node, head, default=""))


def _net(node: list, table: dict[str, str]) -> str:
    """The net name of an item. KiCad 10 writes the name, `(net "SIG")`; KiCad 9 writes a code, `(net 1)`,
    which `table` (the header's `(net 1 "SIG")` entries) resolves. No net, or an unknown code, is ""."""
    n = child(node, "net") or []
    for a in n[1:]:
        if isinstance(a, Quoted):
            return str(a)
    return table.get(n[1], "") if len(n) > 1 else ""


def _net_names(node: list) -> Iterator[str]:
    """Every net name written anywhere in the file, in order: `(net 1 "SIG")` in KiCad 9's header table and
    on its pads, `(net "SIG")` on every KiCad 10 item. Which one a board uses decides where its nets are."""
    for c in node:
        if isinstance(c, list) and c:
            if c[0] == "net":
                yield from (a for a in c[1:] if isinstance(a, Quoted))
            else:
                yield from _net_names(c)


def _copper_layers(root: list) -> tuple[str, ...]:
    """The copper layers top to bottom. The file lists them by number, where B.Cu (2) comes before the
    inner layers (4, 6, ...), so F.Cu goes first, B.Cu last and the rest by number."""
    entries = [(int(e[0]), str(e[1])) for e in (child(root, "layers") or [])[1:] if str(e[1]).endswith(".Cu")]
    entries.sort(key=lambda e: (e[1] == "B.Cu", e[1] != "F.Cu", e[0]))
    return tuple(name for _, name in entries)


def _track(node: list, table: dict[str, str]) -> Track:
    mid = _xy(node, "mid") if child(node, "mid") else None
    return Track(_text(node, "layer"), _net(node, table), num(node, "width", 1, 0.0),
                 _xy(node, "start"), _xy(node, "end"), mid, _text(node, "uuid"))


def _via(node: list, table: dict[str, str]) -> Via:
    layers = tuple(str(a) for a in (child(node, "layers") or [])[1:]) or ("F.Cu", "B.Cu")
    return Via(_xy(node, "at"), num(node, "size", 1, 0.0), num(node, "drill", 1, 0.0), layers,
               _net(node, table), _text(node, "uuid"))


def _points(pts: list) -> list[XY]:
    """The vertices of a `(pts ...)` list. KiCad writes an arc of a polygon as `(arc (start) (mid) (end))`,
    which stands in for all the vertices on it."""
    out: list[XY] = []
    for p in pts[1:]:
        if p[0] == "xy":
            out.append(_pt(p[1], p[2]))
        elif p[0] == "arc":
            out += arc_points(_xy(p, "start"), _xy(p, "mid"), _xy(p, "end"))
    return out


def _polygons(geom: BaseGeometry) -> list[Polygon]:
    """The non-empty polygons of `geom`. An invalid one is rebuilt with buffer(0): KiCad writes a fill with
    a hole as one outline that runs into the hole and back along a zero-width slit, which buffer(0) turns
    into an outline with a hole. (A polygon that truly crosses itself, a bow-tie, keeps one lobe.)"""
    if not geom.is_valid:
        geom = geom.buffer(0)
    return [g for g in getattr(geom, "geoms", [geom]) if not g.is_empty]


def _zone(b: Board, node: list, table: dict[str, str]) -> None:
    """A zone's fills are copper areas, or mask openings on a mask layer. A rule area (keepout) is no copper,
    and a copper zone with no fill at all is only a warning."""
    if child(node, "keepout") is not None:
        return
    net, uuid = _net(node, table), _text(node, "uuid")
    fills = children(node, "filled_polygon")
    for fill in fills:
        layer = _text(fill, "layer")
        polygons = _polygons(Polygon(_points(child(fill, "pts"))))
        if layer in b.copper_layers:
            b.areas += [CopperArea(layer, net, p, "zone", uuid) for p in polygons]
        elif layer in _MASK:
            b.mask_graphics[_MASK[layer]] += polygons
    if not fills:
        for layer in (child(node, "layers") or child(node, "layer") or [])[1:]:  # one layer, or several
            if layer in b.copper_layers:
                b.warnings.append(("W_ZONE_NOT_FILLED", {"uuid": uuid, "layer": str(layer)}))


def _shape(node: list) -> LineString | Polygon:
    """The centre line of a line or arc, or the outline of a rectangle, circle or polygon."""
    head = node[0]
    if head == "gr_line":
        return LineString([_xy(node, "start"), _xy(node, "end")])
    if head == "gr_arc":
        return LineString(arc_points(_xy(node, "start"), _xy(node, "mid"), _xy(node, "end")))
    if head == "gr_rect":
        (x0, y0), (x1, y1) = _xy(node, "start"), _xy(node, "end")
        return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    if head == "gr_circle":
        c = _xy(node, "center")
        return circle(c, math.dist(c, _xy(node, "end")))
    return Polygon(_points(child(node, "pts")))  # gr_poly


def _line(shape: LineString | Polygon) -> LineString:
    return shape.exterior if isinstance(shape, Polygon) else shape


def _covered(node: list, shape: LineString | Polygon) -> list[Polygon]:
    """What a graphic covers: its stroke, `width` wide with round ends, and its inside when it is filled.
    KiCad draws the stroke of a filled shape as well, so a filled shape grows by half its width."""
    width = num(child(node, "stroke") or [], "width", 1, 0.0)
    if isinstance(shape, Polygon) and atom(node, "fill") == "yes":
        return _polygons(shape.buffer(width / 2) if width else shape)
    return _polygons(_line(shape).buffer(width / 2))


def _graphic(b: Board, node: list, table: dict[str, str], edge: list[LineString]) -> None:
    """A board graphic is outline linework on Edge.Cuts, a copper area on a copper layer (with a warning
    when it has no net) or a mask opening on a mask layer. On any other layer it is left alone."""
    layer = _text(node, "layer")
    if layer != "Edge.Cuts" and layer not in b.copper_layers and layer not in _MASK:
        return  # not even read: drawings on the silkscreen and the like can be anything
    shape = _shape(node)
    if layer == "Edge.Cuts":
        edge.append(_line(shape))
    elif layer in b.copper_layers:
        net, uuid = _net(node, table), _text(node, "uuid")
        if not net:
            b.warnings.append(("W_NETLESS_COPPER", {"uuid": uuid, "layer": layer}))
        b.areas += [CopperArea(layer, net, p, "graphic", uuid) for p in _covered(node, shape)]
    else:
        b.mask_graphics[_MASK[layer]] += _covered(node, shape)


def _outline(lines: list[LineString]) -> Polygon | None:
    """The board's shape from the Edge.Cuts linework: the loop that encloses the most, with the loops inside
    it cut out. polygonize returns every loop as a face and leaves a cutout out of the face around it, so
    the board is the face with the largest outer ring. The face of the largest area is not: a big cutout
    leaves a thin frame. The lines are noded first, on a grid of OUTLINE_GRID, so a doubled or overshooting
    line still closes and two ends that miss each other by a hair meet. The outline's vertices then lie on
    that grid: each coordinate moves by at most half of it."""
    # ponytail: ends that miss by less than about 1 um meet on the grid (a 1 nm miss still straddles a grid line
    # about once in a thousand). A wider gap leaves no outline, though KiCad chains ends up to 0.01 mm apart,
    # and only the largest loop is kept, so a panel of boards keeps one board. Upgrade: join the ends within
    # 0.01 mm before noding, and keep every outer loop.
    noded = unary_union(lines, grid_size=OUTLINE_GRID)
    return max(polygonize(noded), key=lambda p: Polygon(p.exterior).area, default=None)


def load_board(path: str | Path) -> Board:
    """Read a .kicad_pcb file. Raises KrsError: E_PARSE_UNBALANCED for a damaged file, E_NOT_A_BOARD for
    another kind of KiCad file and E_BOARD_VERSION for a board older than KiCad 9."""
    path = Path(path)
    text, repaired = repair(path.read_text(encoding="utf-8"))
    root = parse(text)
    if not root or root[0] != "kicad_pcb":
        raise KrsError("E_NOT_A_BOARD", path=str(path))
    version = int(num(root, "version", 1, 0))
    if version < OLDEST_SUPPORTED:
        raise KrsError("E_BOARD_VERSION", version=version)
    warnings: list[tuple[str, dict]] = []
    if repaired:
        warnings.append(("W_REPAIRED_FILTER_RATIO", {"count": repaired}))
    if version > NEWEST_TESTED:
        warnings.append(("W_BOARD_NEWER", {"version": version}))
    table = {n[1]: str(n[2]) for n in children(root, "net") if len(n) > 2}
    setup = child(root, "setup") or []
    b = Board(
        path=path, version=version, thickness=num(child(root, "general") or [], "thickness", 1, DEFAULT_THICKNESS),
        copper_layers=_copper_layers(root), nets=tuple(dict.fromkeys(str(n) for n in _net_names(root) if n)),
        footprints={}, tracks=[], vias=[], areas=[], outline=None,
        pad_to_mask_clearance=num(setup, "pad_to_mask_clearance", 1, 0.0),
        solder_mask_min_width=num(setup, "solder_mask_min_width", 1, 0.0),
        mask_graphics={"F": [], "B": []}, stackup=None, warnings=warnings)
    edge: list[LineString] = []
    for node in root:
        if not isinstance(node, list) or not node:
            continue
        if node[0] in ("segment", "arc"):
            b.tracks.append(_track(node, table))
        elif node[0] == "via":
            b.vias.append(_via(node, table))
        elif node[0] == "zone":
            _zone(b, node, table)
        elif node[0] in _GRAPHICS:
            _graphic(b, node, table, edge)
    b.outline = _outline(edge)
    if b.outline is None:
        b.warnings.append(("W_NO_OUTLINE", {}))
    return b
