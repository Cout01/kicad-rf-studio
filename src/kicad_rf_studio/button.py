# SPDX-License-Identifier: GPL-3.0-or-later
"""The KiCad toolbar button (Stage 2 design 5.5): the helper KiCad's exec action runs (main), which reads the board and
the selection through kicad-python and hands them to the GUI; the GUI's Refill zones and save in KiCad (refill); and
its installer (install), which writes the exec plugin into KiCad's plugin folders. Qt-free; kicad-python is imported
only inside the functions that call KiCad, so importing this module loads none."""
import contextlib
import ctypes
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import sysconfig
import time
import warnings
import zlib
from pathlib import Path

from kicad_rf_studio import runs
from kicad_rf_studio.core.messages import KrsError, detail, reason, render
from kicad_rf_studio.core.project import save_project

TIMEOUT_MS = 1000  # one API call's wait
BUSY_S = 1.0  # a press's whole wait on AS_BUSY
BUSY_WAIT_S = 0.25  # the pause before KiCad, busy, is asked again


def _kicad(socket: str, token: str, timeout_ms: int = TIMEOUT_MS):
    """kipy's client of the KiCad API server at `socket` (kipy's default when empty), sending KiCad's `token`."""
    from kipy import KiCad
    return KiCad(socket_path=socket or None, client_name="kicad-rf-studio", kicad_token=token, timeout_ms=timeout_ms)


def _call(fn, until: float = 0.0):
    """`fn()`, asked again BUSY_WAIT_S later while KiCad answers AS_BUSY and `until` (a time.monotonic() deadline; 0,
    never again) leaves time for it. KiCad's errors are the button's refusals: AS_BUSY past the deadline E_KICAD_BUSY,
    AS_UNHANDLED and AS_UNIMPLEMENTED (not in this KiCad) E_KICAD_UNSUPPORTED, AS_TOKEN_MISMATCH (a KiCad restarted
    since) and no answer E_KICAD_UNREACHABLE. Any other error is raised as it is."""
    # ponytail: one 1 s for AS_BUSY over the whole press (the helper must end within about 2 s), and each answer may
    # take TIMEOUT_MS, so three answers just under it take about 3 s; a longer budget if KiCad is seen busy or slow at
    # a click
    import kipy.errors
    from kipy.proto.common import ApiStatusCode
    refusals = {ApiStatusCode.AS_BUSY: "E_KICAD_BUSY", ApiStatusCode.AS_UNHANDLED: "E_KICAD_UNSUPPORTED",
                ApiStatusCode.AS_UNIMPLEMENTED: "E_KICAD_UNSUPPORTED",
                ApiStatusCode.AS_TOKEN_MISMATCH: "E_KICAD_UNREACHABLE"}
    while True:
        try:
            return fn()
        except kipy.errors.ConnectionError:  # kipy's, no OSError: no server, or no answer within the client's timeout
            raise KrsError("E_KICAD_UNREACHABLE") from None
        except kipy.errors.ApiError as e:
            if e.code == ApiStatusCode.AS_BUSY and time.monotonic() + BUSY_WAIT_S < until:
                time.sleep(BUSY_WAIT_S)
            elif e.code in refusals:
                raise KrsError(refusals[e.code]) from None
            else:
                raise


def _board_path(board) -> Path:
    """The file of kipy's `board`: its project's folder joined with its file name. Raises E_KICAD_NO_BOARD for a new
    board KiCad never saved, which has no file name."""
    document = board.document
    if not document.board_filename:
        raise KrsError("E_KICAD_NO_BOARD")
    return Path(document.project.path) / document.board_filename


def read(socket: str, token: str) -> dict:
    """A press (design 5.5 steps 1-2): the board KiCad's PCB editor has open, its selected pads (KIIDs) and footprints
    (references), and KiCad's version, with `socket` and `token`. Its calls share one BUSY_S on AS_BUSY (_call). Raises
    E_KICAD_VERSION for a KiCad other than 9 or 10, and the errors of _call and _board_path."""
    from kipy.board_types import FootprintInstance, Pad
    from kipy.proto.common.types import KiCadObjectType
    until = time.monotonic() + BUSY_S
    kicad = _kicad(socket, token)
    found = _call(kicad.get_version, until)  # never check_version(): it refuses any KiCad newer than kipy's 10.0.6
    version = f"{found.major}.{found.minor}.{found.patch}"
    if found.major not in (9, 10):
        raise KrsError("E_KICAD_VERSION", version=version)
    board = _call(kicad.get_board, until)
    path = _board_path(board)
    types = [KiCadObjectType.KOT_PCB_PAD, KiCadObjectType.KOT_PCB_FOOTPRINT]
    selected = _call(lambda: board.get_selection(types), until)
    return {"board": str(path), "pads": [item.id.value for item in selected if isinstance(item, Pad)],
            "footprints": [item.reference_field.text.value for item in selected if isinstance(item, FootprintInstance)],
            "kicad": version, "socket": socket, "token": token}


def write_handoff(data: dict) -> Path:
    """Writes `data` to handoff.json in the data folder, which it makes, through save_project; returns its path. Raises
    E_HANDOFF_WRITE."""
    # ponytail: one fixed file, the latest press winning, through save_project's one temporary name: two presses within
    # one write, or a press while the window reads it (Windows then refuses the replace), end in E_HANDOFF_WRITE and
    # the user presses again; a file per press if users meet it
    path = runs.data_dir() / "handoff.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        save_project(path, data)
    except OSError as e:
        raise KrsError("E_HANDOFF_WRITE", path=str(path), reason=reason(e, "T_CANNOT_WRITE")) from None
    return path


def gui_command(handoff: Path) -> list[str]:
    """The GUI's command for `handoff`: this environment's gui-scripts entry, never a PATH lookup."""
    name = "kicad-rf-studio-gui.exe" if sys.platform == "win32" else "kicad-rf-studio-gui"
    return [str(Path(sysconfig.get_path("scripts")) / name), "--handoff", str(handoff)]


def start_gui(command: list[str], folder: Path) -> subprocess.Popen:
    """Starts `command` fully detached (design 5.5), in `folder`: stdin and stdout the null device and stderr appended
    to folder/gui.log, so it holds none of KiCad's pipes; on Windows with the design's flags, elsewhere in a session of
    its own."""
    # ponytail: no CREATE_BREAKAWAY_FROM_JOB: in a KiCad job that kills on close the window closes with KiCad, though
    # its runs break away (control.start); add it, with control.start's PermissionError fallback, if the click-through
    # shows such a job
    detach = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
              if sys.platform == "win32" else {"start_new_session": True})
    with open(folder / "gui.log", "ab") as log:
        return subprocess.Popen(command, cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
                                **detach)


FILL_WAIT_S = 120.0  # Refill's wait for KiCad's fill and save, and its client's timeout


def refill(socket: str, token: str, board: Path) -> Path:
    """Refill zones and save in KiCad (design 5.5 Refill), the GUI's only way to save the board (design 7): in the
    KiCad at `socket` with `token`, every zone of `board` refilled, then the board saved; returns `board`. The board
    KiCad's PCB editor has open is read first, within BUSY_S on AS_BUSY: E_KICAD_UNSUPPORTED there (AS_UNHANDLED: the
    PCB editor was closed since the press, so no handler answers) is E_KICAD_NO_BOARD, and a board other than `board`
    E_KICAD_OTHER_BOARD, with nothing sent further. Not refill_zones(block=True): in kipy 0.8.0 that polls forever
    while KiCad answers AS_BUSY (its counter never grows) and raises on a timed-out Ping (it catches IOError, which
    kipy's ConnectionError is not). KiCad only queues the fill, and answers from its main thread, which the fill holds:
    the save, BUSY_WAIT_S later, is asked again while KiCad answers AS_BUSY and waited for while it holds the fill, for
    up to FILL_WAIT_S, on a client whose timeout is FILL_WAIT_S, as the helper's 1 s would read a large board's save
    as an unreachable KiCad. Raises the errors of _call and _board_path too."""
    # ponytail: a fill or a save longer than FILL_WAIT_S, or a KiCad closed mid-refill, ends in E_KICAD_UNREACHABLE
    # after up to FILL_WAIT_S; each refill's kipy client is closed by the garbage collector
    kicad = _kicad(socket, token, int(FILL_WAIT_S * 1000))
    until = time.monotonic() + BUSY_S
    try:
        pcb = _call(kicad.get_board, until)
    except KrsError as e:
        if e.code == "E_KICAD_UNSUPPORTED":
            raise KrsError("E_KICAD_NO_BOARD") from None
        raise
    if (path := _board_path(pcb)) != board:
        raise KrsError("E_KICAD_OTHER_BOARD", board=str(board), open=str(path))
    _call(lambda: pcb.refill_zones(block=False), until)
    time.sleep(BUSY_WAIT_S)  # KiCad only queues the fill
    _call(pcb.save, time.monotonic() + FILL_WAIT_S)
    return board


def main() -> int:
    """KiCad's exec action (design 5.5): hands the board and the selection of the KiCad that runs it to a detached GUI
    through handoff.json and returns 0, printing nothing (KiCad 10 shows any stderr text); or prints why on one stderr
    line, appends it to button.log in the data folder and returns 1."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # KiCad 10 shows any stderr text
            handoff = write_handoff(read(os.environ.get("KICAD_API_SOCKET", ""), os.environ.get("KICAD_API_TOKEN", "")))
            if sys.platform == "win32":
                # ASFW_ANY, its result ignored: KiCad, in the foreground, started this helper, so the window it starts,
                # or the one that window forwards to, may come to the front (design 2 goal 1)
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            command = gui_command(handoff)
            try:
                start_gui(command, handoff.parent)
            except OSError as e:
                raise KrsError("E_GUI_START", program=command[0], reason=reason(e, "T_CANNOT_START")) from None
        return 0
    except Exception as e:
        line = str(e) if isinstance(e, KrsError) else render("E_INTERNAL", detail=detail(e))
        print(line, file=sys.stderr)
        # ponytail: button.log only grows, one line per failed press; a size cap if it ever matters
        with contextlib.suppress(OSError):
            runs.data_dir().mkdir(parents=True, exist_ok=True)
            with open(runs.data_dir() / "button.log", "a", encoding="utf-8") as log:
                log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
        return 1


IDENTIFIER = "org.kicadrfstudio.app"  # design 7's default; the owner's final one is tied to the account
FOLDER = "kicad-rf-studio"  # the plugin's folder in KiCad's plugins folder, ours by name
VERSIONS = ("9.0", "10.0")  # KiCad's major.minor folders
SIZES = (24, 48)  # the icons' sizes, in px
ICONS = {"light": (0x33, 0x33, 0x33), "dark": (0xDD, 0xDD, 0xDD)}  # the glyph's colour by theme
KICAD = "KiCad" if sys.platform == "win32" else "kicad"  # KiCad's own folder in its documents base (paths.cpp)


def documents() -> Path:
    """KiCad's documents base, as its getUserDocumentPath reads it: KICAD_DOCUMENTS_HOME when set; else on Windows the
    shell's Documents folder (CSIDL_PERSONAL, which follows a OneDrive redirect), elsewhere XDG_DATA_HOME, else
    ~/.local/share. Raises OSError when the shell names no Documents folder."""
    if home := os.environ.get("KICAD_DOCUMENTS_HOME"):
        return Path(home)
    if sys.platform == "win32":
        buffer = ctypes.create_unicode_buffer(260)
        if result := ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer):  # an HRESULT, S_OK = 0
            raise ctypes.WinError(result)
        return Path(buffer.value)
    return Path(os.environ.get("XDG_DATA_HOME") or "~/.local/share").expanduser()


def plugin_folders(version: str | None) -> list[Path]:
    """The plugin's folder in KiCad's `version` folder, or in each of VERSIONS whose folder exists (KiCad makes it at
    its first start)."""
    home = documents() / KICAD
    versions = [version] if version else [v for v in VERSIONS if (home / v).is_dir()]
    return [home / v / "plugins" / FOLDER for v in versions]


def plugin_json(entrypoint: str) -> dict:
    """The exec plugin's plugin.json (design 5.5): one action, a PCB editor toolbar button that runs `entrypoint`, the
    launcher beside it, with the icons install writes."""
    icons = {f"icons-{theme}": [f"icon-{theme}-{size}.png" for size in SIZES] for theme in ICONS}
    return {"$schema": "https://go.kicad.org/api/schemas/v1", "identifier": IDENTIFIER, "name": render("G_APP"),
            "description": render("G_BUTTON_PLUGIN"), "runtime": {"type": "exec"},
            "actions": [{"identifier": "open", "name": render("G_APP"), "description": render("G_BUTTON_ACTION"),
                         "show-button": True, "scopes": ["pcb"], "entrypoint": entrypoint, **icons}]}


def launcher(python: str, windows: bool) -> str:
    """The launcher's text, launch.cmd's (`windows`) or launch.sh's, with \\n line ends: it runs the helper on
    `python`, quoted for its shell, with KiCad's arguments, and ends with the helper's exit code."""
    if windows:  # a batch file expands % even inside quotes, and a registry-set DelayedExpansion would eat a !
        return ('@echo off\nsetlocal DisableDelayedExpansion\n"' + python.replace("%", "%%")
                + '" -X utf8 -I -m kicad_rf_studio.button %*\n')
    return "#!/bin/sh\nexec '" + python.replace("'", "'\\''") + "' -X utf8 -I -m kicad_rf_studio.button \"$@\"\n"


def _png(size: int, rgb: tuple[int, int, int]) -> bytes:
    """The button's icon as an RGBA PNG, `size` px square: a ring and its horizontal diameter (a Smith chart's
    outline) in opaque `rgb` on a transparent ground."""
    c, r, half = (size - 1) / 2, 0.42 * size, size / 24  # the centre, the radius and half the stroke, size / 12
    ink, ground = bytes((*rgb, 255)), bytes(4)
    rows = b"".join(b"\0" + b"".join(  # each row: its filter type, 0 (none), then its pixels
        ink if abs(math.hypot(x - c, y - c) - r) <= half or (abs(y - c) <= half and abs(x - c) <= r) else ground
        for x in range(size)) for y in range(size))
    chunks = ((b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)),  # 8-bit RGBA, not interlaced
              (b"IDAT", zlib.compress(rows)), (b"IEND", b""))
    return b"\x89PNG\r\n\x1a\n" + b"".join(
        struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data)) for kind, data in chunks)


def install(version: str | None = None, remove: bool = False) -> list[tuple[str, dict]]:
    """install-kicad-plugin (design 5.5 Install, A-17): writes the exec plugin (plugin.json, the launcher, which runs
    the helper on this environment's Python, and the icons) into each of plugin_folders(version), made with their
    parents; with `remove`, deletes each of them that exists, and nothing else. Never touches KiCad's settings.
    Returns the notes the CLI prints. Raises E_NO_KICAD_FOLDER, E_PLUGIN_PYTHON and E_PLUGIN_WRITE."""
    # ponytail: KiCad's 9.0 and 10.0 folders only; a KiCad 10.1 makes a 10.1 folder, which VERSIONS then needs.
    # --remove leaves the version and plugins folders, which KiCad makes anyway
    folders = plugin_folders(version)
    if remove:
        notes = []
        for folder in [f for f in folders if f.exists()]:
            try:
                shutil.rmtree(folder)
            except OSError as e:
                raise KrsError("E_PLUGIN_WRITE", path=str(folder), reason=reason(e, "T_CANNOT_WRITE")) from None
            notes.append(("I_PLUGIN_REMOVED", {"folder": str(folder)}))
        return notes or [("I_PLUGIN_NONE", {"folder": str(documents() / KICAD)})]
    if not folders:
        raise KrsError("E_NO_KICAD_FOLDER", folder=str(documents() / KICAD))
    windows = sys.platform == "win32"
    entry = "launch.cmd" if windows else "launch.sh"
    python = os.path.abspath(sys.executable)  # never resolved: a Linux venv's python is a symlink out of the venv
    text = launcher(python, windows)
    # ponytail: a Python path outside the console's code page is refused; its 8.3 short path (GetShortPathNameW) if
    # users meet it
    try:  # launch.cmd in the OEM code page, which cmd.exe reads a batch file in; made before anything is written
        script = text.replace("\n", "\r\n").encode("oem") if windows else text.encode("utf-8")
    except UnicodeEncodeError:
        raise KrsError("E_PLUGIN_PYTHON", python=python) from None
    files = {"plugin.json": (json.dumps(plugin_json(entry), indent=2) + "\n").encode("utf-8"), entry: script,
             **{f"icon-{theme}-{size}.png": _png(size, rgb) for theme, rgb in ICONS.items() for size in SIZES}}
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                (folder / name).write_bytes(data)
            if not windows:
                (folder / entry).chmod(0o755)
        except OSError as e:
            raise KrsError("E_PLUGIN_WRITE", path=str(folder), reason=reason(e, "T_CANNOT_WRITE")) from None
    return [("I_PLUGIN_INSTALLED", {"folder": str(folder)}) for folder in folders] + [("I_PLUGIN_NEXT", {})]


if __name__ == "__main__":
    sys.exit(main())
