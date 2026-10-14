---
name: grill
description: Interview Phil relentlessly about a piece of work until every decision is settled, then write a one-page spec. Replaces plan mode and the long plan doc. TRIGGER when Phil starts work that spans more than one session, runs on a GPU or VM, writes to PHI data, or would need more than about three answers from Phil; or says "/grill", "grill me", "interview me", "let's pin this down". SKIP for small fixes and anything reversible in under an hour.
argument-hint: "<rough idea, or path to a Draft spec to finish>"
---

<!-- The interview below is mattpocock/skills `skills/productivity/grilling/SKILL.md` @ 49dd158,
     unmodified. MIT License, Copyright (c) 2026 Matt Pocock; full text in
     LICENSES/MIT-mattpocock-skills.txt. Only the "Write it down" section after it is ours. -->


Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Word each question so "yes" accepts your recommended answer.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.

## Write it down (VISTA addition)

Given a path to a `Draft` spec (an interview stopped by `/wrapup`), start from its *Decided* and
*Still to ask* lists rather than from scratch.

When the user confirms, save a one-page spec to `docs/plans/<what-it-is>.md`. About 80 lines is
the ceiling; past that it's two pieces of work. No implementation steps.

```markdown
Reference: docs/claude_ops.md
Program: <brief path> — stage N of M

# <What this is>
Status: Draft (YYYY-MM-DD), until the user confirms; then Approved (YYYY-MM-DD)

## Goal
## Done when
- <check> → <what passing looks like>
Stop and come back if: <the result that means the premise was wrong>.
## Decided
- <question> → <answer> (YYYY-MM-DD)
## Out of scope
## Code layout
- <path or module> — <what it does>; <reuses X | extends X | new, because X doesn't fit: why>
## Deliverables
- [ ] <file, table, run or doc> — <one line>
## Expensive steps
<host>: <one-line command> → <pass condition> — approved YYYY-MM-DD | needs approval. Or "None".
## Landing
Branch or straight on main; what must clear before merge; branches that must land first.
```

Leave out the `Program:` line if no brief exists yet, and say so.
