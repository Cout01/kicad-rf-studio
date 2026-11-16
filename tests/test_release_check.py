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


def test_the_isolated_environment_moves_the_apps_and_kicads_folders_and_drops_the_token_and_pythonpath(
        tmp_path, monkeypatch):  # release 1: the plugin step's console scripts run without -I
    for name in ("KICAD_API_TOKEN", "PYTHONPATH", "PYTHONHOME"):
        monkeypatch.setenv(name, "src")
    env = release_check.isolated(tmp_path)
    assert [name for name in ("KICAD_API_TOKEN", "PYTHONPATH", "PYTHONHOME") if name in env] == []
    paths = (env["LOCALAPPDATA"], env["KICAD_DOCUMENTS_HOME"], env["KICAD_API_SOCKET"].removeprefix("ipc://"))
    assert all(Path(p).is_relative_to(tmp_path) for p in paths)


def test_install_fails_a_venv_without_either_entry_point(tmp_path, monkeypatch):  # release 4
    monkeypatch.setattr(release_check, "run", lambda command, **kw: subprocess.CompletedProcess(command, 0, "", ""))
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "x-0-py3-none-any.whl").touch()
    gui, cli = (Path(release_check.program(tmp_path, name)) for name in ("kicad-rf-studio-gui", "kicad-rf-studio"))
    gui.parent.mkdir(parents=True)
    gui.touch()
    assert release_check.install(tmp_path) == (
        "FAIL", "the fresh venv lacks kicad-rf-studio: the wheel lacks its entry points")
    cli.touch()
    assert release_check.install(tmp_path)[0] == "PASS"


def test_the_antenna_step_runs_new_on_the_releases_own_fixture_and_reads_schema_2(tmp_path, monkeypatch):
    fixture = ROOT / "tests" / "fixtures" / "ifa2g4_pi.kicad_pcb"  # Stage 3 design 5.12 item 5; r3
    with zipfile.ZipFile(tmp_path / "source.zip", "w") as z:
        z.write(fixture, "tests/fixtures/ifa2g4_pi.kicad_pcb")
    seen, schema = [], {"schema": 2, "kind": "antenna"}

    def run(command, **kw):  # the fresh venv's new: it writes project.json where -o says
        seen.append((command, kw["env"]))
        out = Path(command[command.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "project.json").write_text(json.dumps(schema), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release_check, "run", run)
    assert release_check.antenna(tmp_path)[0] == "PASS"
    (command, env), = seen
    assert command[:2] == [release_check.program(tmp_path, "kicad-rf-studio"), "new"]
    assert command[3:9] == ["--start", "U1.1", "--antenna", "AE1", "--band", "2400MHz:2483.5MHz"]
    assert Path(command[2]).read_bytes() == fixture.read_bytes() and env["QT_QPA_PLATFORM"] == "offscreen"
    schema = {"schema": 1}
    assert release_check.antenna(tmp_path)[0] == "FAIL"  # no kind: read with .get, a FAIL line
    assert [s.__name__ for s in release_check.STEPS] == ["build", "install", "gui", "antenna", "si", "review",
                                                         "plugin", "privacy"]
    assert release_check.NEEDS["antenna"] == "install"


def test_the_si_step_runs_new_interface_on_the_releases_own_fixture_and_reads_schema_3(tmp_path, monkeypatch):
    fixture = ROOT / "tests" / "fixtures" / "usb2_hs.kicad_pcb"  # Stage 4 design 5.12 item 5; ruling 12
    with zipfile.ZipFile(tmp_path / "source.zip", "w") as z:
        z.write(fixture, "tests/fixtures/usb2_hs.kicad_pcb")
    line = {"chain": {"series": [{"role": "port"}], "shunt": []}}  # R1, then R2: a part port each
    seen, data = [], {"schema": 3, "kind": "si", "ports": [{}] * 6, "lines": [line, line]}

    def run(command, **kw):  # the fresh venv's new: it writes project.json where -o says
        seen.append((command, kw["env"]))
        out = Path(command[command.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "project.json").write_text(json.dumps(data), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release_check, "run", run)
    assert release_check.si(tmp_path)[0] == "PASS"
    (command, env), = seen
    assert command[:2] == [release_check.program(tmp_path, "kicad-rf-studio"), "new"]
    assert command[3:12] == ["--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--pair", "--victim",
                             "TP1.1:TP2.1"]
    assert Path(command[2]).read_bytes() == fixture.read_bytes() and env["QT_QPA_PLATFORM"] == "offscreen"
    data = {**data, "ports": [{}] * 5}
    assert release_check.si(tmp_path)[0] == "FAIL"  # 7 ports where a run takes 8
    assert release_check.NEEDS["si"] == "install"


def test_the_review_step_runs_review_on_the_releases_fixture_and_names_what_differs(tmp_path, monkeypatch):  # 5.17
    fixture, golden = ROOT / "tests" / "fixtures" / "emc_review.kicad_pcb", ROOT / "tests/fixtures/review/emc_review.json"
    lf = fixture.read_bytes().replace(b"\r\n", b"\n")
    with zipfile.ZipFile(tmp_path / "source.zip", "w") as z:  # git archive on a core.autocrlf checkout: CRLF
        z.writestr("tests/fixtures/emc_review.kicad_pcb", lf.replace(b"\n", b"\r\n"))
        z.write(golden, "tests/fixtures/review/emc_review.json")
    seen, data = [], json.loads(golden.read_text(encoding="utf-8"))

    def run(command, **kw):  # the fresh venv's review: it writes review.json where -o says
        seen.append((command, kw, (Path(kw["cwd"]) / command[2]).read_bytes()))
        out = Path(command[command.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "review.json").write_text(json.dumps(data), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release_check, "run", run)
    assert release_check.review(tmp_path)[0] == "PASS"
    (command, kw, board), = seen
    assert command[:3] == [release_check.program(tmp_path, "kicad-rf-studio"), "review", "emc_review.kicad_pcb"]
    assert board == lf  # LF, as the golden's sha256 hashes it (golden_antenna._board)
    assert kw["env"]["QT_QPA_PLATFORM"] == "offscreen"
    data = {**data, "cavities": []}
    assert release_check.review(tmp_path) == ("FAIL", "…/review/review.json differs from "
                                              "tests/fixtures/review/emc_review.json in: cavities")
    assert release_check.NEEDS["review"] == "install"


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
