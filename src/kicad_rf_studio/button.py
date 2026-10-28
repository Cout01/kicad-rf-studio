# SPDX-License-Identifier: GPL-3.0-or-later
"""The KiCad toolbar button (Stage 2 design 5.5): the helper KiCad's exec action runs (main), which reads the board and
the selection through kicad-python and hands them to the GUI. Qt-free; kicad-python is imported only inside the
functions that call KiCad, so importing this module loads none."""
import contextlib
import ctypes
import os
import subprocess
import sys
import sysconfig
import time
import warnings
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
        raise KrsError("E_HANDOFF_WRITE", path=str(path), reason=reason(e, "cannot be written")) from None
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
                raise KrsError("E_GUI_START", program=command[0], reason=reason(e, "cannot be started")) from None
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


if __name__ == "__main__":
    sys.exit(main())
