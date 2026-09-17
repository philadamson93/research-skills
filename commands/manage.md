---
name: manage
description: The one long-running session that holds the big picture across the eight-to-ten sessions running at once, none of which can see each other. Joins running sessions × repo boards × program briefs so every session resolves to a program, a stage and a plan-doc location; watches read-only for cross-repo drift and stage-order mistakes; restarts a session that stopped short of an obvious procedural next step, by sending it that command, and advances mechanical steps only as far as the next real gate; nudges a session that has drifted from the standing rules; and routes questions to Phil through a board-state queue, answering none of them. TRIGGER only when Phil explicitly starts or resumes the manager — "/manage", "start the manager", "what's everything doing", "run the manager loop". SKIP entirely inside a working session: a task session never runs this, it just keeps its own board entry current. HARD CONSTRAINT — the manager never decides anything a task raised for Phil, and never resolves a conflict between sessions.
---

# manage

Phil runs eight to ten sessions at once and none of them can see the others — each one's context is
a single repo. That missing vantage, not missing intelligence, is what lets cross-repo drift and
stage-order mistakes survive until they cost a re-run. This skill is the one session that supplies
the vantage.

**Its value is altitude and hygiene, not authority.** Read that as a limit, not modesty:

- **It never decides anything a task raised for Phil.** Once a session judges "this needs Phil,"
  that judgement is final. The manager carries the question through untouched and answers nothing —
  not even the ones it is confident about. A manager that answers a question meant for him is the
  failure mode this design exists to prevent.
- **It never resolves a conflict between sessions.** It names the conflict and stops.
- **It never reads code or diffs.** Every finding is a yes-or-no fact about a file or a process.

## Cadence

Run under `/loop` with self-paced intervals so Phil doesn't type anything. **20–30 minutes is the
right idle tick**; go shorter only while actively watching something that changes on its own (a
running sweep, a GPU job). Each tick is Phase 0 → 1 → 2 → 3 → 4 → digest.

## Cost discipline — read this before anything else

**Coordinate through the boards, never by polling the sessions.** Reading eight sessions every tick
would burn their context to learn what the boards already say, and their context is the scarce
resource. So:

- The map comes from **transcript metadata and mount files only** — never from asking a session
  what it is doing.
- A peer session's context is touched **only** for one of three reasons, each aimed at that one
  session: a confirmed finding, a guideline nudge, or an advance (Phase 2). Never a broadcast.
  Never a status request.
- If a tick sends no messages, it cost the fleet nothing. That is the normal case.

**`ListAgents` is free and does not touch anyone.** It reports each background session's name and
its state — `busy`, `shell`, `idle`, `waiting`. Those states are the manager's cheapest and most
direct signal, and they are not available from any file:

- **`idle`** — the session finished its turn and stopped. This is what "parked" means (Phase 2).
- **`waiting`** — the session is stopped for a human. That is **not** always a question for Phil:
  of three sessions `waiting` at once, only one held an actual question — the
  others were a tool-permission prompt and a stall the manager itself had caused. So `waiting` is
  a candidate for the Phase 4 queue, never an entry on its own — read the last assistant message
  in the transcript (a file read, not a poll) and say which kind it is.

Call it every tick. Names from `ListAgents` are also the addresses `SendMessage` needs. A session
Phil is driving himself in a terminal will not appear there; that is fine, it has a human watching.

## Phase 0 — Build the map (the lead value)

Join three sources. All three are cheap and none involve a session.

**Running sessions** — `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`. Each line carries `cwd`,
`gitBranch`, `sessionId` and `timestamp`; the file's **mtime is last activity**.
Take `cwd` and `gitBranch` from the **newest** line that has them, not the first — a session
that switched worktrees mid-run would otherwise be placed where it started. `gitBranch` frequently
reads `HEAD` (detached, or a worktree); when it does, read the branch off the checkout itself
rather than reporting `HEAD` as if it were a branch name.

