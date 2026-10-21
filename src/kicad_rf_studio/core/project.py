# SPDX-License-Identifier: GPL-3.0-or-later
"""project.json, schema 1: the project and the job spec in one file. Its board path is relative to the project file
and has forward slashes, so a project folder and its board can move together.

Coordinates in it are in KiCad's frame: mm, with y pointing down, as KiCad shows them and as a user types them in. The
board as read (core.kicad) has y up, so a point [x, y] here is (x, -y) there, and the other way round.

`region` and `mesh` are optional, so schema 1 still reads a file written without them: region_expand_h and mesh_n
give their defaults."""
import hashlib
import json
from pathlib import Path

from kicad_rf_studio.core.messages import KrsError, reason

SCHEMA = 1
EXPAND_H = 3.0  # substrate heights the ROI grows by past the chain (spec 5.1)
MESH_N = {"draft": 2, "normal": 2, "strict": 3}  # the mesh rule's n by preset (spec 5.4, plan 2 Decisions)


def region_expand_h(data: dict) -> float:
    """project.json's region.expand_h, else EXPAND_H."""
    return data.get("region", {}).get("expand_h", EXPAND_H)


def mesh_n(data: dict) -> int:
    """project.json's mesh.n, else its preset's (MESH_N)."""
    return data.get("mesh", {}).get("n") or MESH_N[data["preset"]]


def board_hash(path: str | Path) -> str:
    """The SHA-256 of the file's bytes, in hex."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_project(path: Path, data: dict) -> None:
    """Writes UTF-8 JSON, indented by 2 and with its non-ASCII text as it is. Lines end in "\\n" on every platform."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def load_project(path: Path) -> dict:
    """The project as stored. Raises KrsError: E_PROJECT_UNREADABLE for a path that is not a file, or a file that is
    not UTF-8 JSON (a hand edit can break it); E_PROJECT_SCHEMA for a file that is not of this schema."""
    try:
        if not path.is_file():  # Windows reads a folder as PermissionError, so look before reading (as load_board)
            raise IsADirectoryError() if path.exists() else FileNotFoundError()
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig: an editor may have put a byte order mark in
    except (OSError, ValueError) as e:  # ValueError: UnicodeError or json.JSONDecodeError
        raise KrsError("E_PROJECT_UNREADABLE", path=str(path), reason=reason(e)) from None
    found = data.get("schema") if isinstance(data, dict) else None
    if found != SCHEMA:
        raise KrsError("E_PROJECT_SCHEMA", path=str(path), found=found, expected=SCHEMA)
    return data


def board_file(path: Path, data: dict) -> Path:
    """The board file of the project at `path`. Its stored path is relative to the project file, not to the working
    directory; `load_project` leaves it as stored, so that a saved project keeps a relative path."""
    return (path.parent / data["board"]["path"]).resolve()
