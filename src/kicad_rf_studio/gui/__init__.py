# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI client (Stage 2 design 5): `control`, the Qt-free launcher, events tail and re-attach, and `window`, the
main window. `import kicad_rf_studio.gui` loads no Qt or matplotlib: main() imports Qt inside itself."""
import sys
from pathlib import Path

from kicad_rf_studio import runs


def main(argv: list[str] | None = None) -> int:
    """The kicad-rf-studio-gui entry: shows the main window, with the project `argv[0]` open when given (a
    project.json or its folder; `argv` is sys.argv[1:] when None, as the gui-scripts entry calls it), and returns the
    app's exit code once it quits. Without a console (pythonw, which runs the gui-scripts entry on Windows)
    sys.stderr is None, so it first appends to gui.log in the data folder, where a slot's traceback lands."""
    argv = sys.argv[1:] if argv is None else argv
    if sys.stderr is None:
        runs.data_dir().mkdir(parents=True, exist_ok=True)
        sys.stderr = open(runs.data_dir() / "gui.log", "a", encoding="utf-8")
    from PySide6.QtWidgets import QApplication

    from kicad_rf_studio.gui.window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    win = MainWindow()
    if argv:
        win.open_project(Path(argv[0]))
    win.show()
    return app.exec()
