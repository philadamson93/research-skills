---
name: manage
description: The one long-running session that holds the big picture across the eight-to-ten sessions running at once, none of which can see each other. Joins running sessions × repo boards × program briefs so every session resolves to a program, a stage and a plan-doc location; watches read-only for cross-repo drift and stage-order mistakes; advances mechanical steps to the next real gate; nudges a session that has drifted from the standing rules; and routes questions to Phil through a board-state queue, answering none of them. TRIGGER only when Phil explicitly starts or resumes the manager — "/manage", "start the manager", "what's everything doing", "run the manager loop". SKIP entirely inside a working session: a task session never runs this, it just keeps its own board entry current. HARD CONSTRAINT — the manager never decides anything a task raised for Phil, and never resolves a conflict between sessions.
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
- A peer session's context is touched **only** when sending it a confirmed finding or a guideline
  nudge aimed at that one session. Never a broadcast. Never a status request.
- If a tick sends no messages, it cost the fleet nothing. That is the normal case.

## Phase 0 — Build the map (the lead value)

Join three sources. All three are cheap and none involve a session.

**Running sessions** — `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`. Each line carries `cwd`,
`gitBranch`, `sessionId` and `timestamp`; `message.usage.output_tokens` accumulates the spend; the
file's **mtime is last activity**. A session is live if its transcript was touched inside the tick
window. Take `cwd` and `gitBranch` from the **newest** line that has them, not the first — a session
that switched worktrees mid-run would otherwise be placed where it started. `gitBranch` frequently
reads `HEAD` (detached, or a worktree); when it does, read the branch off the checkout itself
rather than reporting `HEAD` as if it were a branch name.

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
<session-id-8>  <repo> · <branch>  →  <program> stage N/M  →  <plan path>   [<tokens>k, last <MM-DD HH:MM>]
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

**Two checks are deliberately NOT implemented**, because both are false-positive factories and
would train Phil to ignore the digest:

- ~~"plan doc with no `Program:` line"~~ — only *live* plans are stamped, so this fires on the
  hundreds of frozen ones.
- ~~"uncommitted work with no live session"~~ — fires on every `docs/session/` note, which is
  git-ignored by design.

**Retire a check by measured usefulness, not by one bad firing.** Keep a tally per check —
fired / useful — in the digest. Below about 90% useful over 20 firings, retire *that check* and say
so; do not retire the manager. Zero tolerance selects for checks that never fire, which is its own
failure.

## Phase 2 — Advance (mechanical only)

For a session whose next step is procedural, advance it. Judgement is not procedural.

| State | Advance to |
|---|---|
| Uncommitted implementation, tests green | `/review-implementation` |
| Reviewed and clean, plan approved, stage open | build the next stage |
| Over context budget | `/wrapup` |

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

**Lead with a heartbeat** — `last ran <time> · <N> checks · <M> suppressed · <K> sessions live` —
so silence is never mistaken for all-clear. A digest with no findings and no heartbeat is
indistinguishable from a manager that died.

Order: heartbeat → questions for Phil (with ages) → confirmed findings → the map → the
fired/useful tally per check.

## What NOT to do

- **Don't answer a question raised for Phil.** The single hard rule.
- **Don't resolve a conflict between two sessions.** Name it and stop.
- **Don't poll the sessions.** The boards already say it, and their context is the scarce resource.
- **Don't broadcast.** Every message targets one session for a confirmed reason.
- **Don't read code or diffs.** If a finding needs a diff to confirm, it is not a manager finding.
- **Don't advance past a gate** because the next step looks obvious.
- **Don't keep a check that cries wolf** — retire it on its measured tally and say so.
- **Don't trust a zero from a freshness check** you have not proven can return non-zero.
