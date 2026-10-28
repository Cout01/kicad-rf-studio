# SPDX-License-Identifier: GPL-3.0-or-later
"""tools/release_check.py (Stage 2 design 5.6): its pure parts, its privacy step and its order of steps, with no
network and no build. The steps that build, install and fetch run in the controller's release check (plan 4, Task 6)."""
import json
import subprocess
import sys
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest

import privacy_gate as gate
import release_check
from kicad_rf_studio import button

ROOT = Path(__file__).resolve().parents[1]
WHEEL = "kicad_rf_studio-0.1.0.dev0-py3-none-any.whl"  # as pip wheel names this repo's
INFO = "kicad_rf_studio-0.1.0.dev0.dist-info"
SOURCES = ["src/kicad_rf_studio/__init__.py", "src/kicad_rf_studio/data/stackups/jlcpcb-2l.json"]


def wheel(path, members=None):
    """A wheel at `path` holding SOURCES' package files and the dist-info files, changed by `members` (None drops one)."""
    content = {s.removeprefix("src/"): b"x\n" for s in SOURCES} | {
        f"{INFO}/{name}": b"x\n" for name in release_check.DIST_INFO} | (members or {})
    with zipfile.ZipFile(path, "w") as z:
        for name, data in content.items():
            if data is not None:
                z.writestr(name, data)
    return path


def test_the_wheel_holds_the_package_its_data_and_its_dist_info_and_nothing_else(tmp_path):  # design 5.6; RF 3
    assert release_check.inspect_wheel(wheel(tmp_path / WHEEL), SOURCES) == []
    bad = wheel(tmp_path / WHEEL, {"tests/conftest.py": b"x\n", "kicad_rf_studio/data/stackups/jlcpcb-2l.json": None,
                                   f"{INFO}/licenses/NOTICE": None})
    assert release_check.inspect_wheel(bad, SOURCES) == [
        "tests/conftest.py: not the package's", f"{INFO}/licenses/NOTICE: missing",
        "kicad_rf_studio/data/stackups/jlcpcb-2l.json: missing"]


@pytest.mark.parametrize(("identifier", "fails"), [
    ("org.kicadrfstudio.app", []),  # design 7's default
    ("io.github.owner.kicadrfstudio", []),  # r1's form for the owner's account
    ("org.kicad_rf.app", ["KiCad 10.0.7", "design 5.5"]),  # 9.0.7's \w takes the underscore
    ("org.kicad-rf.app", ["KiCad 9.0.7", "design 5.5"]),  # 10.0.7 takes the hyphen
    ("a.b.c", ["KiCad 9.0.7", "KiCad 10.0.7"]),  # a one-letter first segment
    ("org.app", ["KiCad 9.0.7", "KiCad 10.0.7", "design 5.5"])])  # two segments
def test_an_identifier_passes_kicad_9s_and_10s_rules_and_the_designs(identifier, fails):  # design 5.5; plan 3
    assert release_check.identifier_problems(identifier) == fails


def test_plugin_json_is_checked_against_each_schema_and_each_identifier_rule():  # design 5.6
    schema = json.loads(files("kipy.packaging.schemas").joinpath("api.v1.schema.json").read_text(encoding="utf-8"))
    plugin = button.plugin_json("launch.cmd")  # kipy's schema: KiCad 10.0.7's with one more scope (plan 3)
    assert release_check.plugin_problems(plugin, {"9.0.7": schema, "10.0.7": schema}) == []
    worse = {**plugin, "identifier": "1org.x.y", "runtime": {"type": "wasm"}}
    assert release_check.plugin_problems(worse, {"9.0.7": schema}) == [
        "KiCad 9.0.7's schema: '1org.x.y' does not match '^[a-zA-Z][-_a-zA-Z0-9.]{0,98}[a-zA-Z0-9]$'",
        "KiCad 9.0.7's schema: 'wasm' is not one of ['python', 'exec']",
        "identifier '1org.x.y': KiCad 10.0.7's rule", "identifier '1org.x.y': design 5.5's rule"]


def test_the_wheels_texts_go_through_the_privacy_gates_generic_rules_its_allow_list_read_as_src_paths(tmp_path):
    mail = "t" + "@" + "t.test"  # built at run time: the gate would flag a literal address in this file
    path = tmp_path / "w.whl"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("kicad_rf_studio/core/mesh/smooth.py", f"# {mail}\n")  # its src/ path is in privacy_allow.txt
        z.writestr("kicad_rf_studio/x.py", f"x = 1\n# {mail}\n")
    assert release_check.wheel_hits(path, gate._read_allow(ROOT)) == [
        "wheel:kicad_rf_studio/x.py:2: generic:email"]  # Review Focus 3


def test_the_privacy_step_passes_only_a_clean_scan_and_fails_when_the_gate_cannot_scan(tmp_path, monkeypatch):
    def gate_run(code, out="", err=""):  # the gate's script exits `code`, printing `out` and `err`
        done = subprocess.CompletedProcess([], code, out, err)
        monkeypatch.setattr(release_check, "run", lambda command, **kw: done)
        return release_check.privacy(tmp_path)  # no wheel in tmp_path: the history only

    assert gate_run(0) == ("PASS", "the history (no wheel): clean under the generic rules (the private list is the "
                                   "hooks')")
    assert gate_run(1, "abcd1234:docs/x.md:1: generic:drive\n") == (
        "FAIL", "the history (no wheel), under the generic rules:\n  abcd1234:docs/x.md:1: generic:drive")
    status, detail = gate_run(1, err="privacy_gate: git rev-list failed: x")  # exit 1 and no hit: it never scanned
    assert status == "FAIL" and detail.endswith(": exit code 1: privacy_gate: git rev-list failed: x")


def test_main_skips_what_a_failed_step_holds_up_fails_a_step_that_raises_and_removes_its_folder(monkeypatch, capsys):
    made = []

    def build(tmp):
        made.append(tmp)
        (tmp / "dist").mkdir()
        return "FAIL", "no wheel"

    def install(tmp):
        raise AssertionError("install needs build")

    def gui(tmp):
        raise AssertionError("gui needs install")

    def plugin(tmp):
        raise AssertionError("plugin needs install")

    def privacy(tmp):
        raise OSError("gone")  # a step that raises is its own FAIL, and the next steps still run

    monkeypatch.setattr(release_check, "STEPS", (build, install, gui, plugin, privacy))
    assert release_check.main() == 1
    assert capsys.readouterr().out.splitlines() == [
        "FAIL build: no wheel", "SKIPPED install: build did not pass", "SKIPPED gui: install did not pass",
        "SKIPPED plugin: install did not pass", "FAIL privacy: OSError: gone"]
    (tmp,) = made
    assert " " in tmp.name and "é" in tmp.name and not tmp.exists()  # Review Focus 1; one folder, removed


def test_the_release_check_loads_only_the_standard_library_until_its_plugin_step():  # the workflow adds jsonschema
    probe = (f"import sys; sys.path.insert(0, {str(ROOT / 'tools')!r}); import release_check; print(sorted("
             "{m.split('.')[0] for m in sys.modules} & {'kicad_rf_studio', 'jsonschema', 'kipy', 'PySide6', 'numpy'}))")
    out = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr
