# SPDX-License-Identifier: GPL-3.0-or-later
"""Net classes, the RF chain between two pads and the reference of a port (spec 4.6 and 5.6), and an SI line with its
differential pair's partner (Stage 4 design 5.1). Only pads that carry copper count here: a paste-only pad, or a hole
with no copper, is left out of every rule."""
from __future__ import annotations

import difflib
import math
import re
from collections import deque
from collections.abc import Collection
from dataclasses import dataclass, replace

import shapely
from shapely.geometry import Point
from shapely.ops import nearest_points

from kicad_rf_studio.core.kicad.board import Board, Footprint, Pad
from kicad_rf_studio.core.kicad.shapes import XY
from kicad_rf_studio.core.messages import KrsError

GND = re.compile(r"(?i)[ADPSC]?GND\w*|\w*_GND|VSS\w*|0V|EARTH")
POWER = re.compile(r"(?i)\+\w+|\d+V\d*|V(CC|DD|BAT|IN|SYS|BUS|USB|IO|CORE)\w*")
CONNECTOR_PREFIXES = {"J", "P", "X", "CN"}  # the letters before a reference's digits
TIE_DECIMALS = 6  # centres whose distances agree to a nanometre are equally near; the rest is float noise
_ALIAS = re.compile(r"(.*D)([PM])([0-9_]*)")  # D+ and D- as DP and DM, which KiCad's rule pairs with DN


def _base(net: str) -> str:
    """The net's own name: the text after the last "/" of its sheet path."""
    return net.rsplit("/", 1)[-1]


def is_gnd(net: str) -> bool:
    """A ground by its name."""
    return GND.fullmatch(_base(net)) is not None


def is_power(net: str) -> bool:
    """A supply by its name. `0V` fits both patterns and is ground."""
    return POWER.fullmatch(_base(net)) is not None and not is_gnd(net)


@dataclass(frozen=True)
class Classes:
    """What a board's nets and footprints are: net names for `gnd` and `power`, references for the rest."""
    gnd: frozenset[str]
    power: frozenset[str]
    connectors: frozenset[str]
    shields: frozenset[str]


def _copper(fp: Footprint) -> list[Pad]:
    return [p for p in fp.pads if p.layers]


def _netted(fp: Footprint) -> list[Pad]:
    return [p for p in _copper(fp) if p.net]


def _prefix(ref: str) -> str:
    """The letters a reference starts with: J for J1, CN for CN3, REF for REF**#2."""
    return re.match(r"[A-Za-z]*", ref).group()


def _is_shield(board: Board, fp: Footprint, gnd: frozenset[str]) -> bool:
    """A frame of ground pads with a pad of another footprint inside the box around them."""
    pads = _copper(fp)
    if len(pads) < 2 or any(p.net not in gnd for p in pads):
        return False
    x0, y0, x1, y1 = shapely.total_bounds([p.polygon for p in pads])
    return any(x0 <= q.center[0] <= x1 and y0 <= q.center[1] <= y1
               for other in board.footprints.values() if other is not fp for q in _copper(other))


def classify(board: Board, overrides: dict | None = None) -> Classes:
    """The GND and power nets, the connectors and the shields of a board. A key of `overrides` (gnd_nets,
    power_nets, connectors, shields) that is not None replaces the set computed for it."""
    given = overrides or {}

    def pick(key: str, computed) -> frozenset[str]:
        return frozenset(computed if given.get(key) is None else given[key])

    gnd = pick("gnd_nets", (n for n in board.nets if is_gnd(n)))
    return Classes(
        gnd, pick("power_nets", (n for n in board.nets if is_power(n))),
        pick("connectors", (r for r in board.footprints if _prefix(r) in CONNECTOR_PREFIXES)),
        pick("shields", (r for r, fp in board.footprints.items() if _is_shield(board, fp, gnd))))


@dataclass(frozen=True)
class ChainPart:
    """A two-pad part of a chain: its pad names and the nets they sit on."""
    ref: str
    pads: tuple[str, str]  # series: (start side, end side); shunt: (chain side, other side)
    nets: tuple[str, str]


