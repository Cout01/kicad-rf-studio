# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI client (Stage 2 design 5): `control`, the Qt-free logic, and `window`, the main window; main(), one window
per user (instance_name, forward, the lock file). `import kicad_rf_studio.gui` loads no Qt or matplotlib: main(),
forward() and qtbase() import Qt inside themselves."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from kicad_rf_studio import runs
from kicad_rf_studio.core.messages import language

START_WAIT_S = 10.0  # how long a start waits for a window that holds the lock to listen


def instance_name() -> str:
    """The GUI's local server (design 5.5): per user, and per test through the `fake` fixture's data folder. Here, not
    in `control`, so that a second start forwards without loading it (0.8 s: pipeline, numpy, scipy)."""
    return "kicad-rf-studio-" + hashlib.sha256(str(runs.data_dir()).encode("utf-8")).hexdigest()[:16]


def forward(name: str, request: dict) -> bool:
    """Hands `request` to the window that serves `name` as one JSON line; False when none connects within 1 s."""
    # ponytail: fire and forget: a request written to a window that closes before reading it is lost, and the user
    # presses again; an answer line if users meet it
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(name)
    if not sock.waitForConnected(1000):
        return False
    sock.write(json.dumps(request).encode("utf-8") + b"\n")
    sock.waitForBytesWritten()  # its result ignored: on Windows the write may already be done (probed)
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        sock.waitForDisconnected(1000)
    return True


def qtbase(language: str):
    """A QTranslator holding PySide6's own qtbase_<language>.qm (pt-BR design 5.2): Yes/No, context menus, spin box
    steps, About Qt; None for English, or for a language PySide6 has no file for."""
    from PySide6.QtCore import QLibraryInfo, QTranslator
    translator = QTranslator()
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    return translator if language != "en" and translator.load(f"qtbase_{language}", folder) else None


def main(argv: list[str] | None = None) -> int:
    """The kicad-rf-studio-gui entry (`argv` is sys.argv[1:] when None, as the gui-scripts entry calls it): a PROJECT
    (a project.json or its folder) and a KiCad button press's handoff FILE (--handoff), each optional, as the request
    {"project", "handoff"} with absolute paths. One window per user (design 5.5): the request is forwarded to the window
    that runs, and 0 returned at once; otherwise this start takes gui.lock in the data folder, or, while a live start
    holds it, forwards again every 0.2 s for up to START_WAIT_S, then listens on instance_name() and shows the main
    window, which acts on the request and keeps the server and the lock until it closes (a failed listen unlocks at
    once); it returns the app's exit code once it quits. Qt's own words follow the catalog's language while the
    window runs (qtbase). Without a console (pythonw, which runs the gui-scripts entry on Windows) sys.stderr is
    None, so it first appends to gui.log in the data folder, where a slot's traceback and an argument error land."""
    if sys.stderr is None:
        runs.data_dir().mkdir(parents=True, exist_ok=True)
        sys.stderr = open(runs.data_dir() / "gui.log", "a", encoding="utf-8")
    parser = argparse.ArgumentParser(prog="kicad-rf-studio-gui")
    parser.add_argument("project", nargs="?")
    parser.add_argument("--handoff", metavar="FILE")
    args = parser.parse_args(argv)
    request = {key: None if value is None else str(Path(value).absolute()) for key, value in vars(args).items()}
    from PySide6.QtCore import QLockFile
    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    name = instance_name()
    if forward(name, request):
        return 0
    runs.data_dir().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(runs.data_dir() / "gui.lock"))
    lock.setStaleLockTime(0)  # a dead holder's lock is taken over by its PID, never by its age
    # ponytail: a window that holds the lock but never listens (hung at its start) makes a start wait START_WAIT_S,
    # then open a window of its own; Windows lets two servers listen on one name, and Linux's listen renames over it,
    # so the lock, not listen, keeps one window
    deadline = time.monotonic() + START_WAIT_S
    while not lock.tryLock(0) and time.monotonic() < deadline:  # a live start holds it, and is about to listen
        time.sleep(0.2)
        if forward(name, request):
            return 0
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(name):
        lock.unlock()  # a later start may serve; this window runs without a server
    # ponytail: an exception before exec leaves the translator on the app; a try/finally if a caller ever reuses its app
    # after one
    translator = qtbase(language())
    if translator is not None:
        app.installTranslator(translator)
    from kicad_rf_studio.gui.window import MainWindow

    win = MainWindow()
    win.serve(server, lock)
    win.act(request)
    code = app.exec()
    if translator is not None:
        app.removeTranslator(translator)  # at once, not when collected: an app that outlives main is left as it was
    return code
