# SPDX-License-Identifier: GPL-3.0-or-later
"""The test-only CLI entry (Stage 2 design 5.8): `python -X utf8 -I tests/fake_cli.py COMMAND ...` applies the fake's
patches of runs (patches(), which tests/conftest.py's `fake` applies too), with $KRS_FAKE_DATA as the data folder,
then runs cli.main, so a detached orchestrator started by the GUI's code runs tests/fake_worker.py."""
import os
import sys
from pathlib import Path

from kicad_rf_studio import cli, runs


def patches(data: Path) -> dict:
    """The fake's patches of runs: tests/fake_worker.py as the worker, fast polls, `data` as the data folder and an
    openEMS check that passes."""
    return {"WORKER": ("-I", "-u", str(Path(__file__).with_name("fake_worker.py"))), "POLL_S": 0.02,
            "ABORT_WAIT_S": 5.0, "data_dir": lambda: data, "check_openems": lambda: []}


if __name__ == "__main__":
    for name, value in patches(Path(os.environ["KRS_FAKE_DATA"])).items():
        setattr(runs, name, value)
    sys.exit(cli.main())
