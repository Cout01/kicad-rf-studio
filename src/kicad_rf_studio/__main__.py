# SPDX-License-Identifier: GPL-3.0-or-later
"""`python -m kicad_rf_studio` runs the CLI: how Stage 2's GUI starts the orchestrator (design 5.1)."""
import sys

from kicad_rf_studio.cli import main

if __name__ == "__main__":
    sys.exit(main())
