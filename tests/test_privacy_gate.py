# SPDX-License-Identifier: GPL-3.0-or-later
import io
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import privacy_gate as gate  # noqa: E402

# Dummy identity, built at runtime: the gate would flag a literal address in this file.
IDENT = ["-c", "user.name=t", "-c", "user.email=t" + "@" + "t.test", "-c", "commit.gpgsign=false"]
NEVER = "0" * 40


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout.decode().strip()


def private_list(factory, content):
    path = factory.mktemp("list") / "list.txt"
    path.write_bytes(content)
    return path


@pytest.fixture
def repo(tmp_path, tmp_path_factory, monkeypatch):
    git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KRS_PRIVATE_LIST", str(private_list(tmp_path_factory, b"acme\n")))
    return tmp_path


def commit_bytes(repo, path, data, author=None, message="c"):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    git(repo, "add", path)
    git(repo, *IDENT, "commit", "-q", "-m", message, *(["--author", author] if author else []))
    return git(repo, "rev-parse", "HEAD")


def commit(repo, path, text, author=None, message="c"):
    return commit_bytes(repo, path, text.encode(), author, message)


def commit_zip(repo, path, member):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(member, b"x")
    return commit_bytes(repo, path, buf.getvalue())


def stage(repo, path, text):
    (repo / path).write_bytes(text.encode())
    git(repo, "add", path)


def tag(repo, name, message, tagger):
    """An annotated tag of HEAD. Returns the sha of the tag object, which `git rev-parse <tag>` gives unpeeled."""
    git(repo, "-c", "user.name=" + tagger, *IDENT[2:], "-c", "tag.gpgsign=false", "tag", "-a", name, "-m", message)
    return git(repo, "rev-parse", name)


# the deny word in the tagger, in the message, or nowhere; the clean tag's tagger address trips no generic rule (R8)
TAGS = pytest.mark.parametrize("tagger, message, exit_code", [("acme", "v1", 1), ("t", "Release ACME", 1),
                                                              ("t", "v1", 0)], ids=["tagger", "message", "clean"])


def hits(out):
    """Parse '<where>:<line>: <rule>' output lines into (where, line, rule)."""
    return [re.fullmatch(r"(.+):(\d+): (\S+)", line).groups() for line in out.splitlines()]


def push(monkeypatch, *lines):
    monkeypatch.setattr(sys, "stdin", io.StringIO("".join(line + "\n" for line in lines)))
    return gate.main(["--pre-push", "origin", "url"])


# --- scan_text -------------------------------------------------------------------------------

def test_generic_rules():
    text = "a " + "D" + ":" + "\\" + "data\nb " + "user" + "@" + "example.org\n"
    assert gate.scan_text(text, deny=[]) == [(1, "generic:drive"), (2, "generic:email")]


@pytest.mark.parametrize("text, rules", [
    ("C" + ":" + "/x", ["drive"]),
    ("cd " + "E" + ":" + "\\y", ["drive"]),
    ("/" + "home/bob/x", ["home"]),
    ("/" + "Users/bob/x", ["home"]),
    ("\\\\" + "srv\\share", ["unc"]),
    ("bob" + "@" + "mail.example.org", ["email"]),
    ("a" + "@" + "b.co and c" + "@" + "d.co", ["email"]),   # one hit per rule and line
    ("https://example.org/a", []),                          # a URL scheme is not a drive
    ("name" + "@" + "localhost", []),                       # a host needs a dot
])
def test_each_generic_rule(text, rules):
    assert gate.scan_text(text, deny=[]) == [(1, "generic:" + r) for r in rules]


def test_a_huge_line_without_an_at_sign_is_scanned_quickly():
    start = time.perf_counter()
    assert gate.scan_text("a" * 200_000, deny=["x"]) == []     # the e-mail regex alone takes ~30 s here
    assert time.perf_counter() - start < 5


def test_generic_rules_can_be_switched_off():
    assert gate.scan_text("D" + ":" + "/x", deny=[], generic=False) == []


def test_deny_hits_are_numbered_by_entry_and_ordered_by_line():
    assert gate.scan_text("acme ACME\nx", deny=["acme", "x"]) == [(1, "deny#1"), (2, "deny#2")]


# --- the private list ------------------------------------------------------------------------

def test_deny_is_case_insensitive_and_never_echoed(repo, capsys):
    commit(repo, "notes.md", "Project ACME\n")
    assert gate.main(["--all"]) == 1
    out = capsys.readouterr().out
    assert "deny#1" in out and "acme" not in out.lower()


def test_missing_list_fails_closed(repo, monkeypatch):
    monkeypatch.delenv("KRS_PRIVATE_LIST")
    assert gate.main(["--all"]) == 2


def test_list_path_that_does_not_exist_fails_closed(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("KRS_PRIVATE_LIST", str(tmp_path / "nope.txt"))
    assert gate.main(["--all"]) == 2


@pytest.mark.parametrize("content", [
    b"",                                    # no entries protects nothing
    b"# only a comment\n\n",
    "café\n".encode("cp1252"),         # not UTF-8: entries would silently never match
    "acme\n".encode("utf-16"),              # what Windows PowerShell 5 writes for '>'
])
def test_unusable_list_fails_closed(repo, monkeypatch, tmp_path_factory, content):
    monkeypatch.setenv("KRS_PRIVATE_LIST", str(private_list(tmp_path_factory, content)))
    assert gate.main(["--all"]) == 2


def test_list_format(repo, monkeypatch, tmp_path_factory, capsys):
    raw = "﻿zzz\r\n# note qqq\r\n\r\n   \r\n  ACME  \r\n"   # BOM, CRLF, comment, blanks, padding
    monkeypatch.setenv("KRS_PRIVATE_LIST", str(private_list(tmp_path_factory, raw.encode())))
    commit(repo, "a.txt", "zzz\nqqq\nacme\n")
    assert gate.main(["--all"]) == 1
    assert [(n, r) for _, n, r in hits(capsys.readouterr().out)] == [("1", "deny#1"), ("3", "deny#2")]


def test_generic_only_needs_no_list_and_ignores_it(repo, monkeypatch):
    commit(repo, "a.txt", "acme\n")
    assert gate.main(["--all", "--generic-only"]) == 0      # list set but not applied
    monkeypatch.delenv("KRS_PRIVATE_LIST")
    assert gate.main(["--all", "--generic-only"]) == 0      # list absent and not needed


# --- what is scanned -------------------------------------------------------------------------

def test_author_email_is_checked(repo):
    commit(repo, "a.txt", "clean\n", author="dev <dev" + "@" + "acme.test>")
    assert gate.main(["--all"]) == 1


def test_commit_message_is_checked(repo):
    commit(repo, "a.txt", "clean\n", message="Project ACME")
    assert gate.main(["--all"]) == 1


def test_zip_member_names_are_checked(repo):
    commit_zip(repo, "w.npz", member="acme.npy")
    assert gate.main(["--all"]) == 1


@pytest.mark.parametrize("data, exit_code", [
    (b"\0acme", 0),                 # a NUL in the first 8 KiB makes it binary: skipped
    (b"x" * 8192 + b"\0acme", 1),   # a NUL after the first 8 KiB does not
])
def test_binary_blobs_are_skipped(repo, data, exit_code):
    commit_bytes(repo, "blob.bin", data)
    assert gate.main(["--all"]) == exit_code


def test_a_file_named_like_an_archive_but_not_one_is_scanned_as_text(repo):
    commit(repo, "fake.zip", "acme\n")
    assert gate.main(["--all"]) == 1


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_a_utf16_file_with_a_byte_order_mark_is_text_not_binary(repo, capsys, encoding):
    sha = commit_bytes(repo, "notes.txt", "﻿clean\r\nProject ACME\r\n".encode(encoding))  # NULs in every line
    assert gate.main(["--all"]) == 1
    assert hits(capsys.readouterr().out) == [(f"{sha[:8]}:notes.txt", "2", "deny#1")]


@pytest.mark.parametrize("data", [
    "Projeto ação\n".encode("cp1252"),                    # what a Windows editor saves: not UTF-8
    "Projeto ação\n".encode() + b"\xe9\n",                # UTF-8 with one stray byte: its UTF-8 reading still counts
], ids=["cp1252", "utf8-with-a-stray-byte"])
def test_an_accented_entry_matches_text_that_is_not_utf8(repo, monkeypatch, tmp_path_factory, data):
    monkeypatch.setenv("KRS_PRIVATE_LIST", str(private_list(tmp_path_factory, "ação\n".encode())))
    commit_bytes(repo, "notes.txt", data)
    assert gate.main(["--all"]) == 1


@TAGS
def test_all_scans_annotated_tags(repo, capsys, tagger, message, exit_code):
    commit(repo, "a.txt", "clean\n")
    sha = tag(repo, "v1", message, tagger)
    assert gate.main(["--all"]) == exit_code
    out = capsys.readouterr().out
    assert [where for where, _, _ in hits(out)] == [f"{sha[:8]}:tag"] * exit_code and "acme" not in out.lower()


def test_a_blob_is_checked_at_every_path_it_has(repo):
    commit(repo, "tools/privacy_allow.txt", "path:a-allowed.md\n")
    stage(repo, "a-allowed.md", "D" + ":" + "/x\n")
    stage(repo, "b-other.md", "D" + ":" + "/x\n")           # same blob, sorts after the allowed path
    git(repo, *IDENT, "commit", "-q", "-m", "c")
    assert gate.main(["--all", "--generic-only"]) == 1


def test_a_matching_path_is_reported_without_echoing_it(repo, capsys):
    commit(repo, "acme-notes.md", "acme\n")
    assert gate.main(["--all"]) == 1
    out = capsys.readouterr().out
    assert len(hits(out)) == 2 and "acme" not in out.lower()    # the name and the content


def test_a_matching_zip_member_or_branch_is_reported_without_echoing_it(repo, capsys):
    commit_zip(repo, "w.npz", member="acme.npy")
    git(repo, "branch", "acme-branch")
    assert gate.main(["--all"]) == 1
    out = capsys.readouterr().out
    assert len(hits(out)) == 2 and "acme" not in out.lower()    # the member name and the ref name


def test_generic_hit_in_a_file_is_reported_with_commit_and_path(repo, capsys):
    sha = commit(repo, "docs/y.md", "see " + "D" + ":" + "/data\n")
    assert gate.main(["--all", "--generic-only"]) == 1
    assert hits(capsys.readouterr().out) == [(f"{sha[:8]}:docs/y.md", "1", "generic:drive")]


def test_allow_file_exempts_generic_rules_only(repo):
    commit(repo, "tools/privacy_allow.txt", "path:docs/x.md\n")
    commit(repo, "docs/x.md", "D" + ":" + "/x\n")
    assert gate.main(["--all", "--generic-only"]) == 0


def test_allow_file_exempts_only_the_listed_path(repo):
    commit(repo, "tools/privacy_allow.txt", "path:docs/x.md\n")
    commit(repo, "docs/y.md", "D" + ":" + "/x\n")
    assert gate.main(["--all", "--generic-only"]) == 1


def test_allow_file_does_not_exempt_the_private_list(repo):
    commit(repo, "tools/privacy_allow.txt", "path:docs/x.md\n")
    commit(repo, "docs/x.md", "acme\n")
    assert gate.main(["--all"]) == 1


# --- staged and pre-push ---------------------------------------------------------------------

def test_staged_scans_the_index_blob_not_the_worktree(repo, capsys):
    stage(repo, "a.txt", "acme\n")
    (repo / "a.txt").write_bytes(b"clean\n")        # the unstaged edit does not hide the staged blob
    assert gate.main(["--staged"]) == 1
    assert capsys.readouterr().out == "a.txt:1: deny#1\n"
    stage(repo, "a.txt", "clean\n")
    (repo / "a.txt").write_bytes(b"acme\n")         # an unstaged edit is not part of the commit
    assert gate.main(["--staged"]) == 0


def test_pre_push_scans_the_whole_range(repo, monkeypatch):
    commit(repo, "a.txt", "acme\n"); sha = commit(repo, "a.txt", "clean\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n"))
    assert gate.main(["--pre-push", "origin", "url"]) == 1


