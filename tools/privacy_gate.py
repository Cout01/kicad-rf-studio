# SPDX-License-Identifier: GPL-3.0-or-later
"""Local privacy gate for the git hooks in .githooks. Standard library only.

Refuses to commit or push when an entry of the private list (the file named by $KRS_PRIVATE_LIST)
appears anywhere: file contents, file names, ref names, commit messages, author fields, annotated
tags (tagger and message) or archive member names. It also refuses an absolute drive path, home
path, UNC share or e-mail address in a file's contents (the generic rules; tools/privacy_allow.txt
can exempt a path from those only).

A hit is printed as <where>:<line>: <rule>, where <where> is <commit>:<path>, <commit>:commit (the
header and message), <tag>:tag (an annotated tag object) or refs, and <rule> is deny#<n> (the n-th
entry of the list) or generic:<kind>.
The matched text is never printed, nor is a name that matched: such a file shows as path#<n> (its
position in the listing) with line 0 standing for the name itself.
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
    """Archives are checked by member name, other binaries are skipped, the rest is text: UTF-16 when it
    starts with a byte order mark, else UTF-8, else cp1252 (what a Windows editor saves), so that an
    accented entry matches. Text that is not UTF-8 is also read as UTF-8 with the bad bytes replaced, so
    that one stray byte does not hide the rest of a UTF-8 file."""
    if path.lower().endswith(ARCHIVES):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return _check(where, "\n".join(z.namelist()), deny, generic)
        except zipfile.BadZipFile:
            pass  # named like an archive but is not one: treat it like any other file
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):  # UTF-16 is full of NULs: read it before the binary test
        return _check(where, data.decode("utf-16", "replace"), deny, generic)
    if b"\0" in data[:8192]:
        return []
    try:
        return _check(where, data.decode("utf-8"), deny, generic)
    except UnicodeDecodeError:
        both = [data.decode("cp1252", "replace"), data.decode("utf-8", "replace")]  # the same lines: "\n" is ASCII
        found = dict.fromkeys(hit for text in both for hit in scan_text(text, deny, generic))  # each hit once
        return [f"{where}:{n}: {rule}" for n, rule in sorted(found, key=lambda hit: hit[0])]


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


def _pushed(stdin_text: str, remote_name: str) -> tuple[list[str], list[str], list[str]]:
    """Commits, ref names and annotated tags of the updates git feeds the pre-push hook on stdin. A
    new remote ref skips only what remote-tracking refs of that remote reach: another remote proves
    nothing here. A pushed tag object is scanned itself; rev-list peels it to its commit."""
    commits, refs, tags = [], [], []
    for line in filter(str.strip, stdin_text.splitlines()):
        local_ref, local, remote_ref, remote = line.split()
        if set(local) == {"0"}:  # a deletion pushes no commit
            continue
        refs += [local_ref, remote_ref]
        if git("cat-file", "-t", local).strip() == "tag":
            tags.append(local)
        if set(remote) == {"0"}:  # a new remote ref
            span = ["rev-list", local, "--not", f"--remotes={remote_name}"]
        else:
            span = ["rev-list", f"{remote}..{local}"]
        commits += git(*span).split()
    return list(dict.fromkeys(commits)), refs, tags


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
            tagged = git("for-each-ref", "--format=%(objecttype) %(objectname)", "refs/tags").splitlines()
            tags = [sha for kind, sha in map(str.split, tagged) if kind == "tag"]  # not a lightweight tag
        else:
            commits, refs, tags = _pushed(sys.stdin.read(), args.pre_push[0])
        out = _check("refs", "\n".join(refs), deny, False)
        for sha in tags:  # the tagger and the message: the private list only, as for a commit's header
            out += _check(sha[:8] + ":tag", git("cat-file", "tag", sha), deny, False)
        for sha in commits:
            out += _scan_commit(sha, deny, allow, seen)
    if out:
        print("\n".join(out))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