@dataclass(frozen=True)
class Chain:
    """The RF chain between the pads `start` and `end`: its nets in order, its series parts from start to end and
    the shunt parts (by ref) that touch those nets."""
    start: str
    end: str
    nets: tuple[str, ...]
    series: tuple[ChainPart, ...]
    shunt: tuple[ChainPart, ...]


def unknown_pad(board: Board, name: str) -> KrsError:
    """E_UNKNOWN_PAD for `name`, which no pad with copper is called, with up to five pad names close to it (T_NONE
    when none is close)."""
    known = {p.name for fp in board.footprints.values() for p in _copper(fp)}
    return KrsError("E_UNKNOWN_PAD", name=name,
                    candidates=", ".join(difflib.get_close_matches(name, known, n=5)) or "T_NONE")


def _resolve(board: Board, classes: Classes, name: str) -> list[Pad]:
    """The pads with copper called `name` ("REF.NUM"). They sit on one net, which a chain may touch."""
    pads = [p for p in board.pads(name) if p.layers]
    if not pads:
        raise unknown_pad(board, name)
    nets = {p.net for p in pads}
    if len(nets) > 1:
        raise KrsError("E_AMBIGUOUS_PAD", name=name, nets=", ".join(sorted(nets)))
    net = pads[0].net
    if not net or net in classes.gnd or net in classes.power:
        raise KrsError("E_START_ON_GND", name=name, net=net)
    return pads


def _parts(board: Board, classes: Classes, antenna: str | None = None) -> dict[str, list[Pad]]:
    """By ref, in ref order: the footprints with exactly two pads with a net, on two nets; a connector, a shield or the
    footprint `antenna` is none."""
    not_parts = classes.connectors | classes.shields | {antenna}
    parts = {}
    for ref in sorted(board.footprints):
        pads = _netted(board.footprints[ref])
        if len(pads) == 2 and pads[0].net != pads[1].net and ref not in not_parts:
            parts[ref] = pads
    return parts


def _links(board: Board, classes: Classes, antenna: str | None = None) -> dict[str, list[tuple[str, Pad, Pad]]]:
    """The walk's steps, net -> (ref, its pad on the net, its pad on the other net), in ref order: every part of
    `_parts` that is not DNP and has no pad on a GND or power net."""
    blocked = classes.gnd | classes.power
    links: dict[str, list[tuple[str, Pad, Pad]]] = {}
    for ref, (a, b) in _parts(board, classes, antenna).items():
        if not (board.footprints[ref].dnp or a.net in blocked or b.net in blocked):
            links.setdefault(a.net, []).append((ref, a, b))
            links.setdefault(b.net, []).append((ref, b, a))
    return links


def _walk(links: dict[str, list[tuple[str, Pad, Pad]]], net: str) -> dict:
    """The nets a breadth-first walk through `links` reaches from `net`: net -> (from net, ref, near pad, far pad),
    `net` itself -> None."""
    came: dict[str, tuple[str, str, Pad, Pad] | None] = {net: None}
    queue = deque([net])
    while queue:
        here = queue.popleft()
        for ref, near, far in links.get(here, ()):
            if far.net not in came:
                came[far.net] = (here, ref, near, far)
                queue.append(far.net)
    return came


def trace_chain(board: Board, start: str, end: str, classes: Classes | None = None,
                antenna: str | None = None) -> Chain:
    """The chain from pad `start` to pad `end`: the nets on the way, the series parts between them and the shunt
    parts that touch them, DNP ones too. The walk is breadth first, so it takes the fewest parts, trying the parts of
    a net in ref order. A part is a footprint with exactly two pads with a net, on two nets; a connector or a shield
    is none. Given `antenna`, the antenna footprint (Stage 3 design 5.1) ends the chain and is never a part. Raises
    KrsError: E_SAME_PADS, E_UNKNOWN_PAD, E_AMBIGUOUS_PAD, E_START_ON_GND, E_NO_CHAIN."""
    if start == end:
        raise KrsError("E_SAME_PADS", name=start)
    classes = classify(board) if classes is None else classes
    start_net = _resolve(board, classes, start)[0].net
    end_net = _resolve(board, classes, end)[0].net
    came = _walk(_links(board, classes, antenna), start_net)
    if end_net not in came:
        raise KrsError("E_NO_CHAIN", start=start, end=end, reached=", ".join(sorted(came)))
    nets, series = [end_net], []
    while (step := came[nets[-1]]) is not None:
        previous, ref, near, far = step
        series.append(ChainPart(ref, (near.name, far.name), (near.net, far.net)))
        nets.append(previous)
    nets.reverse()
    series.reverse()
    on_chain, used, shunt = set(nets), {p.ref for p in series}, []
    for ref, (a, b) in _parts(board, classes, antenna).items():
        if ref not in used and (a.net in on_chain or b.net in on_chain):
            a, b = (a, b) if a.net in on_chain else (b, a)
            shunt.append(ChainPart(ref, (a.name, b.name), (a.net, b.net)))
    return Chain(start, end, tuple(nets), tuple(series), tuple(shunt))