def test_pre_push_scans_only_what_the_remote_lacks(repo, monkeypatch):
    old = commit(repo, "a.txt", "acme\n"); new = commit(repo, "a.txt", "clean\n")
    assert push(monkeypatch, f"refs/heads/main {new} refs/heads/main {old}") == 0


def test_pre_push_new_branch_skips_what_the_same_remote_has(repo, monkeypatch):
    old = commit(repo, "a.txt", "acme\n")
    git(repo, "update-ref", "refs/remotes/origin/main", old)       # origin already has it
    new = commit(repo, "a.txt", "clean\n")
    assert push(monkeypatch, f"refs/heads/feature {new} refs/heads/feature {NEVER}") == 0


def test_pre_push_does_not_trust_what_only_another_remote_has(repo, monkeypatch):
    old = commit(repo, "a.txt", "acme\n")
    git(repo, "update-ref", "refs/remotes/backup/main", old)       # a different remote has it
    new = commit(repo, "a.txt", "clean\n")
    assert push(monkeypatch, f"refs/heads/main {new} refs/heads/main {NEVER}") == 1


def test_pre_push_skips_deletions(repo, monkeypatch):
    sha = commit(repo, "a.txt", "acme\n")
    assert push(monkeypatch, f"(delete) {NEVER} refs/heads/gone {sha}") == 0