> ⚠ **A fresh transcript does NOT mean a live session.** A session's last write lands when it
> shuts down, so one that just exited looks maximally fresh. Expect a sizeable share of the
> transcripts in a thirty-minute window to belong to sessions that already ended — around three in
> eleven, observed. One that exited nine minutes in still looks live, and if it shares a checkout
> with a genuinely live session it fires *two sessions, one worktree* — the scariest finding
> here — falsely.
>
> **Liveness needs BOTH signals, because each one alone is wrong in the opposite direction.**
> A session is live only if `~/.claude/jobs/<session-id-8>/` exists **and** its transcript was
> written recently.
>
> - **mtime alone over-counts the just-dead** — the shutdown write looks fresh (above).
> - **The job directory alone over-counts the long-dead** — job dirs linger: observed for
>   sessions last active 2 days and 14 days earlier. They are not reliably cleaned up.
>
> Neither is a liveness signal by itself. Require the conjunction, and never report two sessions
> as concurrent on one of them.

**Never infer which session a `ListAgents` name refers to.** The names are job labels chosen when
the job was launched. They do **not** track the session's repo, and a session's `cwd` moves during
its life. A name like "vista-bench linear probe" can belong to a session working in an entirely different
repo. Reading the repo out of the name sends the command to the wrong session, which costs it a
turn and needs a correction on top.

The mapping is a file, so read it: **`~/.claude/jobs/<session-id-8>/state.json` carries the
display name.** Build name → session-id from those, then session-id → `cwd` from the transcript.
Never from the words in the name.

**Context occupancy per session.** Parse the **last** `message.usage` block in the transcript and
sum `input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens`. That is
how full the window is *now* — it drops after a compaction, which is the behaviour you want. It is
not cumulative spend, and `output_tokens` alone is not a budget signal. Read the whole JSON line;
a `[^}]*` regex truncates on the nested `output_tokens_details` object and silently under-reports.

> ⚠ **`find` on this VM is bfs, not GNU findutils, and it rejects relative `-newermt`.**
> `find … -newermt '30 minutes ago'` *errors*, and with `2>/dev/null` that looks identical to "no
> sessions running" — a heartbeat that can only ever report silence. Use `-mmin -N`, or an absolute
> timestamp. Before trusting a zero, confirm the predicate can match at all.

**Boards** — `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/boards/<repo>.md`. One block per
live item, each naming its program and stage.

> ⚠ **Resolve the repo properly or the map lies.** Two ways the naive `basename(cwd)` fails, both
> observed on the first real run (3 of 6 sessions mis-mapped):
> - **A session working in a subdirectory.** `…/vista-cohort/app/backend` yields "backend", which
>   matches no board. Walk up to the git root (`git -C <cwd> rev-parse --show-toplevel`) and use
>   *that* basename.
> - **A sibling checkout.** `rad-eval-usage`, `vista_bench-covrefresh`, `vista-eval-apex-cmp` are
>   checkouts of `rad-eval`, `vista_bench`, `vista-eval`. Boards are **per repo, not per checkout**,
>   so strip the `-<slug>` suffix and fall back to the base repo's board. Confirm with the remote
>   (`git -C <path> remote get-url origin`) rather than guessing from the directory name.
>
> Two more states are **not** findings and must be labelled separately, or the check fires on them
> too:
> - **cwd is the workspace root** (`~/code`), which is not a git repo — so `rev-parse` fails and
>   there is no repo to match. Label it `workspace root (no repo)`. A session can legitimately be
>   working *on* a repo from here, and **there is no reliable way to link it to one**: no cwd, no
>   branch. State that limitation in the map rather than guessing, and read its board entry the
>   other way round — from the board, not from the session.
> - **subagent transcripts** (`agent-*.jsonl`) are not sessions. Exclude them.
>
> Do all of this before the "maps to no program" check can fire. Untested, that check mis-mapped
> **3 of 6** sessions on its first real run, and still flagged 3 of 7 after the repo-resolution fix
> — every one of them a labelling problem, not untracked work. A check that cries wolf on day one
> never earns its place in the digest.

**Briefs** — `…/planning/programs/<name>.md`. The `Stages` table and the `Decided already` ledger.

Emit one row per live session:

```
<session-id-8>  <repo> · <branch>  →  <program> stage N/M  →  <plan path>   [<ctx>k, <state>, last <MM-DD HH:MM>]
```

Resolve each session by matching its `cwd` and `gitBranch` against the board entries, then the
board entry's program against the briefs.

