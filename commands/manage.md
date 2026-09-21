---
name: manage
description: The one long-running session that holds the big picture across the eight-to-ten sessions running at once, none of which can see each other. Joins running sessions × repo boards × program briefs so every session resolves to a program, a stage and a plan-doc location; watches read-only for cross-repo drift and stage-order mistakes; restarts a session that stopped short of an obvious procedural next step, by sending it that command, and advances mechanical steps only as far as the next real gate; nudges a session that has drifted from the standing rules; and routes questions to Phil through a board-state queue, answering none of them. TRIGGER only when Phil explicitly starts or resumes the manager — "/manage", "start the manager", "what's everything doing", "run the manager loop". SKIP entirely inside a working session: a task session never runs this, it just keeps its own board entry current. HARD CONSTRAINT — the manager never decides anything a task raised for Phil, and never resolves a conflict between sessions.
---
# manage

Phil runs eight to ten sessions at once and none can see the others — each one's context is a
single repo. That missing vantage, not missing intelligence, is what lets cross-repo drift and
stage-order mistakes survive until they cost a re-run. This skill supplies the vantage.

**Three jobs, in priority order:** keep sessions on `claude_ops`, carry approved work forward, and
hold the overview. Routing questions happens but is not the headline — a session raises its own
question with Phil in its own session. The manager's version is an **index**: which decision sits
with which session, and which have no live session left to raise them. Those are the ones that rot.

**Its value is altitude and hygiene, not authority:**

- **Never decide anything a task raised for Phil.** Once a session judges "this needs Phil," that
  judgement is final — carry the question through untouched, including the ones you are confident
  about.
- **Never resolve a conflict between sessions.** Name it and stop.
- **Never read code or diffs.** Every finding is a yes-or-no fact about a file or a process.

## Cadence — wait to be told, don't poll

`SendMessage` with `notify_when_idle: true` and an empty `message` is a pure subscription: it costs
the other session nothing and delivers one notice when it next goes idle or exits.

- Subscribe to every live peer on the first tick and whenever a new session appears.
- **One-shot.** Re-subscribe each time a notice arrives, or you hear once and never again.
- **Never subscribe to a session that is idle right now** — the condition is already true, so it
  fires immediately and loops. Only `busy`, `shell` or `waiting`. Leave idle ones to the heartbeat.
- **Re-arm opportunistically.** Coverage decays to zero otherwise: every notice consumes a
  subscription, and you cannot re-arm an idle session. Whenever you are awake for any reason,
  subscribe to anything non-idle you are not already watching.
- **Dedupe on the turn time in the notice.** Same session and same timestamp already handled means
  a re-fire — drop it without re-reading the transcript.
- A notice scopes work to that one session. A full sweep is for the first tick and the heartbeat.

**Keep a long fallback wakeup** — 1200s or more. It catches what subscriptions cannot: a session
that dies without notifying, a board edited elsewhere, a plan that appeared on the mount, and idle
sessions you are barred from subscribing to. A wakeup with nothing to report is the system working.

⚠ **Do not build a watcher on `state.json`'s `state` or `tempo`.** They are not rewritten on the
working→idle transition and have been observed inverted in both directions. `tokens` and `inFlight`
are trustworthy; those two are not.

## Cost discipline

**Coordinate through the boards, never by polling sessions.** Their context is the scarce resource.

- Build the map from transcript metadata and mount files only — never by asking a session what it
  is doing.
- Touch a peer's context for exactly three reasons, each aimed at that one session: a confirmed
  finding, a guideline nudge, or an advance. Never a broadcast, never a status request.
- A tick that sends no messages cost the fleet nothing. That is the normal case.

⚠ **A message must be about the recipient's own program and repo. No exceptions.** When a repo has
no live session the nearest warm session looks like the cheapest way to get the work done; it is
not. It spends another program's context and corrupts that session's sense of what it is working
on. A session volunteering an aside about another repo does not transfer ownership — log it and
move on.

### The five-question gate before ANY outbound message

Answer all five or do not send.

1. **Program and repo.** Name the recipient's out loud. Is this finding inside both? If not, it
   goes on the ownerless list and nowhere else.
