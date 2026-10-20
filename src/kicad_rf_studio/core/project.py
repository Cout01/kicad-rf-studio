# SPDX-License-Identifier: GPL-3.0-or-later
"""project.json, schema 1: the project and the job spec in one file. Its board path is relative to the project file
and has forward slashes, so a project folder and its board can move together.

Coordinates in it are in KiCad's frame: mm, with y pointing down, as KiCad shows them and as a user types them in. The
board as read (core.kicad) has y up, so a point [x, y] here is (x, -y) there, and the other way round."""
import hashlib
import json
from pathlib import Path

from kicad_rf_studio.core.messages import KrsError

SCHEMA = 1


def board_hash(path: str | Path) -> str:
    """The SHA-256 of the file's bytes, in hex."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_project(path: Path, data: dict) -> None:
    """Writes UTF-8 JSON, indented by 2 and with its non-ASCII text as it is. Lines end in "\\n" on every platform."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def load_project(path: Path) -> dict:
    """The project as stored. Raises KrsError E_PROJECT_SCHEMA for a file that is not of this schema."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig: an editor may have put a byte order mark in
    found = data.get("schema") if isinstance(data, dict) else None
    if found != SCHEMA:
        raise KrsError("E_PROJECT_SCHEMA", path=str(path), found=found, expected=SCHEMA)
    return data


def board_file(path: Path, data: dict) -> Path:
    """The board file of the project at `path`. Its stored path is relative to the project file, not to the working
    directory; `load_project` leaves it as stored, so that a saved project keeps a relative path."""
    return (path.parent / data["board"]["path"]).resolve()
