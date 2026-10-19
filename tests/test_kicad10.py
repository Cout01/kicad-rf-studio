# SPDX-License-Identifier: GPL-3.0-or-later
"""CI tier (c): a board saved by KiCad 9 must read the same after KiCad 10 has upgraded it.

KRS_KICAD9_DIR holds the KiCad 9 boards and KRS_KICAD10_DIR their upgraded copies, under the same names.
Without both variables the whole file is skipped."""
import math
import os
from collections import Counter
from pathlib import Path

import pytest

from kicad_rf_studio.core.kicad import load_board

OLD, NEW = os.environ.get("KRS_KICAD9_DIR"), os.environ.get("KRS_KICAD10_DIR")
# skipped tests rather than a skipped module: run alone, a skipped module exits 5 ("no tests collected")
pytestmark = pytest.mark.skipif(
    not (OLD and NEW), reason="set KRS_KICAD9_DIR and KRS_KICAD10_DIR to compare boards before and after an upgrade")

BOARDS = sorted(Path(OLD).glob("*.kicad_pcb")) if OLD else []


def test_there_are_boards_to_compare():
    assert BOARDS, f"no .kicad_pcb files in {OLD}"


def pads(board):
    return {p.uuid: p for fp in board.footprints.values() for p in fp.pads}


def used_nets(board):
    """The nets some item sits on. Board.nets also lists header nets that no item uses, and an upgrade may
    drop those."""
    on_items = ({t.net for t in board.tracks} | {v.net for v in board.vias} | {a.net for a in board.areas}
                | {p.net for fp in board.footprints.values() for p in fp.pads})
    return on_items - {""}


@pytest.mark.parametrize("path", BOARDS, ids=lambda p: p.stem)
def test_upgraded_board_reads_the_same(path):
    old, new = load_board(path), load_board(Path(NEW) / path.name)
    assert used_nets(old) == used_nets(new)
    assert len(old.tracks) == len(new.tracks) and len(old.vias) == len(new.vias)
    # KiCad 9 gives an item a net code and KiCad 10 a name: each item must still land on the same net
    assert Counter((t.layer, t.net) for t in old.tracks) == Counter((t.layer, t.net) for t in new.tracks)
    assert Counter((v.layers, v.net) for v in old.vias) == Counter((v.layers, v.net) for v in new.vias)
    assert sorted(old.footprints) == sorted(new.footprints)
    old_pads, new_pads = pads(old), pads(new)
    assert set(old_pads) == set(new_pads)
    for uuid, pad in old_pads.items():
        assert math.dist(pad.center, new_pads[uuid].center) <= 1e-6, pad.name