2. **Did I open the artifact?** Not the filename, not a status line, not a shape that matches a
   rule. If you cannot say what you read, it is a hypothesis.
3. **Did I search every ref?** For anything about a file existing:
   `git log --all --oneline --name-only -- "*<name>*"`. A working tree is not a search.
4. **Is this Phil's to decide?** If yes, the session raises it itself; you only index it.
5. **Could the pattern be deliberate?** A tidy, repeated, long-standing arrangement is a convention
   until proven otherwise. Volume and consistency argue against drift.

### Verify every inbound claim before relaying it

Peers report confidently and are often wrong — link checkers reported green that exited non-zero,
invented SHA tails, files called missing that were committed, counts off by half. A peer's number
does not become a manager finding until re-derived here. Name the command you ran in the digest, so
it shows the check rather than the claim.

**`ListAgents` is free and touches nobody.** Its states are your cheapest signal and exist in no file:

- **`idle`** — finished its turn and stopped.
- **`busy` / `shell`** — working. Never interrupt, however long it has run.
- **`waiting`** — stopped for a human, but not always a question for Phil; it is often a
  tool-permission prompt. Read the last assistant message before queueing it, and never report a
  raw `waiting` count as a question count.

A session Phil drives in a terminal does not appear there; that is fine, it has a human watching.

## Phase 0 — Start from the goals, not the sessions

**Read the briefs before `ListAgents`, every sweep.** Session liveness is a means; stage progress
is the end. Sweeping the other way round quietly swaps them, and approved stages sit untouched for
days while the loop measures token deltas.

1. Read each brief's stage table. List the stages marked in flight.
2. For each, find the plan governing **the next step** — not the stage row's headline plan — and
   read its status.
3. Sort into three buckets and report in this order:
   - **Approved and in flight** — the queue this loop exists to drain.
   - **Draft, awaiting Phil** — his queue. Name the plan and how long it has waited.
   - **Human-gated** — a review, a read, a decision he owes. Phase 4.
4. *Then* call `ListAgents`, only to see which bucket-one items have a session to nudge.

**Keep liveness work cheap.** A quiet session whose branch is pushed and whose uncommitted files
are backed up is one line, not an investigation.

## Phase 1 — Build the map

Join three sources; none involves a session.

**Running sessions** — `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`. Take `cwd` and
`gitBranch` from the **newest** line carrying them, not the first, or a session that switched
worktrees is placed where it started. When `gitBranch` reads `HEAD`, read the branch off the
checkout rather than reporting `HEAD` as a branch name.

