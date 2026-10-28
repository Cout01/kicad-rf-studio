# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI client (Stage 2 design 5): `control`, the Qt-free launcher, events tail and re-attach, and `window`, the
main window. `import kicad_rf_studio.gui` loads no Qt or matplotlib: main() imports Qt inside itself."""
import sys

from kicad_rf_studio import runs
from kicad_rf_studio.core.messages import render


def main(argv: list[str] | None = None) -> int:
    """The kicad-rf-studio-gui entry: shows the main window and returns the app's exit code once it quits. Without a
    console (pythonw, which runs the gui-scripts entry on Windows) sys.stderr is None, so it first appends to gui.log
    in the data folder, where a slot's traceback lands."""
    if sys.stderr is None:
        runs.data_dir().mkdir(parents=True, exist_ok=True)
        sys.stderr = open(runs.data_dir() / "gui.log", "a", encoding="utf-8")
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    win = QMainWindow()
    win.setWindowTitle(render("G_APP"))
    win.show()
    return app.exec()