> ⚠ **A board block carries no branch, so session → *specific item* is not reliably resolvable.**
> The format is `<name> · program <brief> stage N/M · <state> · <date>` plus a plan pointer —
> nothing that names the branch the work lives on. So a repo with four live items and a session on
> one of them resolves to the *repo's* programs, not to which one. Say "rad-eval · one of 4 items"
> rather than asserting a stage you cannot know. If this ambiguity proves annoying in practice, the
> fix is one token on the board block (a `br:<branch>` field), not cleverer guessing here — but
> don't add it speculatively. **Degrade gracefully**: if a session maps to no board
entry, fall back to branch → nearest plan doc, and flag it (Phase 1). If the boards do not exist
yet, the map is still worth producing as session → branch → nearest doc — that already answers
"where do the docs live for this thing".

## Phase 1 — Watch (read-only)

Each check answers yes or no about a file or a process. No code, no diffs, no judgement calls.

| Check | Fires when |
|---|---|
| **stage-vs-git** | A board entry's stage disagrees with the newest commit on the branch it names. The board block's `<MM-DD>` **is** its last-verified stamp; an entry whose branch has commits newer than that date is unverified, not necessarily wrong. |
| **branch with no plan doc** | A live branch with commits that no plan doc on the mount or in the repo names. |
| **two sessions, one worktree** | Two live transcripts sharing a `cwd`. Genuinely dangerous — one session's reset destroys the other's uncommitted work. |
| **session on a Completed plan** | A live session whose branch's plan doc is marked `Completed`. Either the plan is stale or the work is redundant. |
| **session maps to no program** | A live session that resolves to no board entry. Untracked work, and exactly the higher-level thing worth catching. |
| **board over cap** | A board past 100 lines, or carrying an item marked landed. Means finished work is accumulating where only live work belongs. |
| **brief pointer broken** | `planning/check-brief-links.py` exits non-zero. Cheap, mechanical, and it catches a plan that moved or a stage number that drifted. |
| **plan handed over with no explainer** | A plan doc named by a **live board item** has no `<stem>.html` beside it on the mount. Phil does not read markdown, so that plan has not actually been handed over. Scope this to live items only — see below. |
| **session parked with room left** | A session `ListAgents` reports as `idle`, with room left in its window (Phase 2, not a fixed 300k), and whose next step is one of the procedural ones in Phase 2. This is the trigger that feeds Phase 2; on its own it is a finding, not an action. |

**Two checks are deliberately NOT implemented**, because both are false-positive factories and
would train Phil to ignore the digest:

- ~~"plan doc with no `Program:` line"~~ — only *live* plans are stamped, so this fires on the
  hundreds of frozen ones.
- ~~"uncommitted work with no live session"~~ — fires on every `docs/session/` note, which is
  git-ignored by design.

**Scope the explainer check to live items, and test existence only.** Swept across every plan on
the mount it is worthless: **411 of 413 plans** flag. Two numbers
explain why, and both are traps worth remembering:

- 220 have no `.html` at all — most are frozen plans nobody will ever reread.
- 191 have an `.html` older than the `.md`. That number is an artifact: copying a file onto the
  mount resets its mtime, so "`.md` newer than `.html`" measures the last copy, not staleness.
  **Do not use mtime for the explainer check.** Existence is a fact; mtime here is noise. That is
  the second way mtime lies on this setup — see the liveness warning in Phase 0.

Scoped to plans a live board item actually points at, it fires on a handful, and each one is a
plan Phil has been handed and cannot read.

**Retire a check by measured usefulness, not by one bad firing.** Keep a tally per check —
fired / useful — in the digest. Below about 90% useful over 20 firings, retire *that check* and say
so; do not retire the manager. Zero tolerance selects for checks that never fire, which is its own
failure.

## Phase 2 — Advance (mechanical only)

A session that has stopped short of an obvious procedural next step is the most common thing worth
fixing here, and the cheapest. Restarting it costs one short message. Leaving it parked costs a
whole tick of nothing happening, and Phil finds out when he next looks.

**The trigger is a parked session.** All three must hold:

