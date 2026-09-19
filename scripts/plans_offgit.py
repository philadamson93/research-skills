#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Take a repo's docs/plans tree out of git and point it at the shared mount.

Four modes, run one repo at a time:

  check    compare every plan file on origin/main to its mount copy; print the worklist.
           EXITS 1 if any file has content on both sides the other lacks. This is a gate,
           not a report -- relink refuses to run until it passes.
  push     copy up the files that exist on origin/main but not on the mount. Never overwrites.
  relink   untrack docs/plans, add the ignore rule, replace the tree with ONE symlink.
           Refuses unless check is clean and every file in the tree is safely on the mount.
  doctor   walk every checkout on this machine and repair its docs/plans symlink. Idempotent.

Why origin/main and not the working tree
----------------------------------------
Most checkouts sit on stale feature branches, so the working tree is not what the untrack
commit will act on. Measured 2026-09-15 by scripts/copy-plans-to-mount.sh: rad-eval's checkout
was missing 86 of main's plan docs while crc-extraction-agent had 43 in its tree against 2 on
main. Comparing the working tree therefore answers the wrong question. Everything here reads
`origin/main` via `git cat-file`, except the untracked-file safety sweep in relink, which is
about the working tree by definition.

Why byte identity and not a status line
---------------------------------------
A cheaper check was proposed -- read `grep -m1 "Status:"` from both sides and compare. Measured
2026-09-18 against vista_bench's five known-divergent files: it reported SAME on all five, and
two had no Status line at all. A check that cannot fail proves nothing. Blob-hash comparison of
a whole repo's plan tree costs about 12 seconds.

Never deletes anything on the mount. The mount copy is the only copy once a repo is migrated.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# PLANS_MOUNT / CODE_ROOT are overridable so the modes can be exercised against a scratch
# repo + scratch mount. A destructive step whose failure path was never run is not tested.
MOUNT = Path(os.environ.get("PLANS_MOUNT",
                            "/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning"))
CODE = Path(os.environ.get("CODE_ROOT", Path.home() / "code"))
# Where to look for CLONES. Worktrees are then discovered from each clone found here, so
# this only has to list places a clone is created, not every checkout. ~ is on the list
# because paper-trail keeps two clones directly in it.
SCAN_ROOTS = [CODE, CODE.parent]
IGNORE_RULE = "docs/plans"  # NO trailing slash: with one, git does not ignore a symlink
PLAN_DIR = "docs/plans"

# research-skills is excluded on purpose (2026-09-14): it is public and PHI-free, and there the
# plans are the product. scripts/copy-plans-to-mount.sh excludes it for the same reason.
REPOS = [
    "contrastive-3d-onc", "vista-ct", "paper-trail", "agentic-label-opt",
    "vista-eval", "vista_bench", "rad-eval", "vista-cohort",
    "crc-extraction-agent", "femr-private",
]

IDENTICAL, AHEAD, REPO_ONLY, BOTH = "identical", "mount-ahead", "repo-only", "both-differ"


def git(repo: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}:\n{r.stderr.strip()}")
    return r.stdout


def git_bytes(repo: Path, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}")
    return r.stdout


@dataclass
class Entry:
    rel: str
    blob: str
    state: str
    mount_adds: int = 0
    repo_only_lines: int = 0


@dataclass
class Report:
    repo: str
    ref: str = "origin/main"
    entries: list[Entry] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)

    def of(self, state: str) -> list[Entry]:
        return [e for e in self.entries if e.state == state]

    @property
    def blocked(self) -> list[Entry]:
        return self.of(BOTH)


def plan_blobs(repo: Path, ref: str = "origin/main") -> list[tuple[str, str]]:
    """(blob-sha, path-relative-to-docs/plans) for every plan file on `ref`."""
    out = git(repo, "ls-tree", "-r", ref, "--", PLAN_DIR, check=False)
    rows = []
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        if not (path.endswith(".md") or path.endswith(".html")):
            continue
        rows.append((parts[2], path[len(PLAN_DIR) + 1:]))
    return rows


def compare(repo_name: str, ref: str = "origin/main") -> Report:
    repo = CODE / repo_name
    mount = MOUNT / repo_name
    rep = Report(repo=repo_name, ref=ref)

    for blob, rel in plan_blobs(repo, ref):
        m = mount / rel
        if not m.is_file():
            rep.entries.append(Entry(rel, blob, REPO_ONLY))
            continue
        # hash-object the mount file and compare to the git blob: exact, and no repo read
        mh = git(repo, "hash-object", str(m)).strip()
        if mh == blob:
            rep.entries.append(Entry(rel, blob, IDENTICAL))
            continue
        want = git_bytes(repo, "cat-file", "blob", blob).decode("utf-8", "replace").splitlines()
        got = m.read_text(encoding="utf-8", errors="replace").splitlines()
        # distinct lines present on one side and absent from the other. Counting distinct
        # lines, not occurrences, answers the question that matters here: is there content
        # on this side that exists nowhere on the other.
        wset, gset = set(want), set(got)
        adds = sum(1 for ln in got if ln not in wset)
        drops = sum(1 for ln in want if ln not in gset)
        rep.entries.append(Entry(rel, blob, AHEAD if drops == 0 else BOTH, adds, drops))

    # Untracked plan files in the working tree are invisible to ls-tree and have no git copy at
    # all. relink deletes the tree, so any of these not on the mount would be lost outright.
    for line in git(repo, "ls-files", "--others", "--exclude-standard", "--", PLAN_DIR,
                    check=False).splitlines():
        if not (line.endswith(".md") or line.endswith(".html")):
            continue
        rel = line[len(PLAN_DIR) + 1:]
        if not (mount / rel).is_file():
            rep.untracked.append(rel)
    return rep


def print_report(rep: Report) -> None:
    n = len(rep.entries)
    print(f"\n{rep.repo}: {n} plan files on {rep.ref}")
    for state, label in ((IDENTICAL, "identical"), (AHEAD, "mount ahead (safe)"),
                         (REPO_ONLY, "repo only (push copies these up)"),
                         (BOTH, "BOTH DIFFER -- needs a human")):
        items = rep.of(state)
        print(f"  {label:<34} {len(items)}")
        if state in (REPO_ONLY, BOTH):
            for e in items:
                extra = (f"   mount-only {e.mount_adds} / repo-only {e.repo_only_lines}"
                         f" (distinct lines)"
                         if state == BOTH else "")
                print(f"      {e.rel}{extra}")
    if rep.untracked:
        print(f"  UNTRACKED and not on the mount        {len(rep.untracked)}"
              "   <- no git copy; push these up first")
        for r in rep.untracked:
            print(f"      {r}")


def mode_check(repo_name: str, ref: str = "origin/main") -> int:
    rep = compare(repo_name, ref)
    print_report(rep)
    bad = len(rep.blocked) + len(rep.untracked)
    if bad:
        print(f"\nBLOCKED: {len(rep.blocked)} file(s) differ in both directions, "
              f"{len(rep.untracked)} untracked file(s) have no mount copy.")
        print("Resolve each by hand, then re-run check. relink will not run until this is clean.")
        return 1
    print("\nclean -- safe to push and relink")
    return 0


def mode_push(repo_name: str, apply: bool, ref: str = "origin/main") -> int:
    repo, mount = CODE / repo_name, MOUNT / repo_name
    rep = compare(repo_name, ref)
    todo = rep.of(REPO_ONLY)
    copied = 0
    for e in todo:
        dest = mount / e.rel
        if dest.exists():
            print(f"  refusing to overwrite {e.rel}")
            return 1
        print(f"  {'copy' if apply else 'would copy'} {e.rel}")
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(git_bytes(repo, "cat-file", "blob", e.blob))
            back = git(repo, "hash-object", str(dest)).strip()
            if back != e.blob:
                print(f"  MISMATCH after copy: {e.rel} want={e.blob} got={back}")
                return 1
            copied += 1
    for rel in rep.untracked:
        src, dest = repo / PLAN_DIR / rel, mount / rel
        print(f"  {'copy' if apply else 'would copy'} (untracked) {rel}")
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            if git(repo, "hash-object", str(src)).strip() != git(repo, "hash-object", str(dest)).strip():
                print(f"  MISMATCH after copy: {rel}")
                return 1
            copied += 1
    print(f"\n{copied} file(s) copied up, all verified byte-identical"
          if apply else "\ndry run -- re-run with --apply")
    return 0


