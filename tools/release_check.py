# SPDX-License-Identifier: GPL-3.0-or-later
"""The release check (Stage 2 design 5.6): run by hand before a release, from the repo root
(`python tools/release_check.py`, with the dev venv's Python, which has jsonschema), and by
.github/workflows/release-check.yml on a version tag or by hand. Seven steps, each printing one PASS, FAIL or SKIPPED
line: build (a wheel from git archive of HEAD, the tree a release's source zip holds, inspected), install (a fresh
venv: the wheel, pip check, kicad-python's import and both entry points), gui (the main window built, shown offscreen
and closed, in that venv), antenna (`new --antenna` in that venv on the release's own antenna fixture, its project.json
of schema 2), si (`new --interface` in that venv on the release's own USB 2.0 fixture, its project.json of schema 3
with 8 ports), plugin (install-kicad-plugin in that venv, its plugin.json checked against KiCad's schemas at SCHEMA_TAGS
and the identifier rules) and privacy (the privacy gate's generic rules over the history and the wheel; the private
list stays the hooks'). Every file it makes is under one temporary folder, removed at the end and named with a space
and an accent, but for pip's own cache and build folders; a folder it cannot remove is named on a last line. Every
process of the gui, antenna, si and plugin steps gets that folder for its data, caches and KiCad folders. Exits 1 when
a step fails. The standard library only, but for jsonschema, which kicad-python brings, imported by the plugin step.
Its lines are plain English: a release tool's output, like privacy_gate's, not the app's.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import privacy_gate

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = sys.platform == "win32"
# ponytail: KiCad's floor and the newest 10.0 release, fetched at run time; their schemas are identical (probed with
# 9.0.9.1 and 10.0.8-rc1). An offline or rate-limited run fails the plugin step: vendor both files then, with a NOTICE
# entry. Add a tag when KiCad ships a newer schema
SCHEMA_TAGS = ("9.0.7", "10.0.7")
SCHEMA_URL = "https://gitlab.com/kicad/code/kicad/-/raw/{tag}/api/schemas/api.v1.schema.json"
IDENTIFIER_RULES = (
    ("KiCad 9.0.7", re.search, r"[\w\d]{2,}\.[\w\d]+\.[\w\d]+"),  # its IsValidIdentifier, unanchored
    ("KiCad 10.0.7", re.fullmatch, r"[a-zA-Z]{2,}(\.([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]|[a-zA-Z0-9])){2,}"),
    ("design 5.5", re.fullmatch, r"[A-Za-z]+(\.[A-Za-z0-9]+){2,}"))
# ponytail: exact: a setuptools that writes another dist-info file fails the build step until it is named here
DIST_INFO = ("METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt", "licenses/LICENSE",
             "licenses/COPYING.LESSER", "licenses/NOTICE")
# ponytail: gui.main, the gui-scripts entry's own function: its .exe launcher cannot be told to close, so only a
# launcher replay (design 5.11 item 3) starts the .exe itself
SMOKE = ("import sys; from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication; "
         "from kicad_rf_studio import gui; app = QApplication(sys.argv[:1]); QTimer.singleShot(0, lambda: "
         "[w.close() for w in app.topLevelWidgets() if type(w).__name__ == 'MainWindow' and w.isVisible()] "
         "or app.exit(3)); sys.exit(gui.main([]))")


def inspect_wheel(wheel: Path, sources: list[str]) -> list[str]:
    """[] when `wheel` holds exactly the package (`sources`, HEAD's tracked paths under src/, without src/) and the
    DIST_INFO files of its <name>-<version>.dist-info, read from the wheel's file name; else each member it should
    not hold, sorted, then each one it lacks, sorted."""
    info = "-".join(wheel.name.split("-")[:2]) + ".dist-info/"
    want = {s.removeprefix("src/") for s in sources} | {info + name for name in DIST_INFO}
    with zipfile.ZipFile(wheel) as z:
        have = set(z.namelist())
    return [f"{n}: not the package's" for n in sorted(have - want)] + [f"{n}: missing" for n in sorted(want - have)]


def identifier_problems(identifier: str) -> list[str]:
    """The names of the IDENTIFIER_RULES that `identifier` fails, in their order."""
    return [name for name, match, pattern in IDENTIFIER_RULES if not match(pattern, identifier)]


def plugin_problems(plugin: dict, schemas: dict[str, dict]) -> list[str]:
    """Each error of `plugin` under each KiCad tag's schema in `schemas` (JSON Schema draft 7), sorted by its path
    within a schema, then each identifier rule its identifier fails."""
    from jsonschema import Draft7Validator  # kicad-python's: the one import beyond the standard library
    errors = [f"KiCad {tag}'s schema: {e.message}" for tag, schema in schemas.items()
              for e in sorted(Draft7Validator(schema).iter_errors(plugin), key=lambda e: [str(p) for p in e.path])]
    return errors + [f"identifier {plugin['identifier']!r}: {name}'s rule"
                     for name in identifier_problems(plugin["identifier"])]


def wheel_hits(wheel: Path, allow: set[str]) -> list[str]:
    """The privacy gate's generic rules over each member of `wheel`, as --generic-only reads a blob; off for a member
    whose src/ path `allow` (tools/privacy_allow.txt) lists."""
    with zipfile.ZipFile(wheel) as z:
        return [hit for name in z.namelist()
                for hit in privacy_gate._scan_file(f"wheel:{name}", name, z.read(name), [], "src/" + name not in allow)]


def run(command: list[str], timeout: float = 1800, **kw) -> subprocess.CompletedProcess:
    """`command` run to its end, its output captured as UTF-8 text with errors replaced."""
    return subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)


def failed(command: list[str], done: subprocess.CompletedProcess) -> tuple[str, str]:
    """A FAIL naming `command` (its program's file name and its next three arguments), its exit code and the last
    line of its stderr, else of its stdout."""
    lines = (done.stderr.strip() or done.stdout.strip()).splitlines()
    return "FAIL", f"{' '.join([Path(command[0]).name, *command[1:4]])}: exit code {done.returncode}: " + (
        lines[-1] if lines else "")


def program(tmp: Path, name: str) -> str:
    """The fresh venv's program `name`."""
    return str(tmp / "venv" / ("Scripts" if WINDOWS else "bin") / (name + (".exe" if WINDOWS else "")))


def isolated(tmp: Path) -> dict:
    """This environment for the fresh venv's app: its data, caches and settings, and KiCad's documents and settings
    folders under `tmp`, a KiCad API socket nobody listens on, no KiCad token, no PYTHONPATH or PYTHONHOME (the console
    scripts run without -I, so these would put other code before the wheel's), and Qt offscreen."""
    home, dropped = str(tmp / "home"), ("KICAD_API_TOKEN", "PYTHONPATH", "PYTHONHOME")
    names = ("LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "MPLCONFIGDIR")
    return {**{k: v for k, v in os.environ.items() if k not in dropped}, **dict.fromkeys(names, home),
            "KICAD_DOCUMENTS_HOME": str(tmp / "documents"), "KICAD_CONFIG_HOME": str(tmp / "config"),
            "KICAD_API_SOCKET": f"ipc://{tmp / 'no-kicad.sock'}", "QT_QPA_PLATFORM": "offscreen"}


def build(tmp: Path) -> tuple[str, str]:
    """(a) A wheel that pip wheel --no-deps builds from git archive of HEAD, the tree a release's source zip holds,
    into tmp/dist, inspected."""
    head = run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    for command in (["git", "archive", "--format=zip", "-o", str(tmp / "source.zip"), head],
                    [sys.executable, "-m", "pip", "wheel", "--no-deps", "--quiet", "--disable-pip-version-check",
                     "--wheel-dir", str(tmp / "dist"), str(tmp / "source.zip")]):
        if (done := run(command, cwd=ROOT)).returncode:
            return failed(command, done)
    wheel = next((tmp / "dist").glob("*.whl"))
    sources = run(["git", "ls-tree", "-r", "-z", "--name-only", head, "src"], cwd=ROOT).stdout.split("\0")
    if problems := inspect_wheel(wheel, [s for s in sources if s]):
        return "FAIL", "\n  ".join([wheel.name, *problems])
    return "PASS", f"{wheel.name}, from git archive of {head[:8]}: the package, its data and its dist-info, nothing else"


def install(tmp: Path) -> tuple[str, str]:
    """(b) A fresh venv, the wheel installed, pip check, then kicad-python's protos imported (pip check passes on a
    protobuf of 5.29.0 to 5.29.5, which they refuse: plan 3) and both entry points there (the plugin step runs the
    console script). pip keeps its own cache."""
    wheel, python = next((tmp / "dist").glob("*.whl")), program(tmp, "python")
    for command in ([sys.executable, "-m", "venv", str(tmp / "venv")],
                    [python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", str(wheel)],
                    [python, "-m", "pip", "check", "--disable-pip-version-check"],
                    [python, "-I", "-c", "import kipy.board_types"]):
        if (done := run(command)).returncode:
            return failed(command, done)
    if missing := [n for n in ("kicad-rf-studio", "kicad-rf-studio-gui") if not Path(program(tmp, n)).exists()]:
        return "FAIL", f"the fresh venv lacks {' and '.join(missing)}: the wheel lacks its entry points"
    return "PASS", (f"{wheel.name} installs in a fresh venv with both entry points, pip check finds nothing broken, "
                    "kicad-python's protos import")


def gui(tmp: Path) -> tuple[str, str]:
    """(c) The GUI entry's own function in the fresh venv, offscreen and isolated (SMOKE)."""
    command = [program(tmp, "python"), "-I", "-c", SMOKE]
    if (done := run(command, timeout=300, env=isolated(tmp))).returncode:
        return failed(command, done)
    return "PASS", "the main window was built, shown offscreen and closed, in the fresh venv"


def antenna(tmp: Path) -> tuple[str, str]:
    """(d) `new --antenna` by the fresh venv's console script on the release's own tests/fixtures/ifa2g4_pi.kicad_pcb,
    taken from tmp/source.zip, isolated: its project.json schema 2 and kind antenna, the installed importer and schema
    2 at no cost (no openEMS runs)."""
    with zipfile.ZipFile(tmp / "source.zip") as z:
        board = z.extract("tests/fixtures/ifa2g4_pi.kicad_pcb", tmp / "source")
    command = [program(tmp, "kicad-rf-studio"), "new", board, "--start", "U1.1", "--antenna", "AE1",
               "--band", "2400MHz:2483.5MHz", "-o", str(tmp / "antenna")]
    if (done := run(command, timeout=300, env=isolated(tmp))).returncode:
        return failed(command, done)
    data = json.loads((tmp / "antenna" / "project.json").read_text(encoding="utf-8"))
    schema, kind = data.get("schema"), data.get("kind")
    if (schema, kind) != (2, "antenna"):
        return "FAIL", f"…/antenna/project.json: schema {schema!r}, kind {kind!r}"
    return "PASS", "new wrote an antenna project, schema 2, from tests/fixtures/ifa2g4_pi.kicad_pcb in the fresh venv"


def si(tmp: Path) -> tuple[str, str]:
    """(e) `new --interface` by the fresh venv's console script on the release's own tests/fixtures/usb2_hs.kicad_pcb,
    taken from tmp/source.zip, isolated: its project.json schema 3, kind si and 8 ports, the pair's 4, the victim's 2
    and R1's and R2's: the installed tracer's pair rule and schema 3 at no cost (no openEMS runs)."""
    with zipfile.ZipFile(tmp / "source.zip") as z:
        board = z.extract("tests/fixtures/usb2_hs.kicad_pcb", tmp / "source")
    command = [program(tmp, "kicad-rf-studio"), "new", board, "--start", "J1.3", "--end", "U1.3", "--interface",
               "usb2-hs", "--pair", "--victim", "TP1.1:TP2.1", "-o", str(tmp / "si")]
    if (done := run(command, timeout=300, env=isolated(tmp))).returncode:
        return failed(command, done)
    data = json.loads((tmp / "si" / "project.json").read_text(encoding="utf-8"))
    schema, kind = data.get("schema"), data.get("kind")
    ports = len(data.get("ports", [])) + sum(q.get("role") == "port" for x in data.get("lines", [])
                                             for q in x["chain"]["series"] + x["chain"]["shunt"])
    if (schema, kind, ports) != (3, "si", 8):
        return "FAIL", f"…/si/project.json: schema {schema!r}, kind {kind!r}, {ports} ports"
    return "PASS", "new wrote an SI project, schema 3, 8 ports, from tests/fixtures/usb2_hs.kicad_pcb in the fresh venv"


def plugin(tmp: Path) -> tuple[str, str]:
    """(f) install-kicad-plugin by the fresh venv's console script into tmp's KiCad 10.0 folder (9.0's files are the
    same), checked by kicad-python-packager, against KiCad's schema at each of SCHEMA_TAGS and the identifier rules
    (plugin_problems), and its entrypoint executable, as KiCad checks it at the click."""
    folder = tmp / "documents" / ("KiCad" if WINDOWS else "kicad") / "10.0" / "plugins" / "kicad-rf-studio"
    for command in ([program(tmp, "kicad-rf-studio"), "install-kicad-plugin", "--kicad", "10.0"],
                    [program(tmp, "kicad-python-packager"), "validate", str(folder)]):
        if (done := run(command, timeout=300, env=isolated(tmp))).returncode:
            return failed(command, done)
    data = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    schemas = {tag: json.load(urllib.request.urlopen(SCHEMA_URL.format(tag=tag), timeout=60)) for tag in SCHEMA_TAGS}
    problems = plugin_problems(data, schemas) + [f"{a['entrypoint']}: not executable" for a in data["actions"]
                                                 if not os.access(folder / a["entrypoint"], os.X_OK)]
    if problems:
        return "FAIL", "\n  ".join(problems)
    return "PASS", (f"plugin.json passes kicad-python's validator, KiCad {' and '.join(SCHEMA_TAGS)}'s schemas and "
                    "the identifier rules, and its launcher is executable")


def privacy(tmp: Path) -> tuple[str, str]:
    """(g) The privacy gate's generic rules, as ci.yml runs them: over the history (its script, --all --generic-only)
    and over the wheel's texts (wheel_hits). The private list stays the hooks' (spec 9.1): pre-commit and pre-push run
    it on every commit and push."""
    command = [sys.executable, "-X", "utf8", str(ROOT / "tools" / "privacy_gate.py"), "--all", "--generic-only"]
    done = run(command, cwd=ROOT)
    hits = done.stdout.splitlines()
    if done.returncode != (1 if hits else 0):  # the gate also exits 1, with nothing on stdout, when git fails
        return failed(command, done)
    wheel = next((tmp / "dist").glob("*.whl"), None)
    hits += wheel_hits(wheel, privacy_gate._read_allow(ROOT)) if wheel else []
    scanned = f"the history and {wheel.name}" if wheel else "the history (no wheel)"
    if hits:
        return "FAIL", "\n  ".join([f"{scanned}, under the generic rules:", *hits])
    return "PASS", f"{scanned}: clean under the generic rules (the private list is the hooks')"


NEEDS = {"install": "build", "gui": "install", "antenna": "install", "si": "install", "plugin": "install"}
STEPS = (build, install, gui, antenna, si, plugin, privacy)


def main() -> int:
    """Runs STEPS in order in one temporary folder and prints each one's line; a step whose NEEDS did not pass is
    SKIPPED, and a step that raises is its own FAIL. Returns 1 when a step failed, else 0."""
    sys.stdout.reconfigure(errors="replace")
    status = {}
    # ponytail: a file a process still holds (Windows) stays in TEMP, named on the last line; a TEMP longer than about
    # 60 characters overflows Windows' 260-character paths in the venv (PySide6-Essentials' deepest file) unless long
    # paths are enabled, and the failing step names it: run it with a shorter TEMP then
    with tempfile.TemporaryDirectory(prefix="krs release é ", ignore_cleanup_errors=True) as name:
        tmp = Path(name).resolve()  # TEMP may be an 8.3 short path, which venv warns about
        for step in STEPS:
            need = NEEDS.get(step.__name__)
            if need and status[need] != "PASS":
                result = ("SKIPPED", f"{need} did not pass")
            else:
                try:
                    result = step(tmp)
                except Exception as e:  # its own FAIL; the next steps still run
                    result = ("FAIL", f"{type(e).__name__}: {e}")
            status[step.__name__] = result[0]
            print(f"{result[0]} {step.__name__}: {result[1]}", flush=True)
    if Path(name).exists():
        print(f"NOTE: {Path(name).name} is left in TEMP: delete it by hand", flush=True)
    return 1 if "FAIL" in status.values() else 0


if __name__ == "__main__":
    sys.exit(main())
