# SPDX-License-Identifier: GPL-3.0-or-later
"""The review's golden outputs (Stage 5 design 5.14; plan 1 ruling 4): each review fixture's review.json as `review`
writes it on the board copied into the working folder (golden_antenna._board, LF line ends as git stores it), so the
golden names the board by its file name and its sha256 only. Plan 1's Task 11 records them once; a deliberate change is
a ruled re-recording: delete tests/fixtures/review and run this again from the repo root."""
import contextlib
import sys
import tempfile
from pathlib import Path

import p0
from golden_antenna import _board
from kicad_rf_studio import cli

GOLDEN = p0.FIX / "review"
CASES = {"emc_review": [], "usb2_hs": [], "usb2_hs_gap": [], "qspi_clk": [],
         "lpf915": ["--net", "RF_*", "--f0", "915MHz"]}  # lpf915's RF nets match no pattern


def golden_bytes(name: str) -> bytes:
    """The review.json `review` writes into the folder `name` on the fixture `name`, its board copied into the working
    folder (_board), with CASES[name]'s options. Run it in an empty working folder."""
    code = cli.main(["review", _board(name), *CASES[name], "-o", name])  # outside the assert, which python -O drops
    assert code == 0, code
    return Path(name, "review.json").read_bytes()


def main() -> int:
    """Writes each case's golden_bytes to GOLDEN, made here, each from an empty temporary working folder, and returns 0;
    1 when GOLDEN exists."""
    if GOLDEN.exists():
        print("golden_review: tests/fixtures/review exists; a re-recording is a ruling, which deletes it first",
              file=sys.stderr)
        return 1
    GOLDEN.mkdir()
    for name in CASES:
        # chdir's exit restores the starting folder before the folder is removed: Windows cannot remove a working one
        with tempfile.TemporaryDirectory() as folder, contextlib.chdir(folder):
            (GOLDEN / f"{name}.json").write_bytes(golden_bytes(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
