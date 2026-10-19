# SPDX-License-Identifier: GPL-3.0-or-later
"""Local privacy gate for the git hooks in .githooks. Standard library only.

Refuses to commit or push an entry of the private list (the file named by $KRS_PRIVATE_LIST) found
anywhere, or an absolute drive path, home path, UNC share or e-mail address found in a file's
contents. A hit is printed as <where>:<line>: <rule>. The matched text, and any file, ref or
archive-member name that matched, is never printed.
"""
import argparse
import io
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

GENERIC = {
    "drive": r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]",
    "home": r"/(?:home|Users)/[^/\s]+/",
    "unc": r"\\\\[A-Za-z0-9_.$-]+\\",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
}
ARCHIVES = (".npz", ".zip")


def scan_text(text: str, deny: list[str], generic: bool = True) -> list[tuple[int, str]]:
    """Return one (line, rule) per hit, lines counted from 1. The matched text is never returned."""
    folded = [d.casefold() for d in deny]
    hits = []
    for n, line in enumerate(text.split("\n"), 1):
        low = line.casefold()
        hits += [(n, f"deny#{i}") for i, d in enumerate(folded, 1) if d in low]
        if generic:
            # ponytail: the e-mail regex is quadratic on a huge run of word characters. The "@" test
            # spares base64 and hex lines; a huge run right before an "@" is still slow, cap it if that appears.
            hits += [(n, f"generic:{name}") for name, rx in GENERIC.items()
                     if (name != "email" or "@" in line) and re.search(rx, line)]
    return hits


def git(*args: str, raw: bool = False) -> str | bytes:
    # ponytail: one git process per call and per blob; batch with `cat-file --batch` if --all gets slow
    done = subprocess.run(["git", *args], capture_output=True)
    if done.returncode:
        sys.exit(f"privacy_gate: git {args[0]} failed: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout if raw else done.stdout.decode("utf-8", "replace")


def _read_list() -> list[str]:
    """Entries of the private list; [] when it is unset, unreadable, not UTF-8 or has no entries."""
    try:
        lines = Path(os.environ["KRS_PRIVATE_LIST"]).read_text("utf-8-sig").splitlines()
    except (KeyError, OSError, UnicodeError):
        return []
    return [s for s in map(str.strip, lines) if s and not s.startswith("#")]


def _read_allow(root: Path) -> set[str]:
    """Paths listed as `path:<repo-relative path>` in the working tree's tools/privacy_allow.txt."""
    try:
        lines = (root / "tools" / "privacy_allow.txt").read_text("utf-8-sig", errors="replace").splitlines()
    except OSError:
        return set()
    return {line[5:].strip() for line in lines if line.startswith("path:")}


def _check(where: str, text: str, deny: list[str], generic: bool) -> list[str]:
    return [f"{where}:{n}: {rule}" for n, rule in scan_text(text, deny, generic)]


def _scan_file(where: str, path: str, data: bytes, deny: list[str], generic: bool) -> list[str]:
    """Archives are checked by member name, other binaries are skipped, the rest is UTF-8 text."""
    if path.lower().endswith(ARCHIVES):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return _check(where, "\n".join(z.namelist()), deny, generic)
        except zipfile.BadZipFile:
            pass  # named like an archive but is not one: treat it like any other file
    if b"\0" in data[:8192]:
        return []
    return _check(where, data.decode("utf-8", "replace"), deny, generic)


def _scan_files(prefix: str, files: list[tuple[str, str]], deny: list[str], allow: set[str],
                seen: set) -> list[str]:
    """Check names and contents. `files` holds (ref, path) pairs, where `git show <ref>` prints the
    blob. A name that matches is reported as path#<n> at line 0 instead of being printed."""
    out = []
    for k, (ref, path) in enumerate(files, 1):
        name = scan_text(path, deny, generic=False)
        where = prefix + (f"path#{k}" if name else path)
        out += [f"{where}:0: {rule}" for _, rule in name]
        generic = path not in allow
        key = (ref, generic, path.lower().endswith(ARCHIVES))
        if key not in seen:  # every blob once
            seen.add(key)
            out += _scan_file(where, path, git("show", ref, raw=True), deny, generic)
    return out


def _scan_commit(sha: str, deny: list[str], allow: set[str], seen: set) -> list[str]:
    prefix = sha[:8] + ":"
    out = _check(prefix + "commit", git("cat-file", "commit", sha), deny, False)
    files = []
    for entry in filter(None, git("ls-tree", "-r", "-z", "--full-tree", sha).split("\0")):
        meta, path = entry.split("\t", 1)
        _, kind, blob = meta.split()
        if kind == "blob":  # not a submodule
            files.append((blob, path))
    return out + _scan_files(prefix, files, deny, allow, seen)


def _pushed(stdin_text: str) -> tuple[list[str], list[str]]:
    """Commits and ref names of the updates git feeds the pre-push hook on stdin."""
    commits, refs = [], []
    for line in filter(str.strip, stdin_text.splitlines()):
        local_ref, local, remote_ref, remote = line.split()
        if set(local) == {"0"}:  # a deletion pushes no commit
            continue
        refs += [local_ref, remote_ref]
        if set(remote) == {"0"}:  # a new remote ref: everything no remote-tracking ref has yet
            span = ["rev-list", local, "--not", "--remotes"]
        else:
            span = ["rev-list", f"{remote}..{local}"]
        commits += git(*span).split()
    return list(dict.fromkeys(commits)), refs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="privacy_gate", description="Local privacy gate.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="scan the index (pre-commit)")
    mode.add_argument("--pre-push", nargs=2, metavar=("REMOTE", "URL"),
                      help="scan the commits being pushed; git sends the ref updates on stdin")
    mode.add_argument("--all", action="store_true", help="scan the whole history")
    ap.add_argument("--generic-only", action="store_true", help="skip the private list (CI)")
    args = ap.parse_args(argv)

    deny = [] if args.generic_only else _read_list()
    if not (deny or args.generic_only):
        print("privacy_gate: private list missing, empty or not UTF-8; point KRS_PRIVATE_LIST at it",
              file=sys.stderr)
        return 2
    allow = _read_allow(Path(git("rev-parse", "--show-toplevel").strip()))
    seen = set()
    if args.staged:
        names = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split("\0")
        out = _scan_files("", [(":" + n, n) for n in names if n], deny, allow, seen)
    else:
        if args.all:
            commits = git("rev-list", "--all").split()
            refs = git("for-each-ref", "--format=%(refname)").split()
        else:
            commits, refs = _pushed(sys.stdin.read())
        out = _check("refs", "\n".join(refs), deny, False)
        for sha in commits:
            out += _scan_commit(sha, deny, allow, seen)
    if out:
        print("\n".join(out))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
