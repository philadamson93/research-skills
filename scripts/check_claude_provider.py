#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check whether new Claude Code sessions on this machine use Vertex or the subscription login.

Used by /switch-provider after Phil restarts `claude agents`. Read-only. Three checks:

  1. settings  which provider ~/.claude/settings.json asks for (Vertex keys present or not)
  2. window    whether the running `claude agents` window started AFTER the settings file was
               last edited -- an older window keeps handing out the old provider
  3. sessions  the environment the background helper recorded for each session started since
               that window opened (~/.claude/daemon/roster.json, workers/*/dispatch/env)

Exits 0 when the window is fresh and every session started from it matches the settings,
1 on any mismatch, 2 when nothing has been started from the fresh window yet (start one, rerun).
"""

import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
ROSTER = os.path.join(HOME, ".claude", "daemon", "roster.json")
KEY = "CLAUDE_CODE_USE_VERTEX"


def fmt(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def agents_window_starts() -> list[float]:
    """Start times (epoch seconds) of running `claude agents` processes owned by this user."""
    out = subprocess.run(
        ["ps", "-u", str(os.getuid()), "-o", "pid=,args="], capture_output=True, text=True
    ).stdout
    starts = []
    for line in out.splitlines():
        pid, _, args = line.strip().partition(" ")
        if args.strip() == "claude agents":
            st = subprocess.run(
                ["ps", "-o", "lstart=", "-p", pid], capture_output=True, text=True
            ).stdout.strip()
            starts.append(time.mktime(time.strptime(st, "%a %b %d %H:%M:%S %Y")))
    return starts


def main() -> int:
    env = json.load(open(SETTINGS)).get("env", {})
    want = "vertex" if env.get(KEY) else "subscription"
    edited = os.path.getmtime(SETTINGS)
    print(f"settings   asks for {want} (file last edited {fmt(edited)})")

    starts = agents_window_starts()
    if not starts:
        print("window     no 'claude agents' window running -- start one, then rerun")
        return 2
    newest = max(starts)
    for s in sorted(starts):
        state = "fresh" if s > edited else "STALE (opened before the edit)"
        print(f"window     claude agents started {fmt(s)}: {state}")
    stale_windows = [s for s in starts if s <= edited]

    workers = json.load(open(ROSTER)).get("workers", {})
    since = []
    for wid, w in workers.items():
        d = w.get("dispatch") or {}
        created = (d.get("createdAt") or 0) / 1000
        if created > newest:
            got = "vertex" if KEY in (d.get("env") or {}) else "subscription"
            since.append((created, wid, got))
    if newest <= edited:
        print("RESULT     FAIL: every agents window predates the edit -- exit and restart it")
        return 1
    if not since:
        print("sessions   none started from the fresh window yet -- start one, then rerun")
        return 2
    bad = 0
    for created, wid, got in sorted(since):
        ok = got == want
        bad += not ok
        print(f"sessions   {fmt(created)} {wid}: {got}{'' if ok else '  <-- MISMATCH'}")
    if bad:
        print(f"RESULT     FAIL: {bad} new session(s) not on {want}")
        return 1
    note = f" ({len(stale_windows)} older window(s) still open -- sessions started there stay on the old provider)" if stale_windows else ""
    print(f"RESULT     PASS: {len(since)} new session(s) on {want}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