def ensure_ignore_rule(repo: Path) -> bool:
    """Add the no-trailing-slash rule if absent; fix a slashed one. True if the file changed.

    Touches as few bytes as possible. These .gitignore files are long and shared (vista_bench's
    runs past 240 lines), so rewriting one through splitlines()/join() would normalise every line
    ending and any missing final newline into the diff -- turning a one-line change into a
    whole-file conflict surface for whichever other session is mid-edit.
    """
    gi = repo / ".gitignore"
    text = gi.read_text() if gi.exists() else ""
    lines = text.splitlines()
    if IGNORE_RULE in (ln.strip() for ln in lines):
        return False
    if (IGNORE_RULE + "/") in (ln.strip() for ln in lines):
        # a trailing slash does NOT match a symlink, so the tree would show up permanently dirty.
        # Replace that one line in place and leave every other byte untouched.
        out, done = [], False
        for ln in text.splitlines(keepends=True):
            if not done and ln.strip() == IGNORE_RULE + "/":
                out.append(ln.replace(IGNORE_RULE + "/", IGNORE_RULE, 1)); done = True
            else:
                out.append(ln)
        gi.write_text("".join(out))
        return True
    # append only; never rewrite what is already there
    with gi.open("a") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        fh.write("\n# The planning tree lives on the shared mount and is symlinked back here, so\n"
                 "# plan docs cost no PHI review. No trailing slash: with one, git would not\n"
                 "# ignore the symlink and every checkout would show a dirty tree.\n"
                 f"{IGNORE_RULE}\n")
    return True


def link_target(repo_name: str) -> Path:
    return MOUNT / repo_name


