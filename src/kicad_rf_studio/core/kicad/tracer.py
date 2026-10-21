# SPDX-License-Identifier: GPL-3.0-or-later
"""Net classes, the RF chain between two pads and the reference of a port (spec 4.6 and 5.6). Only pads that carry
copper count here: a paste-only pad, or a hole with no copper, is left out of every rule."""
from __future__ import annotations

import difflib
import math
import re
from collections import deque
from dataclasses import dataclass

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


def _resolve(board: Board, classes: Classes, name: str) -> list[Pad]:
    """The pads with copper called `name` ("REF.NUM"). They sit on one net, which a chain may touch."""
    pads = [p for p in board.pads(name) if p.layers]
    if not pads:
        known = {p.name for fp in board.footprints.values() for p in _copper(fp)}
        raise KrsError("E_UNKNOWN_PAD", name=name,
                       candidates=", ".join(difflib.get_close_matches(name, known, n=5)) or "none")
    nets = {p.net for p in pads}
    if len(nets) > 1:
        raise KrsError("E_AMBIGUOUS_PAD", name=name, nets=", ".join(sorted(nets)))
    net = pads[0].net
    if not net or net in classes.gnd or net in classes.power:
        raise KrsError("E_START_ON_GND", name=name, net=net)
    return pads


def trace_chain(board: Board, start: str, end: str, classes: Classes | None = None) -> Chain:
    """The chain from pad `start` to pad `end`: the nets on the way, the series parts between them and the shunt
    parts that touch them, DNP ones too. The walk is breadth first, so it takes the fewest parts, trying the parts of
    a net in ref order. A part is a footprint with exactly two pads with a net, on two nets; a connector or a shield
    is none. Raises KrsError: E_SAME_PADS, E_UNKNOWN_PAD, E_AMBIGUOUS_PAD, E_START_ON_GND, E_NO_CHAIN."""
    if start == end:
        raise KrsError("E_SAME_PADS", name=start)
    classes = classify(board) if classes is None else classes
    start_net = _resolve(board, classes, start)[0].net
    end_net = _resolve(board, classes, end)[0].net
    blocked, not_parts = classes.gnd | classes.power, classes.connectors | classes.shields
    parts: dict[str, list[Pad]] = {}  # by ref: the footprints with exactly two pads with a net, on two nets
    for ref in sorted(board.footprints):
        pads = _netted(board.footprints[ref])
        if len(pads) == 2 and pads[0].net != pads[1].net and ref not in not_parts:
            parts[ref] = pads
    links: dict[str, list[tuple[str, Pad, Pad]]] = {}  # net -> (ref, its pad on the net, its pad on the other net)
    for ref, (a, b) in parts.items():
        if not (board.footprints[ref].dnp or a.net in blocked or b.net in blocked):
            links.setdefault(a.net, []).append((ref, a, b))
            links.setdefault(b.net, []).append((ref, b, a))
    came: dict[str, tuple[str, str, Pad, Pad] | None] = {start_net: None}  # net -> (from net, ref, near pad, far pad)
    queue = deque([start_net])
    while queue:
        net = queue.popleft()
        for ref, near, far in links.get(net, ()):
            if far.net not in came:
                came[far.net] = (net, ref, near, far)
                queue.append(far.net)
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
    for ref, (a, b) in parts.items():
        if ref not in used and (a.net in on_chain or b.net in on_chain):
            a, b = (a, b) if a.net in on_chain else (b, a)
            shunt.append(ChainPart(ref, (a.name, b.name), (a.net, b.net)))
    return Chain(start, end, tuple(nets), tuple(series), tuple(shunt))


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


def choose_reference(board: Board, classes: Classes, signal: str) -> Reference | None:
    """The reference of the port at pad `signal` (spec 5.6): the nearest ground pad of its connector or IC (centre to
    centre; a tie goes to the lower pad number, then the lower uuid), else the nearest ground copper. It always lies
    on the signal pad's layer, `signal_layer`. None when there is none. Raises KrsError for a signal that
    `trace_chain` would refuse as an end."""
    sig = _resolve(board, classes, signal)[0]
    layer = signal_layer(board, sig)
    fp = board.footprints[sig.ref]
    rule = "connector" if sig.ref in classes.connectors else "ic" if len(_copper(fp)) >= 3 else None
    # a pad that lists `layer` has copper there, so the layer test also leaves out the pads without copper
    grounds = [p for p in fp.pads if p.net in classes.gnd and layer in p.layers] if rule else []
    if grounds:
        # ponytail: pad numbers compare as text ("10" before "2"); it only matters between exactly equal distances
        near = min(grounds, key=lambda p: (round(math.dist(sig.center, p.center), TIE_DECIMALS), p.number, p.uuid))
        return Reference(rule, near.name, near.uuid, None, layer)
    shapes = [t.polygon() for t in board.tracks if t.layer == layer and t.net in classes.gnd]
    shapes += [a.polygon for a in board.areas if a.layer == layer and a.net in classes.gnd]
    shapes += [p.polygon for f in board.footprints.values() for p in f.pads
               if layer in p.layers and p.net in classes.gnd]
    shapes = [s for s in shapes if not s.is_empty]  # a zero-width track has no copper, and its distance is NaN
    if not shapes:
        return None
    here = Point(sig.center)
    # ponytail: measures every ground shape of the layer once per port; an STRtree if a big board makes it slow
    x, y = nearest_points(here, min(shapes, key=here.distance))[1].coords[0]
    return Reference("copper", None, None, (x, y), layer)