def test_pre_push_checks_ref_names(repo, monkeypatch):
    sha = commit(repo, "a.txt", "clean\n")
    assert push(monkeypatch, f"refs/heads/main {sha} refs/heads/acme-x {NEVER}") == 1


@TAGS
def test_pre_push_scans_a_pushed_tag(repo, monkeypatch, tagger, message, exit_code):
    commit(repo, "a.txt", "clean\n")
    sha = tag(repo, "v1", message, tagger)
    assert push(monkeypatch, f"refs/tags/v1 {sha} refs/tags/v1 {NEVER}") == exit_code


def test_pre_push_of_a_tag_scans_the_commits_it_brings(repo, monkeypatch):
    commit(repo, "a.txt", "acme\n"); commit(repo, "a.txt", "clean\n")
    sha = tag(repo, "v1", "v1", "t")  # a clean tag of a clean commit, whose parent the remote lacks
    assert push(monkeypatch, f"refs/tags/v1 {sha} refs/tags/v1 {NEVER}") == 1


# --- the hooks -------------------------------------------------------------------------------

def install_hooks(repo):
    for rel in (".githooks/pre-commit", ".githooks/pre-push", "tools/privacy_gate.py"):
        (repo / rel).parent.mkdir(exist_ok=True)
        shutil.copy2(ROOT / rel, repo / rel)
    git(repo, "config", "core.hooksPath", ".githooks")


def test_pre_commit_hook_blocks_a_staged_hit(repo):
    install_hooks(repo)
    stage(repo, "a.txt", "acme\n")
    blocked = subprocess.run(["git", *IDENT, "commit", "-m", "c"], cwd=repo, capture_output=True)
    assert blocked.returncode != 0 and b"deny#1" in blocked.stdout + blocked.stderr
    stage(repo, "a.txt", "clean\n")
    git(repo, *IDENT, "commit", "-q", "-m", "c")        # a clean commit goes through


def test_pre_push_hook_blocks_a_hit_in_the_new_range(repo, tmp_path_factory):
    remote = tmp_path_factory.mktemp("remote")
    git(remote, "init", "-q", "--bare")
    git(repo, "remote", "add", "origin", str(remote))
    commit(repo, "a.txt", "clean\n")
    install_hooks(repo)
    git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")       # a clean range is allowed
    stage(repo, "a.txt", "acme\n")
    git(repo, *IDENT, "commit", "-q", "--no-verify", "-m", "c")     # skips pre-commit, not pre-push
    blocked = subprocess.run(["git", "push", "origin", "HEAD:refs/heads/main"], cwd=repo, capture_output=True)
    assert blocked.returncode != 0 and b"deny#1" in blocked.stdout + blocked.stderr


def test_hooks_are_posix_scripts_marked_executable():
    for name, args in (("pre-commit", "--staged"), ("pre-push", '--pre-push "$@"')):
        script = f"#!/bin/sh\nexec python tools/privacy_gate.py {args}\n"
        assert (ROOT / ".githooks" / name).read_bytes() == script.encode()
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    listing = subprocess.run(["git", "ls-files", "-s", ".githooks"], cwd=ROOT, capture_output=True, text=True).stdout
    modes = {line.split("\t")[1]: line.split()[0] for line in listing.splitlines()}
    assert (modes[".githooks/pre-commit"], modes[".githooks/pre-push"]) == ("100755", "100755")