def mode_relink(repo_name: str, apply: bool, ref: str = "origin/main") -> int:
    repo = CODE / repo_name
    plans = repo / PLAN_DIR

    # REFUSE unless this checkout is actually sitting on the ref we compared against.
    #
    # check reads `ref` (origin/main by default), but relink deletes the WORKING TREE and untracks
    # whatever is in THIS checkout's index. On a feature branch those are different sets, and the
    # difference is unprotected: files tracked on the branch but not on the ref are never compared
    # to the mount, and a working-tree EDIT to a tracked file is not compared either -- the
    # untracked sweep does not see it, because the file is tracked.
    #
    # Measured 2026-09-19 on crc-extraction-agent, parked on feat/phi-safe-externalized-storage:
    # origin/main had 2 plan files, the branch tracked 50, the working tree held 61, and 13 were
    # uncommitted (8 untracked, 5 edits to tracked files). check compares 2 and passes; relink
    # would then have deleted 61. Migrate from a checkout that IS at the ref -- a scratch worktree
    # (`git worktree add --detach <path> origin/main`) is the cheap way, and leaves shared
    # checkouts alone.
    head = git(repo, "rev-parse", "HEAD", check=False).strip()
    want = git(repo, "rev-parse", ref, check=False).strip()
    if not head or not want:
        print(f"{repo_name}: cannot resolve HEAD or {ref} in {repo}")
        return 1
    if head != want:
        branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip() or "detached"
        tracked_here = len(git(repo, "ls-files", "--", PLAN_DIR, check=False).split())
        tracked_ref = len(plan_blobs(repo, ref))
        dirty = len(git(repo, "status", "--porcelain", "--", PLAN_DIR, check=False).splitlines())
        print(f"\n{repo_name}: REFUSING -- this checkout is not at {ref}.")
        print(f"  {repo} is on '{branch}' ({head[:9]}), {ref} is {want[:9]}.")
        print(f"  check compared {tracked_ref} file(s) from {ref}, but relink would untrack the "
              f"{tracked_here} file(s) this branch tracks")
        print(f"  and delete the whole tree, including {dirty} uncommitted change(s) that were "
              f"never compared to the mount.")
        print(f"  Migrate from a checkout that is at {ref}:")
        print(f"    git -C {repo} worktree add --detach /tmp/offgit/{repo_name} {ref}")
        print(f"    CODE_ROOT=/tmp/offgit uv run --script scripts/plans_offgit.py relink "
              f"{repo_name} --apply")
        return 1

    if mode_check(repo_name, ref) != 0:
        return 1
    if plans.is_symlink():
        print(f"\n{repo_name}: already a symlink -> {os.readlink(plans)}")
        return 0
    if not apply:
        print(f"\nwould untrack {PLAN_DIR}, set the ignore rule, and link it to "
              f"{link_target(repo_name)}\ndry run -- re-run with --apply")
        return 0
    # A repo can have NOTHING tracked under docs/plans and still need migrating -- femr-private's
    # main carries no plan docs at all, yet 16 live on the mount that its checkouts should be able
    # to open. `git rm` errors on an empty pathspec and rmtree errors on a missing directory, so
    # both are conditional. Without this the whole mode died on a traceback for that repo.
    tracked_now = git(repo, "ls-files", "--", PLAN_DIR, check=False).strip()
    if tracked_now:
        print(f"\nuntracking {PLAN_DIR} in {repo_name} (index only, files stay)")
        git(repo, "rm", "-r", "--cached", "-q", PLAN_DIR)
    else:
        print(f"\n{repo_name}: nothing tracked under {PLAN_DIR} -- ignore rule and link only")
    ensure_ignore_rule(repo)
    if plans.exists() and not plans.is_symlink():
        shutil.rmtree(plans)                   # real dir; the mount copy is verified above
    plans.parent.mkdir(parents=True, exist_ok=True)
    plans.symlink_to(link_target(repo_name))
    print(f"linked {PLAN_DIR} -> {link_target(repo_name)}")
    left = git(repo, "ls-files", "--", PLAN_DIR).strip()
    if left:
        print("FAILED: files still tracked under docs/plans")
        return 1
    print("verified: 0 files tracked, link resolves, "
          f"{len(list(link_target(repo_name).rglob('*.md')))} plan docs reachable")
    return 0


def worktrees_of(root: Path) -> list[Path]:
    """The paths `git worktree list` reports for one clone, skipping prunable entries."""
    paths: list[Path] = []
    cur: Path | None = None
    prunable = False
    for line in git(root, "worktree", "list", "--porcelain", check=False).splitlines():
        if line.startswith("worktree "):
            if cur is not None and not prunable:
                paths.append(cur)
            cur, prunable = Path(line[len("worktree "):]), False
        elif line.startswith("prunable "):
            prunable = True
    if cur is not None and not prunable:
        paths.append(cur)
    return paths


def checkouts_of(repo_name: str) -> list[Path]:
    """Every checkout on this machine whose origin is this repo -- worktrees AND separate clones.

    THREE sources, unioned, because no two of them are enough. Each was added only after it was
    caught missing a checkout that a session was actually working in.

      1. a scan of ~/code/*  -- the only thing that finds a SEPARATE CLONE, which shares no
         worktree list with its siblings (vista_bench_fresh, the two *-mcp-runtime clones).
      2. a scan of ~/*       -- the only thing that finds a clone that is not under ~/code at all.
         paper-trail has two: ~/paper-trail, which holds the live isolation plan and 52 tracked
         plan files against main's 20, and its worktree ~/paper-trail-planA.
      3. `git worktree list`, run from every clone found by 1 and 2 -- the only thing that finds a
         NESTED worktree. 91 of this machine's 143 worktrees sit at <repo>/.claude/worktrees/*,
         and three agentic-label-opt worktrees live under ~/.paper-trail/.

    Source 1 alone -- what this did until 2026-09-19 -- found 50 checkouts of the 146 that exist.
    Adding 3 found 146 but still missed paper-trail's two outside ~/code, which is why 2 is here.
    The misses are not harmless: a checkout loses its real docs/plans files the moment it moves
    onto the migrated main, and with no link created nothing in it can open a plan doc by its repo
    path. That is the state vista-cohort-frontend is in today.

    Known limit: a clone nested deeper than one level below ~ or ~/code is still invisible. There
    is none today (verified by a depth-4 sweep of ~ on 2026-09-19). If one appears, add its parent
    to SCAN_ROOTS rather than widening the sweep -- walking all of ~ is slow and picks up junk.
    """
    seen: dict[Path, Path] = {}
    roots: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if not (d / ".git").exists():
                continue
            url = git(d, "remote", "get-url", "origin", check=False).strip()
            if url and Path(url.rstrip("/")).name.removesuffix(".git") == repo_name:
                roots.append(d)
    for d in roots:
        for q in [d, *worktrees_of(d)]:
            if (q / ".git").exists():
                seen.setdefault(q.resolve(), q)
    return [seen[k] for k in sorted(seen)]


