# Work dashboard

One status view, built around **questions** (test something) and **features** (build something), that
answers after hours away: what finished, what needs Phil, what is running where, and what is next.
Spec: `docs/plans/work-dashboard.md`.

- Served: front door `/dashboard/` (a site on the review server on vista-cohort; clicks save there).
- Files: `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/` (also opens as local files, read-only for clicks).

## How it works

Nothing here asks a session anything. It reads what already exists and writes pages.

| Source | Gives |
|---|---|
| `planning/dashboard/items/<id>.json` | one question or feature: wording, result layout, decisions, runs, code |
| `planning/dashboard/hosts/<host>.json` | each machine's Claude sessions and what the box is doing (`snapshot_sessions.py`) |
| readbacks named in an item's runs | the run's state, from the status line at the top |
| `planning/review_answers/<email>.json` | Phil's clicks and comments, saved by the review server |
| `planning/boards/*.md`, `planning/programs/*.md` | programs and their stage strips |

- `snapshot_sessions.py` runs on every machine every 5 minutes (others run the mount copy in `planning/dashboard/bin/`).
- `build_dashboard.py` runs on phil-sllm-01 after the snapshot (`refresh.sh`) and writes, all flat in `planning/dashboard/`:
  `index.html` (status), `<item-id>.html` (one per item), `method-<name>.html` (one per method),
  `phil-actions.json` (Phil's clicks and comments merged, for sessions to read) and `problems-auto.json`.
- `daily_review.py` runs once a day: one Sonnet call over all item files proposes duplicate work and
  missing links into `problems-proposed.json`, capped at $5 a day. It never edits item files.

## Item file format

JSON, one file per item. **Who may change a field matters**: Phil owns the meaning; sessions own progress.

```json
{
  "id": "agents-vs-embeddings",            // file name without .json; never changes
  "kind": "question",                      // question | feature
  "program": "vista-bench-paper",          // brief file name under planning/programs/
  "title": "Do LLM agents add anything to our embedding models?",   // PHIL
  "why": "Are site-specific embedding models and LLM agents mutually beneficial?",  // PHIL
  "answer": "Agents tie our best models; adding one on top of the best fusion gains nothing.", // PHIL
  "approved": {"at": "2026-11-18"},        // set when Phil approves the wording; absent = draft wording
  "draft": {"answer": "...", "by": "<session name>", "at": "2026-11-19"},  // SESSION proposes PHIL-owned changes here
  "status": "One plain line: where it stands now.",   // SESSION
  "methods": ["alone", "fusion", "disagreement"],     // links questions using the same method
  "links": ["agent-over-time"],                       // other items it depends on or feeds
  "in_paper": false,                                  // PHIL: result is definitely going into the paper
  "layout": "grid",                        // grid | findings | checklist  (pick one; all optional)
  "grid": {"columns": ["Treatment start", "6 months"],
           "groups": [{"method": "Agent alone", "rows": [
             {"label": "Zero-shot agent", "sub": "what it is",
              "cells": [{"state": "tie", "value": "ties", "note": "",
                         "session": "", "commit": "", "planned": true}]}]}]},   // SESSION fills cells
  "findings": [{"text": "Within-stage probes no better", "number": "-0.015", "state": "no"}],   // SESSION
  "checklist": [{"step": "Review passed", "state": "done", "commit": "a489806"}],             // SESSION
  "decisions": [{"id": "sonnet-test", "kind": "decision", "text": "Run the Sonnet agent on test?",
                 "since": "2026-11-18", "closed": null}],   // SESSION adds/closes; Phil answers on the page
  "runs": [{"label": "Ladder test passes", "machine": "phil-sllm-02",
            "readback": "planning/vista_eval_vlm/session/...-readback.md",
            "job": "alo-run",                 // text to look for in the machine's job list
            "quiet_h": 6}],                   // how long it may write nothing while the job is alive
  "code": [{"what": "Agent over time", "where": "vista_eval_vlm feat/died-ehr-over-time",
            "state": "unmerged", "used_by": ["agents-vs-embeddings"]}],   // throwaway | unmerged | permanent
  "match": ["agents-vs-embeddings"],       // session names/asks that belong here (until hand-offs name the item)
  "sources": ["planning/vista_bench/paper/sessions/...-readback.md"]
}
```

A session that thinks code should become permanent adds a decision with `"kind": "make permanent?"`; the
builder also raises one itself when a `throwaway` code entry is used by two or more items or the item is
`in_paper`.

Cell and finding `state`: `yes` (helps, held up) · `tie` · `no` (no gain) · `running` · `waiting` (on Phil) ·
`gap` (not run) · `na`. Checklist `state`: `done` · `doing` · `todo` · `blocked`.

Nothing in the format is specific to one program: a labeler question uses `findings` (agreement, cost per
patient), an app or engineering piece is a `feature` with a `checklist`, a benchmark experiment uses `grid`.

## Readback status line

Every readback a run names starts (first line after any `Reference:`/`Program:` lines) with:

```
Status: running | waiting on Phil | done | failed — <one plain sentence: the result or what it's doing>
```

Sessions rewrite it every time they update the readback. The page trusts it; a readback without one shows
"status unknown". A run with status `running` counts as **possibly died** only when nothing new has been
written for `quiet_h` hours **and** its machine reports no job containing `job`. If the machine doesn't
report, the page says "quiet, can't check the job".

## Phil's clicks

On the served page, Done / Snooze / triage / comments / Approve are kept in browser storage under `wd:` keys,
which the review server saves to `planning/review_answers/<email>.json`. The builder merges them into
`phil-actions.json` (with timestamps) so any session can read what Phil decided, dismissed or wrote, and
applies an Approve click by setting `approved` in the item file. `/dashboard` turns a closed decision with a
comment into a dated line in the program brief's decision ledger.