1. `ListAgents` reports it **`idle`** — it finished its turn and stopped. Not `busy`, not `shell`,
   and never `waiting` (that one is stopped for a human — Phase 4, and advancing it is forbidden).
2. It has **room left** — context occupancy under roughly half the model's window, measured as in
   Phase 0. **Not a fixed 300k.** These sessions run on windows far larger than that:
   parked sessions have been observed carrying 407k and 387k in a single request, so the window
   is at least that and 300k was nowhere near full. An absolute ceiling benches healthy sessions.
   Infer the window from the largest occupancy you have actually observed, and never call a
   session over budget on a number you have not checked against its window.
3. Its next step is **procedural** — one of the rows below. Judgement is not procedural.
4. You have confirmed **which session it is** via `state.json`, not by reading its name.

A session that is `busy` is not parked, however long it has been running. Never interrupt one.

### What to advance to

Each row's condition is an **observable fact about a file or a process**, because the manager may
not read code or diffs and may not ask a session what it is doing.

| What you can see | Advance to |
|---|---|
| A plan doc with no `<stem>.html` on the mount | `/explain-plan <plan>` |
| Review clean, plan approved, a later stage still open in the brief | build the next stage |
| Context over budget | `/wrapup` |

**The three review skills are NOT advances. Never send one.** `/review-plan`,
`/review-implementation` and `/review-tests` each spawn Codex or a fresh Claude subagent — that is
real spend, which gate 4 below already forbids, and `claude_ops` reserves that budget for Phil
explicitly ("spending that budget is my call"). Two independent reasons, either one sufficient:

- **Cost.** They are expensive skills. Phil decides, not the manager.
- **They stall anyway.** `/review-plan` and `/review-tests` never silently default the reviewer,
  so a bare invocation stops on an `AskUserQuestion` the manager must not answer. The advance
  would buy a stalled session, not progress.

When a review is genuinely the next step, that is a **digest line**, not a message: name the
session, the plan, and the command including `--reviewer codex` or `--reviewer claude`, so Phil
can paste it if he wants to spend it.

**"Tests green" and "reviewed and clean" are not things the manager can see.** Any row phrased
that way is unusable: confirming it needs either the diff or a status request, and both are
banned. If the state of a review decides the next step, that is not a mechanical advance — put it
in the digest and let Phil judge it.

### How to advance — the mechanism

`SendMessage`, addressed to the name `ListAgents` prints for that session. One session, one
message, and the message is the command and nothing else:

```
SendMessage({to: "motor note embedding phase 1",
             message: "/explain-plan docs/plans/eval-run-vista-02-vistabench-ehr_code.md"})
```

Rules for the message:

- **Send the command, not an instruction to think about it.** "You look parked, consider
  generating the explainer" wastes a turn. `/explain-plan <plan>` starts the work.
- **Name the plan path explicitly.** The session may have compacted and lost it.
- **One advance per session per tick**, the same cap as a nudge.
- **Never explain the manager to the session.** It does not need to know this exists.
- **If the session is not in `ListAgents`** — Phil is driving it in a terminal — do not try to
  reach it. Put one line in the digest naming the session, the command, and the plan, so he can
  paste it.

### The safety rule that makes this safe

**An advance must be cheap AND produce only a file.** Both halves matter — file-only output on
its own is not enough:

- **Cheap** — no Codex run, no spawned subagent, no GPU, no API spend. That rules out all three
  review skills (above).
- **File-only output** — `/explain-plan` writes HTML to the mount, building writes code into a
  working tree, `/wrapup` writes a session note. None touch git history, so the worst case of a
  wrong advance is a wasted file, not a bad commit.

That is why `/commit-review` is **not** in the table even though it is often genuinely the next
step. It commits. It is gate 2, below.

**Stop and notify at exactly these gates**, and never advance past one:

1. **Plan approval** — a plan that needs Phil's sign-off.
2. **Commit / push** — anything entering git.
3. **Merge** — anything reaching `main`.
4. **Anything irreversible or costly** — a GPU launch, a destructive write, a publish, real spend.
5. **A question a task raised for Phil** — absolutely never advance past this. Codex and Claude
   adjudicate code between themselves; a question marked for Phil is not theirs and not the
   manager's.

## Phase 3 — Remind a session that drifted