def trace_line(board: Board, classes: Classes, start: str, end: str) -> Chain:
    """An SI line from pad `start` to pad `end` (Stage 4 design 5.1): trace_chain's chain. Where it raises E_NO_CHAIN
    and a footprint of three or more copper pads with a net, no connector or shield, has a pad on a net the walk
    reaches from `start` and another on one it reaches from `end`, E_SI_THROUGH_PART {start, end, refs} names those
    footprints instead: the line runs through a part the model cannot hold."""
    try:
        return trace_chain(board, start, end, classes)
    except KrsError as e:
        if e.code != "E_NO_CHAIN":
            raise
        # ponytail: a part of three or more pads is found by the nets it bridges, not by geometry; a choke whose other
        # side the walk cannot reach (a GND net) still reads E_NO_CHAIN
        links, not_parts = _links(board, classes), classes.connectors | classes.shields
        near, far = (_walk(links, _resolve(board, classes, name)[0].net) for name in (start, end))
        refs = [ref for ref in sorted(board.footprints) if ref not in not_parts
                and len(pads := _netted(board.footprints[ref])) >= 3
                and any(p.net in near for p in pads) and any(p.net in far for p in pads)]
        if not refs:
            raise
        raise KrsError("E_SI_THROUGH_PART", start=start, end=end, refs=", ".join(refs)) from None


@dataclass(frozen=True)
class Reference:
    """Where a port's reference sits: on a pad (`pad`, `uuid`) for the connector and ic rules, or at a `point` on
    ground copper for the copper rule. `layer` is the copper layer it is on."""
    rule: str  # "connector" | "ic" | "copper"
    pad: str | None
    uuid: str | None
    point: XY | None
    layer: str


def signal_layer(board: Board, pad: Pad) -> str:
    """The copper layer of a port at `pad` (M-6): the first of its layers where a track of its net touches it, else
    its first layer. A through-hole pad lists every copper layer, and its signal leaves on the track's."""
    return next((layer for layer in pad.layers if any(
        t.layer == layer and t.net == pad.net and t.polygon().intersects(pad.polygon) for t in board.tracks)),
        pad.layers[0])