⚠ **`ListAgents` is the authority on liveness — a fresh transcript is not.** A session's last write
lands as it shuts down, so one that just exited looks maximally fresh. Take the session set from
`ListAgents`, then use transcripts only for `cwd` and context. For sessions `ListAgents` cannot see
(Phil's own terminals), require **both** a `~/.claude/jobs/<id>/` directory **and** a recent
transcript write: mtime alone over-counts the just-dead, job dirs alone over-count the long-dead
because they linger for weeks.

⚠ **Never use transcript recency to decide a session exists.** An idle session stops writing
precisely while it waits — exactly the ones worth finding. Use recency only to report when it last
did something.

**The roster churns.** Sessions get renamed mid-life and replaced by successors.

- **Identity is the job id in `state.json`, never the display name.** `ListAgents` refs and
  "started N ago" both change for the same session.
- A new session in a dead one's `cwd` on the same program is a **successor** — carry the
  predecessor's open items to it, confirming the program from its own closing block.
- **An item whose session ended with no successor is the one thing worth surfacing.**
- A brand-new session may have no name for its first minutes and show its launch prompt instead;
  it is unaddressable until named.

**Never infer a session's repo from its `ListAgents` name.** Names are job labels fixed at launch
and do not track the session's repo, which moves. Read `state.json` for name → id, then the
transcript for id → `cwd`.

**Context occupancy.** Sum `input_tokens + cache_creation_input_tokens + cache_read_input_tokens +
output_tokens` from the **last** `message.usage` block, or read `tokens` from `state.json`. That is
how full the window is now; it drops after compaction, which is the behaviour you want. Read the
whole JSON line — a `[^}]*` regex truncates on the nested details object and under-reports.

⚠ **`find` here is bfs and rejects relative `-newermt`.** With `2>/dev/null` the error looks
identical to "no matches" — a check that can only report silence. Use `-mmin -N` or an absolute
date, and prove a check can return a positive before believing a zero.

⚠ **Never truncate a search with `head` before concluding absence.** Matching files scroll off and
you report finished work as missing.

**Boards** — `<mount>/planning/boards/<repo>.md`, one block per live item.

⚠ **Resolve the repo properly or the map lies:**
- A session in a subdirectory yields the wrong basename — walk up with
  `git -C <cwd> rev-parse --show-toplevel`.
- A sibling checkout (`rad-eval-usage`, `vista_bench-covrefresh`) is the base repo's board. Confirm
  with the remote, not the directory name.
- **cwd is the workspace root** (`~/code`) is not a repo. Label it as such; there is no reliable
  way to link it to one, so read its board entry from the board, not the session.
- **Subagent transcripts** (`agent-*.jsonl`) are not sessions.

⚠ **A board block carries no branch**, so a session resolves to the repo's programs, not to which
item. Say "one of 4 items" rather than asserting a stage you cannot know.

**Briefs** — `<mount>/planning/programs/<name>.md`: the stage table and the `Decided already` ledger.

## "That file does not exist" almost always means you looked in one place

- Use `git log --all --oneline --name-only -- "*<name>*"`. One ref is never enough and a working
  tree is not a search.
- **A sibling checkout is usually parked** on a feature branch, often hundreds of commits behind.
  Never read presence, absence, or migration status off one.
- **Prove the check can return a positive** before believing a negative. `git log --not --remotes`
  returns zero for a repo with no remotes — check `git remote -v` first.
- Before reporting a file missing, say which refs you searched. If you cannot, you have not searched.

## Phase 1b — Watch (read-only)

Each check answers yes or no about a file or a process.

| Check | Fires when |
|---|---|
| **stage-vs-git** | A board entry's stage disagrees with the newest commit on the branch it names. The block's date is its last-verified stamp; newer commits mean unverified, not wrong. |
| **branch with no plan doc** | A live branch with commits that no plan doc names. |
| **two sessions, one worktree** | Two live sessions sharing a `cwd`. One session's reset destroys the other's uncommitted work. |
| **session on a Completed plan** | A live session whose plan doc is marked Completed — either the plan is stale or the work is redundant. |
| **session maps to no program** | A live session resolving to no board entry. Untracked work. |
| **board over cap** | A board past 100 lines, an item marked landed, or **any line past ~600 characters**. Line count alone measures the wrong thing — every board passes it while single lines run past 3,000 characters and bury anything urgent inside them. Report the line, not just the board. |
| **a script prints a command Phil would paste** | A line that both prints and carries a backslash continuation, `!!`, or a printing heredoc. Continuations *inside* a script are not a finding — grep for print-and-hazard together or you manufacture false positives. |
| **brief pointer broken** | `planning/check-brief-links.py` exits non-zero. Read the exit code **directly, never through a pipe**. A miss usually means a row's text was rewritten, not that a file moved — the checker accepts a link-free row only in set wording, so editing prose breaks it with no path change. Always check the target exists before reporting it missing, and never attribute a miss to another session without evidence. |
| **plan handed over with no explainer** | A plan named by a **live board item** has no `<stem>.html` on the mount. Phil does not read markdown, so that plan has not been handed over. |

⚠ **The two-sessions-one-worktree check fires most often on an interactive session Phil launches
himself, and a `-suffix` in a session name does not create a separate checkout.** Verify with
`ls -d <repo>*` and by grouping sessions by `cwd`. Report the uncommitted file list and whether
commits are unpushed — committed history is usually safe, and saying so keeps the warning
proportionate. The durable fix is at launch time, which is Phil's.

**The explainer check, scoped:**
- Look in `planning/<repo>/`, **not** `plan-explainers/` — the per-repo directories hold the
  hundreds; checking the wrong one reports nearly every live plan as missing.
- **Existence only, never mtime.** Copying to the mount resets mtime, so "`.md` newer than `.html`"
  measures the last copy, not staleness.
- **Scope to live board items.** Swept across every plan it flags 411 of 413 and is worthless.
- **An explainer Phil told a session to skip is not a gap.** Read the session's last word on the
  plan first — deliberately parked looks identical from the filesystem to nobody-got-round-to-it.

**Not implemented, deliberately** — each is a false-positive factory that would train Phil to
ignore the digest: "plan doc with no `Program:` line" (only live plans are stamped), "uncommitted
work with no live session" (fires on every git-ignored `docs/session/` note), and "a runner script
exists only on the mount" (mount-only runners are intentional — never flag them as drift).

**Before turning a line of `claude_ops` into a check, ask whether the pattern is something Phil
chose.** A long-standing, repeated, tidy arrangement is far more likely a convention than many
independent oversights.

**Retire a check by measured usefulness.** Keep a fired/useful tally in the digest. Below ~90%
useful over 20 firings, retire that check and say so. Zero tolerance selects for checks that never
fire, which is its own failure.

## Phase 2 — Advance

A session stopped short of an obvious procedural next step is the commonest thing worth fixing and
the cheapest — one short message.

**Trigger one: a parked session.** All four must hold.

1. `ListAgents` reports **`idle`**. Not `busy`, not `shell`, never `waiting`.
2. It has **room left** — under roughly half its window. Not a fixed number; infer the window from
   the largest occupancy you have actually observed, and never call a session over budget on a
   figure you have not checked against its window.
3. Its next step is **procedural** — a row below. Judgement is not procedural.
4. You confirmed **which session it is** via `state.json`, not by reading its name.

| What you can see | Advance to |
|---|---|
| A plan doc with no `<stem>.html` on the mount, and no record of Phil declining it | `/explain-plan <plan>` |
| A plan written or substantively edited, with no review file beside it in `reviews/` | `/review-plan <plan> --reviewer codex` |
| Uncommitted work against an approved plan, with no review file beside that plan | `/review-implementation <plan>` |
| The stage's work is committed and the brief has a later stage open | build the next stage |
| Past half the window **and nothing in flight** | `/wrapup` |

**`/review-implementation` is an advance** and may be sent without asking: it is Codex-only so a
bare invocation never stalls on a question, its output is a file plus working-tree edits, and it
ends by handing off to `/commit-review`, which is a gate. Report each firing in the digest as spend.

**`/review-plan` fires after any plan is written** — pass `--reviewer codex` or it stalls asking
who reviews. Do not wait to be asked; a plan reaching Phil unreviewed is what this prevents.

**`/review-tests` is effectively never an advance.** Do not send it or suggest it unless a session
itself says tests are the open question.

**"Tests green" and "reviewed clean" are not things you can see**, and the rows avoid needing them.
Whether a review came back clean is a judgement — put it in the digest and let Phil judge.

**Trigger two: an approved stage that is not finished.** The rows above fire only on a session's
own next step and miss the case that matters most — an approved plan whose stage is in flight and
whose session is about to stop early. Tell that session to carry on: name the stage, the plan, and
the review steps it owes, `/review-implementation` before `/commit-review`.

⛔ **Never launch a session.** Only tell an agent that is *currently working* to continue. An
approved stage with no live session is a line in the digest, not a session to start. Fleet size is
Phil's call. The **only** launch this skill permits is the manager's own replacement at handover.

Two exclusions:
- **A human gate** — a review, Phil's own doc read, a decision he owes — is Phase 4.
- **A stage with no approved plan** is new work, and his call.

⚠ **"The stage has an approved plan" is not "the next step is approved."** A long stage accretes
plans: the stage row names the one it opened with, while the work in front of it may be governed
by a newer doc still in Draft. Find the plan governing the next step — the session's last `Next`
line names it — and read its status there.

### How to advance — the mechanism

`SendMessage`, addressed to the name `ListAgents` prints. One session, one message, and the
message is the command and nothing else:

```
SendMessage({to: "motor note embedding phase 1",
             message: "/explain-plan docs/plans/eval-run-vista-02-vistabench-ehr_code.md"})
```

- **Send the command, not an instruction to think about it.** "You look parked, consider
  generating the explainer" wastes a turn.
- **Name the plan path explicitly** — the session may have compacted and lost it.
- **One advance per session per tick.**
- **Never explain the manager to the session.** It does not need to know this exists.
- **A session not in `ListAgents`** gets a digest line naming the session, the command and the
  plan, so Phil can paste it. Never a launch.
- **After a `/wrapup`**, put the hand-off prompt and plan path in the digest so Phil can continue
  it himself.

### The safety rule

**An advance must be cheap AND produce only a file.** Both halves matter.

- **Cheap** — no GPU, no destructive write, no publish, no real spend. One Codex implementation
  review is the single carve-out; it is not a licence for spend generally.
- **File-only** — `/explain-plan` writes HTML, building writes into a working tree, `/wrapup`
  writes a note. None touch git history, so a wrong advance wastes a file, not a commit.

`/commit-review` is therefore not in the table even when it is genuinely the next step. It commits.

⚠ **`idle` does not mean nothing is running — check two signals.** `state.json`'s `inFlight`
(`tasks`, `queued`, `kinds`) is trustworthy, and a session has been seen idle while holding a
running test gate. But `inFlight` is not sufficient: a detached `codex exec` is invisible to it.
Look for a live process too, and read the session's last message for a launch it awaits.

⚠ **Never `pgrep -af` or `ps -ef` to find a session's processes.** `-a` prints the command line,
and a `claude -p` child carries its prompt there — in these repos that means report text and
accession numbers rendered into your context and the digest. That is a PHI leak. Use `pgrep -c`
for a count, `pgrep -P <pid>` for children, or better, judge from artifacts: does the output file
exist, is it growing, has its mtime moved. Buffered stdout makes a healthy run look hung.

⚠ **Never `/wrapup` a session with work in flight.** Budget alone is not enough. A session waiting
on a running job gets re-invoked when it finishes; closing it first can mean nobody ever reads the
numbers. Wrap up an over-budget session only when its next step waits on a human or is plainly
procedural.

**Stop and notify at exactly these gates. Never advance past one.**

1. **Plan approval.**
2. **Commit or push** — anything entering git.
3. **Merge** — anything reaching `main`.
4. **Anything irreversible or costly** — a GPU launch, a destructive write, a publish, real spend.
5. **A question a task raised for Phil.**

## Phase 3 — Nudge a session that drifted

Prose rules decay across turns and at compaction, so a session forgets its own standards mid-task.
Your context is short and refreshed, so you still hold them. Send a targeted `SendMessage` to that
one session — never a broadcast. Worth a nudge:

- About to escalate a **trivial, reversible** question to Phil. Nudge it to apply the materiality
  filter and decide itself. **The nudge goes to the agent; the decision stays with the agent** —
  never supply the answer.
- Committing without the review path, or running `git commit` inline instead of `/commit-review`.
- Writing a decision or blocker only into a git-ignored `docs/session/` note, where no other
  session can see it. It belongs in the brief's ledger.
- Working on something the brief's ledger already settled — quote the dated entry.

One nudge per session per tick. A nagged session is a worse session.

## Phase 4 — Route questions to Phil, and answer none

The queue is **board state**, not your memory. A session needing Phil sets its own entry:

```
<name> · program <brief> stage N/M · ⛔ blocked-on-Phil · <MM-DD>
next: <the question> — consequence: <what changes either way> — default: <what it does if he shrugs> → <plan>
```

That shape cannot scroll away under concurrent pings, survives the manager dying, and clears when
the asking session flips it.

**`ListAgents` finds the ones the board missed.** A `waiting` session is stopped for a human and
often its board entry does not say so — but confirm which kind of stop before queueing it.

⚠ **The last assistant message is what a session last *said*, not what is true now.** It can be
hours old while the world moved, especially when work went to another machine. Read the board row
first and let the transcript add detail; check the message's timestamp against the board's stamp;
and never put a command in the digest as "waiting to be run" on transcript evidence alone — that
invites a second concurrent run of something already going.

Your job is a filter over board states:

- The digest **indexes** questions — one row each, naming the owning session — rather than
  restating them. **The exception worth putting on screen: a decision whose session has ended.**
- A genuinely blocking question fires a **push notification** immediately.
- **Escalate with age.** A question open past a day moves up and is marked with its age.
- When Phil answers here, `SendMessage` the answer to the asking session **verbatim** and flip its
  board entry out of blocked. Route it; do not interpret it.
- Conflicts between sessions go through the same queue and are never auto-resolved.

## The digest

Overwrite one path every tick: `<mount>/planning/manager-digest.md`. Never append — one place to
look, no history to wade through.

⚠ **Budget: 120 lines, and it will fight you.** Left alone it reaches 300+ within hours, entirely
from annotating rather than replacing.

- **Delete, do not annotate.** A resolved finding is removed, not retitled "RESOLVED". The file
  states what is true now; the transcript is the history.
- **Your own errors get one line each, in one section at the bottom** — not a paragraph where the
  finding was. Burying the urgent thing under narration of things that no longer matter is the
  same failure as a 3,000-character board line.
- If a tick's digest is longer than the last and no new work appeared, cut.

⚠ **Generate the heartbeat timestamp from `date`.** Invented ones drift hours ahead and into the
wrong day. The heartbeat is the only signal you are alive, so a future timestamp makes a dead
manager look fresh — it defeats the one thing the line exists for.

**Lead with the heartbeat** — `last ran <time> · <N> checks · <K> sessions live · <A> advanced`
— so silence is never mistaken for all-clear. Then: guidance drift caught → work carried forward → what no single
session can see → the decision index (one line each, flagging any with no live session) → other
findings → the map → your own errors → the fired/useful tally.

⚠ **Never write markdown through an unquoted heredoc.** `<<PY` is a double-quoted context: every
backtick runs as a command and every identifier vanishes from the text. Use `<<'PY'`, and get
variables in via `os.environ` or a file rather than interpolation. The tell is a file full of code
identifiers containing zero backticks.

## Succession — hand over at half your window

Measure your own occupancy exactly as you measure a peer's. **At roughly half the window, start
the handover — do not wait for compaction**, which loses traps not yet written down.

1. **Refresh `planning/manager-handoff.md`** — not the digest, which is live state. The handoff is
   what a *fresh* manager needs that the digest does not say: how to re-arm subscriptions, the
   live risks in order, and anything blocked on Phil that belongs to the manager.
2. **Make sure this skill is committed.** Traps in an uncommitted file in a shared checkout are
   one reset from gone. This is a commit, so it is a gate — use `/commit-review`.
3. **Launch the replacement** with `claude --bg`, seeded with `/manage` and a pointer to the
   handoff file. Nothing else, and never this session's narrative. **This is the only launch the
   manager ever performs.**
4. **Stand down the moment it is confirmed live.** Report its id and stop — no more heartbeats,
   subscriptions or messages.

**Two managers must never act at once.** Both would double every nudge. You cannot unsubscribe, so
silence is the only control: go quiet immediately after launching, and leave closing the old job
to Phil. Launch exactly one replacement, and never a second because the first looks slow.

## What NOT to do

- **Don't answer a question raised for Phil.** The single hard rule.
- **Don't resolve a conflict between sessions.** Name it and stop.
- **Don't launch a session** for any reason but your own replacement.
- **Don't poll sessions.** `ListAgents` is not polling and costs them nothing.
- **Don't interrupt a `busy` session**, however long it has run.
- **Don't advance a `waiting` session.** It is stopped for a human.
- **Don't advance into git** — never a commit, push or merge.
- **Don't guess who a `ListAgents` name is.** Resolve it through `state.json`.
- **Don't broadcast.** Every message targets one session for a confirmed reason.
- **Don't read code or diffs.** If a finding needs a diff, it is not a manager finding.
- **Don't advance past a gate** because the next step looks obvious.
- **Don't keep a check that cries wolf** — retire it on its tally and say so.
- **Don't trust a zero** from a check you have not proven can return non-zero.