def mode_doctor(repo_names: list[str], apply: bool) -> int:
    bad = 0
    for name in repo_names:
        target = link_target(name)
        if not target.is_dir():
            print(f"  {name:<38} no mount folder at {target} -- skipped")
            continue
        for d in checkouts_of(name):
            # the bare leaf name is ambiguous now that nested worktrees are included -- several
            # repos have one called e.g. "vertex-gate" -- so show the path instead.
            lbl = str(d).replace(str(Path.home()), "~")
            plans = d / PLAN_DIR
            tracked = git(d, "ls-files", "--", PLAN_DIR, check=False).strip()
            if tracked:
                # this checkout is on a commit that predates the migration -- its real files are
                # correct for the commit it has. Leave it completely alone.
                print(f"  {lbl:<64} not yet (still tracks {len(tracked.splitlines())} files)")
                continue
            if plans.is_symlink() and Path(os.readlink(plans)) == target:
                print(f"  {lbl:<64} linked")
                continue
            if plans.exists() and not plans.is_symlink():
                print(f"  {lbl:<64} REAL DIR but nothing tracked -- left alone, look at it")
                bad += 1
                continue
            print(f"  {lbl:<64} {'LINKING' if apply else 'would link'}")
            if apply:
                if plans.is_symlink():
                    plans.unlink()
                plans.parent.mkdir(parents=True, exist_ok=True)
                plans.symlink_to(target)
    if not apply:
        print("\ndry run -- re-run with --apply")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["check", "push", "relink", "doctor"])
    ap.add_argument("repo", nargs="?", help="repo name; omit with doctor for all")
    ap.add_argument("--apply", action="store_true", help="actually write (default is a dry run)")
    ap.add_argument("--ref", default="origin/main",
                    help="which ref to compare against. Default origin/main, because that is what "
                         "the untrack commit acts on. Use --ref HEAD straight after a local merge, "
                         "when origin/main does not yet carry the files the merge just re-added.")
    a = ap.parse_args()

    if a.mode == "doctor":
        # validate here too: without this a typo'd repo name finds no mount folder, skips
        # silently and prints "dry run", which reads exactly like success.
        if a.repo and a.repo not in REPOS:
            ap.error(f"{a.repo} is not in scope. In scope: {', '.join(REPOS)}")
        return mode_doctor([a.repo] if a.repo else REPOS, a.apply)
    if not a.repo:
        ap.error(f"{a.mode} needs a repo name")
    if a.repo not in REPOS:
        ap.error(f"{a.repo} is not in scope. In scope: {', '.join(REPOS)}")
    if not (CODE / a.repo / ".git").exists():
        ap.error(f"no git repo at {CODE / a.repo}")

    return {"check": lambda: mode_check(a.repo, a.ref),
            "push": lambda: mode_push(a.repo, a.apply, a.ref),
            "relink": lambda: mode_relink(a.repo, a.apply, a.ref)}[a.mode]()


if __name__ == "__main__":
    sys.exit(main())