Prose rules decay after a few turns and at compaction, so a session forgets its own standards
mid-task. The manager is the backstop: its own context is short and refreshed, so it still holds
the standing rules the drifting session has lost. Send a **targeted `SendMessage`** to that one
session — never a broadcast.

Worth a nudge:

- About to escalate a **trivial, reversible** question to Phil. Nudge the session to apply the
  materiality filter and decide it *itself*. **The nudge goes to the agent; the decision stays with
  the agent.** The manager does not supply the answer.
- Committing without the review path, or about to run `git commit` inline instead of
  `/commit-review`.
- Writing a decision or blocker only into a git-ignored `docs/session/` note, where no other
  session can see it. It belongs in the brief's ledger.
- Working on a stage the brief's ledger already settled — quote the dated entry.

One nudge per session per tick, maximum. A nagged session is a worse session.

## Phase 4 — Route questions to Phil, and answer none

The queue is **board state**, not the manager's memory. A session that needs Phil sets its own board
entry:

```
<name> · program <brief> stage N/M · ⛔ blocked-on-Phil · <MM-DD>
next: <the question> — consequence: <what changes either way> — default: <what it does if he shrugs> → <plan>
```

That shape is deliberate. It cannot scroll away under concurrent pings; it survives the manager
dying, because the state lives in the mount file and not in a context window; and it clears the
moment the asking session flips its own entry out of blocked.

**`ListAgents` finds the ones the board missed.** A session reported as **`waiting`** is stopped
for a human, and often its board entry does not say so. Confirm what kind of stop it is by reading
the last assistant message in its transcript before queueing it — of three `waiting` sessions
observed at once, one held a real question; the others were a tool-permission prompt and a stall
the manager caused. Never advance any of them, and never report a raw `waiting` count as a question
count. The board is still the durable queue — it survives the manager dying and
`ListAgents` does not — but a session that asked and forgot to write it down is exactly the kind of
silent block this whole design exists to surface.

The manager's job is a **filter over board states** — nothing more:

- The digest **leads with the open-question count and the questions themselves**. Status goes below
  the fold. If there are three questions waiting, that is the first thing on screen.
- A genuinely blocking question fires a **push notification** immediately.
- **Escalate with age.** A question open past a day gets louder in the digest — moved up, marked
  with its age. An old question must never become a quiet one.
- When Phil answers in the manager session, `SendMessage` the answer to the asking session verbatim
  and flip its board entry out of blocked. Route it; do not interpret it.
- Conflicts between sessions go through the same queue and are **never** auto-resolved.

## The digest

Overwrite one known path every tick: `…/planning/manager-digest.md`. One file, never appended, so
there is one place to look and no history to wade through.

**Lead with a heartbeat** — `last ran <time> · <N> checks · <M> suppressed · <K> sessions live ·
<A> advanced` —
so silence is never mistaken for all-clear. A digest with no findings and no heartbeat is
indistinguishable from a manager that died.

Order: heartbeat → questions for Phil (with ages) → confirmed findings → the map → the
fired/useful tally per check.

## What NOT to do

- **Don't answer a question raised for Phil.** The single hard rule.
- **Don't resolve a conflict between two sessions.** Name it and stop.
- **Don't poll the sessions.** The boards already say it, and their context is the scarce resource.
  `ListAgents` is not polling — it costs them nothing and you should call it every tick.
- **Don't interrupt a `busy` session**, however long it has been running. Only `idle` is parked.
- **Don't advance a `waiting` session.** It is stopped for a human — gate 5 if that is a question
  for Phil, and not yours to unblock either way.
- **Don't advance into git.** Every advance must produce a file, never a commit, push, or merge.
- **Don't guess who a `ListAgents` name is.** Resolve it through `state.json`. A misrouted advance
  costs the wrong session a turn and needs a correction on top.
- **Don't broadcast.** Every message targets one session for a confirmed reason.
- **Don't read code or diffs.** If a finding needs a diff to confirm, it is not a manager finding.
- **Don't advance past a gate** because the next step looks obvious.
- **Don't keep a check that cries wolf** — retire it on its measured tally and say so.
- **Don't trust a zero from a freshness check** you have not proven can return non-zero.
