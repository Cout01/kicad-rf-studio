# SPDX-License-Identifier: GPL-3.0-or-later
"""The review's tags (Stage 5 design 5.1; BC2): the nets R1 to R3 measure, each with the first source that tagged it,
in this order: the nets named (flags), the project's chain, A8's name patterns past the deny list (only with no flag),
and a walk from those through two-pad series parts and differential partners. Ground and power never take a tag."""
from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from fnmatch import fnmatchcase

from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.tracer import Classes, _base, _links, _walk, partner_net

FAMILIES = {name: re.compile(expr, re.IGNORECASE) for name, expr in (  # r1's expressions cut to A8's seven
    ("CLK", r".*(CLK|LRCK|OSC).*"),
    ("SCK", r".*SCK.*"),
    ("XTAL", r".*(XTAL|XIN|XOUT).*"),
    ("SW", r"(SW|LX|PH)\d*|.*_(SW|LX)\d*"),
    ("SPI", r".*(SPI|SDIO|MOSI|MISO).*|.*(SDO|SDI)\d*"),
    ("I2S", r".*I2S.*"),
    ("USB", r".*USB.*"))}
DENY = frozenset({"CTRL", "NSS", "DIO", "BUSY", "RST", "IRQ", "EN", "CS"})


def family(net: str) -> str | None:
    """The first family whose expression fullmatches the net's own name, `_base(net)`; None when none does, or when
    the name's last "_" word, upper-cased with its trailing digits stripped, is in DENY (SPI_CS, CLK_EN)."""
    name = _base(net)
    if name.rsplit("_", 1)[-1].upper().rstrip("0123456789") in DENY:
        return None
    return next((f for f, expr in FAMILIES.items() if expr.fullmatch(name)), None)


def tag(board: Board, classes: Classes, never: Collection[str], flags: Sequence[str] = (),
        chain_nets: Collection[str] = ()) -> tuple[dict[str, str], list[str]]:
    """The tags, net -> source sorted by net, and the flags that match no net the review can tag. A net takes the
    first source that tags it: "flag", a board net that fnmatchcase matches against a flag by full name or by
    `_base` (past the deny list); "project", a net of `chain_nets`; "pattern:<family>", only with no flag; then
    "walk", breadth first from every net tagged so far, through `_walk` over `_links` and `partner_net`. A net of
    `never` (the plane nets) or the empty net is never tagged, and the walk never passes through one."""
    blocked = {*never, ""}
    nets = [n for n in board.nets if n not in blocked]
    hits = {f: {n for n in nets if fnmatchcase(n, f) or fnmatchcase(_base(n), f)} for f in flags}
    flagged = set().union(*hits.values())
    tags: dict[str, str] = {}
    for n in nets:
        if n in flagged:
            tags[n] = "flag"
        elif n in chain_nets:
            tags[n] = "project"
        elif not flags and (f := family(n)):
            tags[n] = f"pattern:{f}"
    # _links leaves out the parts on classes.gnd and classes.power; `never` also holds the dotted supplies POWER misses
    links = {n: [(ref, near, far) for ref, near, far in steps if far.net not in blocked]
             for n, steps in _links(board, classes).items()}
    queue = list(tags)
    for net in queue:  # breadth first: the queue grows behind the loop
        reached = list(_walk(links, net))
        if partner := partner_net(net, board.nets):
            reached.append(partner[0])
        for other in reached:
            if other not in tags and other not in blocked:
                tags[other] = "walk"
                queue.append(other)
    return dict(sorted(tags.items())), [f for f, hit in hits.items() if not hit]
