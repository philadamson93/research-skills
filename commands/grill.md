---
name: grill
description: Interview Phil until a piece of work is pinned down at the level that matters — what we're building, how we'll know it worked, where it sits in the codebase, and what it costs — then write a one-page spec. Replaces plan mode and the long plan doc. TRIGGER when Phil starts work that spans more than one session, runs on a GPU or VM, writes to PHI data, or would need more than about three answers from Phil; or says "/grill", "grill me", "interview me", "let's pin this down". SKIP for small fixes and anything reversible in under an hour.
argument-hint: "<rough idea, or path to a spec to finish>"
---

<!-- Adapted from mattpocock/skills `skills/productivity/grilling/SKILL.md` @ 49dd158, MIT License,
     Copyright (c) 2026 Matt Pocock. Changes: questions go through AskUserQuestion; question level
     tuned to Phil (below); adds a calibration list and a one-page spec at the end.
     Full MIT text: LICENSES/MIT-mattpocock-skills.txt. -->

# grill

Interview Phil relentlessly until you reach a shared understanding. Map this as a **design
tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already
settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask
the whole frontier in one round, through `AskUserQuestion` (up to four per call; make several
calls if the frontier is wider). Put your recommended answer first, marked "(Recommended)".
Then wait for the answers before the next round.

Each round reshapes the tree: settled decisions push the frontier outward and unblock questions
that depended on them. Recompute the frontier and ask the next round. A question whose answer
depends on another question still open in this round belongs to a _later_ round. An answer may
come back as a correction or a new idea rather than a pick; follow it.

Finding _facts_ is your job, never Phil's. When a question needs a fact from the code, the docs,
the mount or memory, dispatch a sub-agent to find it; don't ask for anything you could look up.
(Plan docs are often in an ignored symlink: search
`/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/`, not the checkout.) Don't block on it:
only the questions downstream of a running search wait. The _decisions_ are Phil's: put each to
Phil and wait.

The interview is done when the frontier is empty: every branch visited, nothing left silently
assumed. Don't act on it until Phil confirms you've reached a shared understanding.

**Given a path to a `Draft` spec** (an interview stopped by `/wrapup`), read its *Decided* and
*Still to ask* lists, rebuild the frontier from there, and don't re-ask what's settled.

## What to ask about

Phil cares about the high level, not engineering detail. Ask about:

- **What and why**: the goal, the scope, what's out.
- **How we'll know it worked**: the checks, the numbers, the result that would mean the premise
  was wrong. Settle any fork you can see coming ("above 0.8 do A, otherwise B") now.
- **Shape**: where this lives, whether it's modular in the right places, whether it reuses what
  exists or forks it, contracts with sibling repos.
- **What it costs**: GPU or VM runs, writes to PHI data, anything not undoable in under an hour.
  Put each such step to Phil as its own question, and record the answer on its line in the spec.
- **Research choices**: cohort, split, labels, baselines, thresholds, fall back or raise.

Decide yourself, and don't ask about: names, internal code structure, library and API minutiae,
test mechanics, file layout inside a module. Options describe outcomes, never mechanisms.

## Calibration

Phil tunes this list. When Phil says a question was too detailed, or that you missed one Phil
needed, add a one-line example here (dated) and commit it to research-skills on main.

- 2026-10-14 (seed): "fall back or raise on a missing per-task parquet" is too mechanical. Ask
  "skip that task and keep going, or stop so you can look?" instead.

## Write it down

When Phil confirms, save a one-page spec to `docs/plans/<what-it-is>.md`. About 80 lines is
the ceiling; past that it's two pieces of work. No implementation steps.

```markdown
Reference: docs/claude_ops.md
Program: <brief path> — stage N of M

# <What this is>
Status: Draft (YYYY-MM-DD), until Phil confirms; then Approved (YYYY-MM-DD)

## Goal
## Done when
- <check> → <what passing looks like>
Stop and come back if: <the result that means the premise was wrong>.
## Decided
- <question> → <answer> (YYYY-MM-DD)
## Out of scope
## Deliverables
- [ ] <file, table, run or doc> — <one line>
## Expensive steps
<host>: <one-line command> → <pass condition> — approved YYYY-MM-DD | needs approval. Or "None".
## Landing
Branch or straight on main; what must clear before merge; branches that must land first.
```

Leave out the `Program:` line if no brief exists yet, and say so.
