---
name: grill
description: Interview Phil relentlessly about a piece of work until every decision is settled, then write a one-page spec. Replaces plan mode and the long plan doc. TRIGGER when Phil starts work that spans more than one session, runs on a GPU or VM, writes to PHI data, or would need more than about three answers from Phil; or says "/grill", "grill me", "interview me", "let's pin this down". SKIP for small fixes and anything reversible in under an hour.
argument-hint: "<rough idea, or path to a Draft spec to finish>"
---

<!-- The interview below is mattpocock/skills `skills/productivity/grilling/SKILL.md` @ 49dd158,
     unmodified. MIT License, Copyright (c) 2026 Matt Pocock; full text in
     LICENSES/MIT-mattpocock-skills.txt. Only the "Where the rounds go" and "Write it down" sections
     after it are ours. The first one overrides where a round is shown: on the dashboard, not in chat. -->


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

## Where the rounds go (VISTA addition, Phil 2026-11-20)

Phil reads and answers grill rounds on the work dashboard's **To review** tab, not in chat. Each round,
and the final "is this the shared understanding?" check, is a page sent there:

1. Write the round as JSON in `$CLAUDE_JOB_DIR/tmp` (or `docs/session/`): title `Grill: <the work>`,
   round number, one or two sentences of context, the settled decisions so far, and the frontier questions,
   each with its body and recommended answer. When a question has a short list of answers, give them as
   `options` (with `multi` if several can be picked) and make `recommend` one of them: Phil answers on the page
   by clicking, the recommendation starts selected, and "Other" opens a box pre-filled with it. Format in the docstring of
   `research-skills/scripts/dashboard/grill_page.py` (mount copy: `planning/dashboard/bin/grill_page.py`).
2. `python3 <that script> round.json grill-<slug>.html`, then send it with `/send-for-review` as a verdict
   page (no `--fyi`), `--name grill-<slug>` every round so each new round shows as the next version and the
   old one is marked replaced, `--item` once the dashboard item exists, and
   `--look "Grill round N: <the decision that matters most this round>"`.
3. In chat, print only the link it gives and the question titles, one line each. Start the `wait` line in
   the background and end the turn.
4. When it wakes you: `APPROVED` with no comment means yes to every recommendation. `NEEDS CHANGES` (or an
   approval with a comment) means read the comment: `Q2: …` lines override those questions (the page writes
   them when Phil changes an answer: an option label, several joined by `; `, or Other's text), unmentioned
   questions take the recommendation, and anything unclear goes into the next round rather than being
   guessed. Record the answers, recompute the frontier, send the next round.
5. The final round has no questions and carries the spec text (`"spec"`). Its approval is Phil's confirming
   the interview, so the spec becomes Approved.

If Phil answers in chat instead, take the answer from chat. If the send fails (mount not reachable), say so
and ask the round in chat in the format above.

## Write it down (VISTA addition)

Given a path to a `Draft` spec (an interview stopped by `/wrapup`), start from its *Decided* and
*Still to ask* lists rather than from scratch.

When the user confirms, save a one-page spec to `docs/plans/<what-it-is>.md`. About 80 lines is
the ceiling; past that it's two pieces of work. No implementation steps.

Also write (or update) the work dashboard item for it: `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/items/<id>.json`,
format in `research-skills/scripts/dashboard/README.md`. A question if it tests something, a feature if it
builds something. Before saving, propose the plain-English title, why it matters and (for a question) the
result layout, and ask the user "is this right?"; their yes is the approval, so set `approved`. Put the
spec's open decisions under `decisions` and its Expensive steps under `runs` once they are started.

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
