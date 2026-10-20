# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib

import pytest

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import SCHEMA, board_file, board_hash, load_project, save_project


def test_schema_mismatch(tmp_path):
    p = tmp_path / "project.json"; p.write_text('{"schema": 99}', encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_project(p)
    assert e.value.code == "E_PROJECT_SCHEMA"


# --- beyond the brief's test: what the error says, and the rest of the file interface -------------------


def test_schema_mismatch_names_the_file_and_both_versions(tmp_path):
    p = tmp_path / "project.json"; p.write_text('{"schema": 99}', encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_project(p)
    assert e.value.params == {"path": str(p), "found": 99, "expected": SCHEMA}
    assert "schema 99" in str(e.value) and "schema 1" in str(e.value)


@pytest.mark.parametrize("text", ["{}", '{"board": {}}', "[]", "null", "7"])
def test_a_file_with_no_schema_is_refused(tmp_path, text):
    p = tmp_path / "project.json"; p.write_text(text, encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_project(p)
    assert e.value.code == "E_PROJECT_SCHEMA" and e.value.params["found"] is None


def test_board_hash_is_the_sha256_of_the_bytes(tmp_path):
    p = tmp_path / "board.kicad_pcb"; p.write_bytes(b"abc")
    assert board_hash(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"  # FIPS 180-2 test vector
    raw = b"(kicad_pcb)\r\n\xff\x00 \xc3\xa7\r\n"  # CRLF, a byte that is not UTF-8, a NUL: bytes, not decoded text
    p.write_bytes(raw)
    assert board_hash(p) == hashlib.sha256(raw).hexdigest()


def test_save_then_load_keeps_the_data_and_the_non_ascii_text(tmp_path):
    data = {"schema": SCHEMA, "note": "ação — Ω", "values": [1.5, None, True]}
    p = tmp_path / "project.json"
    save_project(p, data)
    assert load_project(p) == data
    raw = p.read_bytes()
    assert "ação — Ω".encode("utf-8") in raw  # ensure_ascii=False: the text itself, not \u escapes
    assert raw.startswith(b'{\n  "schema": 1,\n  "note"')  # indent=2
    assert b"\r" not in raw  # the same bytes on every platform


def test_load_accepts_a_byte_order_mark(tmp_path):
    p = tmp_path / "project.json"; p.write_bytes(b'\xef\xbb\xbf{"schema": 1}')  # what an older Notepad writes
    assert load_project(p) == {"schema": 1}


def test_board_file_follows_the_project_file_not_the_working_directory(tmp_path, monkeypatch):
    (tmp_path / "boards").mkdir()
    board = tmp_path / "boards" / "x.kicad_pcb"; board.write_text("x", encoding="utf-8")
    project = tmp_path / "proj" / "project.json"
    monkeypatch.chdir(tmp_path)  # neither the project's folder nor the board's
    assert board_file(project, {"board": {"path": "../boards/x.kicad_pcb"}}) == board.resolve()
    assert board_file(project, {"board": {"path": board.as_posix()}}) == board.resolve()  # an absolute path stays