def choose_reference(board: Board, classes: Classes, signal: str, rank: int = 0) -> Reference | None:
    """The reference of the port at pad `signal` (spec 5.6): the nearest ground pad of its connector or IC (centre to
    centre; a tie goes to the lower pad number, then the lower uuid), else the nearest ground copper. It always lies
    on the signal pad's layer, `signal_layer`. A `rank` k > 0 gives the k-th next best of that rule's own order
    (spec 9.4 criterion 3, D-18): the next ground pad, or the nearest point of another piece of the layer's ground
    copper united, by (distance, x, y); a pad rule never goes on to the copper rule. None when there is none.
    Raises KrsError for a signal that `trace_chain` would refuse as an end."""
    sig = _resolve(board, classes, signal)[0]
    layer = signal_layer(board, sig)
    fp = board.footprints[sig.ref]
    rule = "connector" if sig.ref in classes.connectors else "ic" if len(_copper(fp)) >= 3 else None
    # a pad that lists `layer` has copper there, so the layer test also leaves out the pads without copper
    grounds = [p for p in fp.pads if p.net in classes.gnd and layer in p.layers] if rule else []
    if grounds:
        # ponytail: pad numbers compare as text ("10" before "2"); it only matters between exactly equal distances
        grounds.sort(key=lambda p: (round(math.dist(sig.center, p.center), TIE_DECIMALS), p.number, p.uuid))
        if rank >= len(grounds):
            return None  # a pad rule never goes on to the copper rule (PF-8)
        return Reference(rule, grounds[rank].name, grounds[rank].uuid, None, layer)
    shapes = [t.polygon() for t in board.tracks if t.layer == layer and t.net in classes.gnd]
    shapes += [a.polygon for a in board.areas if a.layer == layer and a.net in classes.gnd]
    shapes += [p.polygon for f in board.footprints.values() for p in f.pads
               if layer in p.layers and p.net in classes.gnd]
    shapes = [s for s in shapes if not s.is_empty]  # a zero-width track has no copper, and its distance is NaN
    if not shapes:
        return None
    here = Point(sig.center)
    # ponytail: measures every ground shape of the layer once per port; an STRtree if a big board makes it slow
    order = [nearest_points(here, min(shapes, key=here.distance))[1]]
    if rank:
        # the rank-0 point lies on its piece's outline, where an exact intersects test can miss by float noise: a
        # piece within 1e-6 mm of it holds it
        pieces = [q for q in shapely.get_parts(shapely.union_all(shapes)) if q.distance(order[0]) > 1e-6]
        order += sorted((nearest_points(here, q)[1] for q in pieces),
                        key=lambda p: (round(here.distance(p), TIE_DECIMALS), p.x, p.y))
    return Reference("copper", None, None, order[rank].coords[0], layer) if rank < len(order) else None


def partner_net(net: str, nets: Collection[str]) -> tuple[str, str] | None:
    """The partner of `net` among the board's `nets` (Stage 4 design 5.1), and how: KiCad's own rule
    (BOARD::MatchDpSuffix, KiCad 10 pcbnew/board.cpp): from the name's end, past digits and underscores, a + or -, or
    an upper-case P or N, swapped ("rule"); else the DP/DM alias of a name whose last letters there are DP or DM
    ("alias"); None when neither complement is a net of the board."""
    stem = net.rstrip("0123456789_")
    swap = {"+": "-", "-": "+", "P": "N", "N": "P"}.get(stem[-1:])
    if swap and (other := stem[:-1] + swap + net[len(stem):]) in nets:
        return other, "rule"
    if (m := _ALIAS.fullmatch(net)) and (other := m[1] + {"P": "M", "M": "P"}[m[2]] + m[3]) in nets:
        return other, "alias"
    return None


def partner_ends(board: Board, classes: Classes, start: str, end: str) -> tuple[str, str, str]:
    """The partner's two ends (Stage 4 design 5.1): for each of pads `start` and `end`, its net's partner (partner_net,
    among board.nets) and that net's one copper pad on the same footprint; and how, "alias" when either end took the
    alias, else "rule". E_SI_PARTNER {net, pad, ref, partner, pads}, naming --pair-with, when a net has no partner
    (partner and pads T_NONE) or its footprint holds not exactly one pad of it (pads joined by ", ", T_NONE for
    none)."""
    ends, hows = [], []
    for name in (start, end):
        pad = _resolve(board, classes, name)[0]
        partner, how = partner_net(pad.net, board.nets) or (None, None)
        pads = sorted({p.name for p in _copper(board.footprints[pad.ref]) if p.net == partner})
        if len(pads) != 1:
            raise KrsError("E_SI_PARTNER", net=pad.net, pad=name, ref=pad.ref, partner=partner or "T_NONE",
                           pads=", ".join(pads) or "T_NONE")
        ends.append(pads[0])
        hows.append(how)
    return ends[0], ends[1], "alias" if "alias" in hows else "rule"


