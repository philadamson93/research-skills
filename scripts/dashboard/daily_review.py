#!/usr/bin/env python3
"""Once a day: one Sonnet call over every question/feature file proposes problems for Phil's triage.

    python3 daily_review.py [--force] [--cap 5]

Looks for duplicate or overlapping work, missing links between items, the same code built twice, and
questions whose answer another item already holds. Writes planning/dashboard/problems-proposed.json.
Never edits item files, never messages a session. No tools: the model only reads what this script sends.
Spend is logged per day in planning/dashboard/review-spend.json and stops at the cap.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import tempfile
from datetime import date
from pathlib import Path

DASH = Path("/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard")
MODEL = "claude-sonnet-5-5"
KEEP = ("id", "kind", "program", "title", "why", "answer", "status", "methods", "links", "decisions", "code", "in_paper")

PROMPT = """You review a researcher's list of open research questions and engineering features, across several
programs, to find problems worth raising with him. Items are JSON below.

Find at most 8 problems of these kinds, only where the items themselves show it:
- duplicate or overlapping work: two items answering the same question, or building the same thing
- a missing link: one item's result clearly bears on another, but neither links to the other
- code built twice, or a throwaway script several items now depend on
- a question whose answer another item already holds

Rules for each problem: one or two plain-English sentences a researcher can read cold. Name the items by their
titles. No internal run labels, file names or code names as the subject. Do not invent facts beyond the items.
If there are no real problems, return an empty list. Do not raise again anything in DISMISSED (Phil already
dismissed or merged it), nor a reworded version of it.

Reply with JSON only: [{"text": "...", "items": ["<id>", "<id>"]}]

ITEMS:
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="run even if it already ran today")
    ap.add_argument("--cap", type=float, default=5.0, help="dollars per day")
    ap.add_argument("--dash", default=str(DASH))
    args = ap.parse_args()
    dash = Path(args.dash)
    lock = open(dash / ".daily-review.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)   # one review at a time, even if cron overlaps
    except OSError:
        print("another review is running")
        return
    # read the spend log only after taking the lock, so two overlapping runs cannot both pass the checks
    today = date.today().isoformat()
    ledger_f = dash / "review-spend.json"
    ledger = json.loads(ledger_f.read_text()) if ledger_f.exists() else {}
    spent = ledger.get(today, {}).get("usd", 0.0)
    if ledger.get(today, {}).get("ran") and not args.force:
        print(f"already ran today (${spent:.2f}); --force to run again")
        return
    if spent >= args.cap:
        print(f"daily cap reached: ${spent:.2f} of ${args.cap:.2f}")
        return
    items = []
    for f in sorted((dash / "items").glob("*.json")):
        try:
            it = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        items.append({k: it[k] for k in KEEP if k in it})
    if len(items) < 2:
        print("fewer than two items; nothing to compare")
        return
    dismissed = []
    try:
        acts = json.loads((dash / "phil-actions.json").read_text())
        dismissed = [v.get("text") for v in acts.get("problems", {}).values()
                     if isinstance(v, dict) and v.get("act") in ("dismiss", "dup") and v.get("text")]
    except (OSError, json.JSONDecodeError):
        pass
    # Record the run before calling: a timeout or a garbled answer must not let cron retry and overspend.
    ledger[today] = {"usd": round(spent, 4), "ran": True, "state": "started"}
    ledger_f.write_text(json.dumps(ledger, indent=1))
    prompt = PROMPT + json.dumps(items, ensure_ascii=False) + "\n\nDISMISSED:\n" + json.dumps(dismissed, ensure_ascii=False)
    try:
        with tempfile.TemporaryDirectory() as empty:  # empty folder: no project files for the model to pick up
            out = subprocess.run(
            ["claude", "-p", prompt, "--model", MODEL,
             "--output-format", "json", "--max-turns", "1", "--tools", "", "--strict-mcp-config",
             "--max-budget-usd", f"{max(0.01, args.cap - spent):.2f}"],
            capture_output=True, text=True, timeout=900, cwd=empty)
        res = json.loads(out.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        # Spend unknown: count the whole cap as spent today, so nothing runs again until tomorrow.
        ledger[today] = {"usd": round(max(spent, args.cap), 4), "ran": True, "state": f"failed: {type(e).__name__}"}
        ledger_f.write_text(json.dumps(ledger, indent=1))
        raise SystemExit(f"review call failed ({type(e).__name__}); counted as the full ${args.cap:.2f} for today")
    cost = float(res.get("total_cost_usd") or 0)
    ledger[today] = {"usd": round(spent + cost, 4), "ran": True, "state": "done"}
    ledger_f.write_text(json.dumps(ledger, indent=1))
    if res.get("is_error"):
        raise SystemExit(f"review call returned an error (${cost:.2f}): {str(res.get('result'))[:300]}")
    txt = (res.get("result") or "").strip()
    txt = txt[txt.find("["): txt.rfind("]") + 1] if "[" in txt else "[]"
    try:
        found = json.loads(txt)
    except json.JSONDecodeError:
        raise SystemExit(f"could not read the review's answer (${cost:.2f}): {txt[:300]}")
    titles = {i["id"]: i.get("title", i["id"]) for i in items}
    problems = [f"[daily review {today}] {p['text']}" for p in found if isinstance(p, dict) and p.get("text")
                and all(x in titles for x in p.get("items", []))]   # drop anything naming items that don't exist
    tmp = dash / ".problems-proposed.json.tmp"
    tmp.write_text(json.dumps(problems, indent=1, ensure_ascii=False))
    tmp.replace(dash / "problems-proposed.json")
    print(f"{len(problems)} proposed problem(s), ${cost:.2f} (today ${spent + cost:.2f} of ${args.cap:.2f})")


if __name__ == "__main__":
    main()