def antenna_kind(board: Board, ref: str) -> str | None:
    """What footprint `ref` is as an antenna (Stage 3 design 5.1), the first that holds: "module" for an RF_Module:
    library id; "printed" when the copper graphics it draws cover more area than its copper pads, a radiator and never
    a net-tie stub; "chip" for an AE reference or an RF_Antenna: library id, keep-outs or not; "module" for any other
    footprint with a keep-out; else None."""
    # ponytail: a custom-library module that draws more copper than its pads reads printed, and a connector or
    # converter with a keep-out reads module in antenna_kinds (check_antenna's candidates list only printed ones); a
    # class test if plan 5's list shows them
    fp = board.footprints[ref]
    if fp.lib_id.startswith("RF_Module:"):
        return "module"
    if sum(a.polygon.area for a in board.areas if a.ref == ref) > sum(p.polygon.area for p in _copper(fp)):
        return "printed"
    if _prefix(ref) == "AE" or fp.lib_id.startswith("RF_Antenna:"):
        return "chip"
    return "module" if fp.keepout else None


def antenna_kinds(board: Board) -> dict[str, str]:
    """The kind of each footprint that `antenna_kind` reads as an antenna, by reference, in reference order."""
    return {ref: kind for ref in sorted(board.footprints) if (kind := antenna_kind(board, ref))}


def _no_kind(board: Board, code: str, ref: str) -> KrsError:
    """The refusal `code` of footprint `ref`, which names no antenna kind, with the printed antennas on the board as
    its candidates (T_NONE when there is none)."""
    printed = [r for r, kind in antenna_kinds(board).items() if kind == "printed"]
    return KrsError(code, ref=ref, candidates=", ".join(printed) or "T_NONE")


def check_antenna(board: Board, ref: str) -> None:
    """Refuses footprint `ref` as a project's antenna unless `antenna_kind` reads it as printed (Stage 3 design 5.1).
    Raises KrsError: E_ANTENNA_UNKNOWN for a ref not on the board, E_ANTENNA_MODULE or E_ANTENNA_CHIP by its kind and
    E_NOT_AN_ANTENNA for a footprint of no kind; the first and the last name the printed antennas on the board."""
    if ref not in board.footprints:
        raise _no_kind(board, "E_ANTENNA_UNKNOWN", ref)
    kind = antenna_kind(board, ref)
    if kind == "module":
        raise KrsError("E_ANTENNA_MODULE", ref=ref)
    if kind == "chip":
        raise KrsError("E_ANTENNA_CHIP", ref=ref)
    if kind is None:
        raise _no_kind(board, "E_NOT_AN_ANTENNA", ref)


def feed_pad(board: Board, classes: Classes, ref: str) -> Pad:
    """The feed pad of antenna `ref` (Stage 3 design 5.1): the first by number of its copper pads on its one signal
    net, a net that is neither empty, GND nor power. Raises KrsError E_ANTENNA_FEED, naming its signal nets (T_NONE
    for none), when it has not exactly one."""
    pads = [p for p in _netted(board.footprints[ref]) if p.net not in classes.gnd | classes.power]
    nets = sorted({p.net for p in pads})
    if len(nets) != 1:
        raise KrsError("E_ANTENNA_FEED", ref=ref, nets=", ".join(nets) or "T_NONE")
    # ponytail: pad numbers compare as text ("10" before "2"); it only matters for an antenna with two feed pads
    return min(pads, key=lambda p: p.number)


def adopt(board: Board, ref: str, net: str) -> None:
    """Gives the antenna footprint `ref`'s netless copper, its copper graphics and its pads with no net, the net `net`,
    in place (Stage 3 design 5.3), and drops those graphics' W_NETLESS_COPPER. E_ANTENNA_UNKNOWN for a ref not on the
    board."""
    # ponytail: every netless piece of the footprint takes the feed net; a floating parasitic element would then read as
    # an open of it (E_OPEN_IN_ROI); adopt only the copper the feed pad reaches if one appears
    if ref not in board.footprints:
        raise _no_kind(board, "E_ANTENNA_UNKNOWN", ref)
    drawn = {a.uuid for a in board.areas if a.ref == ref and not a.net}
    board.areas = [replace(a, net=net) if a.ref == ref and not a.net else a for a in board.areas]
    fp = board.footprints[ref]
    board.footprints[ref] = replace(fp, pads=tuple(p if p.net else replace(p, net=net) for p in fp.pads))
    board.warnings = [(code, params) for code, params in board.warnings
                      if not (code == "W_NETLESS_COPPER" and params["uuid"] in drawn)]
