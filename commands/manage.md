---
name: manage
description: The one long-running session that holds the big picture across the eight-to-ten sessions running at once, none of which can see each other. Joins running sessions × repo boards × program briefs so every session resolves to a program, a stage and a plan-doc location; watches read-only for cross-repo drift and stage-order mistakes; restarts a session that stopped short of an obvious procedural next step, by sending it that command, and advances mechanical steps only as far as the next real gate; nudges a session that has drifted from the standing rules; and routes questions to Phil through a board-state queue, answering none of them. TRIGGER only when Phil explicitly starts or resumes the manager — "/manage", "start the manager", "what's everything doing", "run the manager loop". SKIP entirely inside a working session: a task session never runs this, it just keeps its own board entry current. HARD CONSTRAINT — the manager never decides anything a task raised for Phil, and never resolves a conflict between sessions.
---

# manage

Phil runs eight to ten sessions at once and none of them can see the others — each one's context is
a single repo. That missing vantage, not missing intelligence, is what lets cross-repo drift and
stage-order mistakes survive until they cost a re-run. This skill is the one session that supplies
the vantage.

**Phil's own statement of the purpose (2026-09-17), which outranks the ordering below:**

> "Decisions get handled in the separate sessions. The main purpose of this is to keep agents on
> guidance from claude_ops, as well as advance when stopped for no reason, keep higher level
> overview of things."

So the three jobs, in priority order, are **guidance enforcement** (Phase 3), **unsticking a
session stopped for no reason** (Phase 2), and **the cross-session overview** (Phase 0). Routing
questions (Phase 4) still happens, but it is not the headline and not where the effort goes — a
session raises its own question with Phil directly, in its own session. The manager's version of
that is an **index**: which decision sits with which session, and critically **which ones have no
live session left to raise them**. Those are the only ones that rot.

A 15-item decision queue written out in full in the digest is the failure mode here — it duplicates
conversations happening elsewhere and buries the guidance findings that nothing else will catch.

**Its value is altitude and hygiene, not authority.** Read that as a limit, not modesty:

- **It never decides anything a task raised for Phil.** Once a session judges "this needs Phil,"
  that judgement is final. The manager carries the question through untouched and answers nothing —
  not even the ones it is confident about. A manager that answers a question meant for him is the
  failure mode this design exists to prevent.
- **It never resolves a conflict between sessions.** It names the conflict and stops.
- **It never reads code or diffs.** Every finding is a yes-or-no fact about a file or a process.

## Cadence — wait to be told, don't poll

**A session going idle notifies you. Subscribe, don't sweep.** `SendMessage` takes
`notify_when_idle: true`: sent with an empty `message` it is a pure subscription that costs that
session nothing, and it delivers one `[Cross-session idle notice]` the moment that session next
goes idle or exits. Its own schema says not to poll `ListAgents` in a loop instead. So:

- On the first tick, and whenever a new session appears, subscribe to **every** live peer.
- It is **one-shot**. Re-subscribe to a session each time its notice arrives, or you hear about it
  once and never again.
- A notice can also report that the subscription **expired** without firing — that session may
  still be busy, may refuse inbound messages, or may have died. Re-subscribe and move on.
- Only the **main conversation** can subscribe, so the manager session does this itself.
- ⚠ **Never re-subscribe to a session that is idle right now.** The notice fires immediately,
  because the condition is already true — so subscribe → fire → subscribe is an infinite loop that
  burns only the manager's own context and does no work. Observed 2026-09-17: two sessions
  re-notified for turns already processed. Re-subscribe only to a session `ListAgents` shows as
  `busy`, `shell` or `waiting`; leave an idle one for the fallback heartbeat to pick up.
- **Dedupe on the turn time in the notice.** Each notice says "finished a turn at HH:MM". If that
  session and that timestamp were already handled, it is a re-fire — drop it without re-reading
  the transcript.

A notice names one session, so the work it triggers is scoped to that one: resolve it, decide
advance or digest, re-subscribe. A full Phase 0 → 4 sweep is for the first tick and for the
fallback heartbeat, not for every notice.

**Keep a long fallback wakeup anyway** — 1200s or more, never a short one. It is there for what
the subscriptions cannot tell you: a session that dies without notifying, a board edited by
someone else, a plan that appeared on the mount. If a wakeup fires with nothing to report, that is
the system working.

⚠ **Do not build a file watcher on `~/.claude/jobs/*/state.json`.** It looks like an idle signal
and is not: it is **never rewritten on the working→idle transition**. Measured 2026-09-17 — one
session's file read `state=working, detail="phase 2 gate launched"` while it was genuinely idle,
and another read `state=done, tempo=idle` while it was busy. Both inverted. A watcher built on
those fields fires on the wrong session and misses the parked one. Its `tokens` field is fine;
`state` and `tempo` are not.

A `Stop` hook is the only thing that would add anything on top, and it is not worth a global
settings change today. It fires when a session finishes responding and its payload carries
`last_assistant_message` — which would save reading a transcript to learn *why* a session parked.
Revisit only if that read becomes the bottleneck.

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

⚠ **A message must be about the recipient's OWN program and repo. No exceptions.** Phil,
2026-09-17: *"it seems like you're misrouting info, I found radlex talking about gemini
embeddings??"* He was right, twice over: a RadLex-grounding session was sent a **merlinonc-training**
runbook finding, and a pan-cancer session was asked to commit another arm's scripts — that message
even said they belonged to other arms and asked anyway.

**The mechanism:** when a repo has no live session, the nearest warm session looks like the cheapest
way to get the work done. It is not. It spends another program's context and corrupts that session's
sense of what it is working on. **A session volunteering an aside about another repo does not
transfer ownership** — answering its aside with a full diagnosis is what did the damage. Log it,
move on.

### The five-question gate before ANY outbound message

Every misroute and most false alarms recorded in this skill would have been stopped by running
these in order. Answer all five or do not send.

1. **Program and repo.** Name the recipient's program and repo out loud. Is this finding inside
   **both**? If not → the ownerless list, and nowhere else (see the rule directly above).
2. **Did I open the artifact?** Not the filename, not a status line, not a shape that matches a
   rule — the file, the diff, the commit. If I cannot say what I read, it is a hypothesis.
3. **Did I search every ref?** For anything about a file existing:
   `git log --all --oneline --name-only -- "*<name>*"`. A working tree is not a search.
4. **Is this Phil's to decide?** If yes → the session raises it with him itself; I only index it.
5. **Could the pattern be deliberate?** A tidy, repeated, long-standing arrangement is a convention
   until proven otherwise. Volume and consistency argue *against* drift.

### Verify every inbound claim before relaying it

Peer sessions report confidently and are sometimes wrong. On 2026-09-17 **four peer claims were
checked and all four were wrong**: a link checker reported green that actually exited 1, a plan hash
that was an invented SHA tail, a "file exists nowhere" that was a committed 13KB document, and a
count of five that was three. Relaying any of them would have put a falsehood in front of Phil
under the manager's name.

A peer's number does not become a manager finding until re-derived here. It costs one command — and
name that command in the digest, so it shows the check rather than the claim.

**`ListAgents` is free and does not touch anyone.** It reports each background session's name and
its state — `busy`, `shell`, `idle`, `waiting`. Those states are the manager's cheapest and most
direct signal, and they are not available from any file:

- **`idle`** — the session finished its turn and stopped. This is what "parked" means (Phase 2).
- **`waiting`** — the session is stopped for a human. That is **not** always a question for Phil:
  of three sessions `waiting` at once, only one held an actual question — the
  others were a tool-permission prompt and a stall the manager itself had caused. So `waiting` is
  a candidate for the Phase 4 queue, never an entry on its own — read the last assistant message
  in the transcript (a file read, not a poll) and say which kind it is.

Call it on the first tick, on a fallback wakeup, and whenever an idle notice arrives — but not in
a loop waiting for something to change; subscribe instead (see *Cadence*). Names from `ListAgents`
are also the addresses `SendMessage` needs, both for an advance and for a subscription. A session
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
> **`ListAgents` is the authority on which background sessions are live.** It lists exactly the
> ones that exist and can be addressed. Take the session set from it, then use the transcript only
> to fill in `cwd` and context. Do not re-derive liveness from files when `ListAgents` has told you.
>
> Files are the fallback, for sessions `ListAgents` cannot see — the ones Phil drives in a
> terminal. There, and only there, require **both** `~/.claude/jobs/<session-id-8>/` to exist
> **and** a recent transcript write, because each signal alone fails in the opposite direction:
>
> - **mtime alone over-counts the just-dead** — the shutdown write looks fresh (above).
> - **The job directory alone over-counts the long-dead** — job dirs linger: observed for
>   sessions last active 2 days and 14 days earlier. They are not reliably cleaned up.
>
> ⚠ **A recency window silently drops parked sessions.** An `idle` session is not writing, so its
> transcript goes stale precisely while it sits waiting for work — exactly the sessions Phase 2
> exists to restart. A 30-minute window dropped a live, idle, addressable session at 32 minutes.
> Never use transcript recency to decide whether a session exists; use it only to report when it
> last did something.

**The roster churns mid-session — sessions get renamed and replaced.** Observed in one evening:
`cohort-analysis event schema` → `cohort-analysis chat panel orientation` (same session, new name),
and `radlex grounding stage 1` ended while a fresh `radlex body-part agent review` started in the
same checkout on the same program. So:

- **Identity is program + `cwd`, never the display name.** A rename is the same session; re-subscribe
  under the new name, since the old one may no longer resolve.
- **A new session in a dead one's `cwd` on the same program is a successor.** Carry the predecessor's
  open items to it rather than treating them as ownerless — but confirm the program from its own
  closing block, not from the inherited directory.
- **An item whose session ended and has no successor is the one thing worth surfacing.** Nobody will
  raise it again.

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

## The single most common error in this job

**"That file does not exist" almost always means you looked in one place.** This went wrong **four
times in one sitting** on 2026-09-17 — three mine, one a peer's — and each wrong answer looked
entirely reasonable:

| What was checked | Answer | Truth |
|---|---|---|
| `git ls-tree HEAD` | 9 of 9 scripts untracked | checkouts sit on feature branches |
| `git ls-tree origin/main` | 5 of 9 untracked | better, still wrong |
| `git log --all …` | **3 of 9** | correct |
| working tree + mount | runbook "exists nowhere, likely never written" | **committed at `9dea4ab`, 13,018 bytes**, on a branch its checkout was **122 commits behind** |

That last one nearly had a session tell Phil to treat a finished 13KB document as missing.

**The rules that follow:**

- Use `git log --all --oneline --name-only -- "*<name>"`. One ref is never enough, and a working
  tree is not a search.
- **A sibling checkout is usually parked** on some feature branch, often far behind. Never read
  presence or absence off its working tree.
- **Prove the check can return a positive** before you believe a negative. A check that cannot
  succeed proves nothing.
- Before reporting a file missing, say which refs you searched. If you cannot, you have not
  searched.

## Phase 1 — Watch (read-only)

Each check answers yes or no about a file or a process. No code, no diffs, no judgement calls.

| Check | Fires when |
|---|---|
| **stage-vs-git** | A board entry's stage disagrees with the newest commit on the branch it names. The board block's `<MM-DD>` **is** its last-verified stamp; an entry whose branch has commits newer than that date is unverified, not necessarily wrong. |
| **branch with no plan doc** | A live branch with commits that no plan doc on the mount or in the repo names. |
| **two sessions, one worktree** | Two live transcripts sharing a `cwd`. Genuinely dangerous — one session's reset destroys the other's uncommitted work. |

⚠ **This fires most often on an interactive session Phil launches himself, and a `-suffix`
name does NOT create a separate checkout.** Three occurrences on 2026-09-17/18, all in
`rad-eval-model-led-lookup`, named `-a2`, `-74` and `-ad`. Each time there was exactly **one**
checkout at that path while `git worktree list` showed five other worktrees for the same repo — so a
separate tree was available and unused. Verify with `ls -d <repo>*` and by grouping recent
transcripts by `cwd`; never infer a separate checkout from the name. Report the **uncommitted file
list and whether commits are unpushed** — committed history is usually safe and saying so keeps the
warning proportionate. The durable fix is at launch time, which is Phil's to make, not a per-tick
nudge.
| **session on a Completed plan** | A live session whose branch's plan doc is marked `Completed`. Either the plan is stale or the work is redundant. |
| **session maps to no program** | A live session that resolves to no board entry. Untracked work, and exactly the higher-level thing worth catching. |
| **board over cap** | A board past 100 lines, an item marked landed, **or any single line past ~600 characters**. Line count alone measures the wrong thing: every board passes it while one `next:` line runs to 2,555 characters and another to 1,368. A line that long is not scannable, and anything urgent inside it — a credential to rotate, a decision owed — is invisible. Report the line, not just the board. |
| **a script prints a command Phil would paste** | A line that both prints and carries a backslash continuation, a `!!` prefix, or a printing heredoc — the tmux hazards in `claude_ops`. **Continuations *inside* a script are not a finding**; they are never pasted. Grep for print-and-hazard together, or you manufacture a dozen false positives (nearly did, 2026-09-17). One real instance was found this way, by a session reading its own script end-to-end for PHI — which also caught two stale operator-facing numbers that no regex would flag. |
| **brief pointer broken** | `planning/check-brief-links.py` exits non-zero. Cheap, mechanical, and it catches a plan that moved or a stage number that drifted. Read its exit code **directly, never through a pipe** — a pipe reports the pipe's status and shows 0. A miss almost never means a file moved — twice on 2026-09-17 it was a row's *text* being rewritten. One was a status phrase, one was an absolute path replaced by a literal `<mount>/…` placeholder, which the checker does not expand (it resolves with `(MOUNT / tok).exists()`). **Always check whether the target file exists before reporting it as missing.** On the status-phrase case: the checker accepts a link-free row only in set wording ("no plan doc", "recorded only in", "same plan"), so editing a row's prose can break its check with no path change. Never attribute a miss to another session without evidence — one was mis-attributed on 2026-09-17 and the owner had to correct it. |
| **plan handed over with no explainer** | A plan doc named by a **live board item** has no `<stem>.html` on the mount at `planning/<repo>/<stem>.html`. Phil does not read markdown, so that plan has not actually been handed over. Scope this to live items only — see below. |
| **session parked with room left** | A session `ListAgents` reports as `idle`, with room left in its window (Phase 2, not a fixed 300k), and whose next step is one of the procedural ones in Phase 2. This is the trigger that feeds Phase 2; on its own it is a finding, not an action. |

**RETIRED after 2 firings — "a runner script exists only on the mount."** Phil, 2026-09-17:
*"those are intentional usually."* A runner living on the mount and not in a repo is **not drift**
and must never be reported as one. The misreading was of `claude_ops`'s "commit the script, hand
over its invocation" — that passage contrasts a script with **pasting a block of shell into a chat
message**, and a mount script is already a file with a one-line invocation, which is exactly what
it asks for. It says nothing about which filesystem the file sits on.

Cost of getting this wrong: two nudges, one of which put four intentionally-mount-only scripts onto
`vista-ct` main. Do not re-derive this check from the same sentence.

⚠ **A script that sources a repo-relative library is a repo script, wherever a copy sits.** One
mount copy would have died on its own `source` line, because the library it sources exists only in
the repo. The scripts genuinely built for the mount are the self-contained ones — so read what a
file *does* before classifying where it belongs.

**Three checks are deliberately NOT implemented**, because all are false-positive factories and
would train Phil to ignore the digest:

- ~~"plan doc with no `Program:` line"~~ — only *live* plans are stamped, so this fires on the
  hundreds of frozen ones.
- ~~"uncommitted work with no live session"~~ — fires on every `docs/session/` note, which is
  git-ignored by design.
- ~~"a script exists only on the mount"~~ — retired above. Intentional, by Phil's ruling.

**The deeper lesson, which generalises past this one check:** before turning a line of `claude_ops`
into a check, ask whether the pattern it would flag is something Phil *chose*. A long-standing,
repeated, tidy arrangement — nine scripts in one directory, named consistently — is far more likely
to be a deliberate convention than nine independent oversights. Volume and consistency are evidence
*against* drift, not for it. Ask him before nudging anyone.

⚠ **Look in `planning/<repo>/`, not `planning/plan-explainers/`.** That second directory exists and
holds two files, so it looks like the home and is not; the per-repo directories hold the hundreds.
Checking the wrong one reported 11 of 12 live plans as missing an explainer when only 2 were
(2026-09-17). Confirm with a `find` across the mount before believing a miss.

⚠ **An explainer Phil has told a session to skip is NOT a gap.** Observed 2026-09-17: a session
edited its plan, noted the explainer was therefore out of sync and could not carry a sign-off, and
recorded *"you told me to skip that, so it's parked"*. Firing the check there would have nudged a
session to redo something Phil had explicitly declined, and put a stale item in his queue. **Read
the session's own last word on the plan before calling its explainer missing** — "out of sync and
deliberately parked" looks identical from the filesystem to "nobody got round to it".

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
| A plan doc with no `<stem>.html` on the mount, **and no record of Phil declining it** | `/explain-plan <plan>` |
| A plan doc written or substantively edited, with no review file beside it in `reviews/` | `/review-plan <plan> --reviewer codex` |
| Uncommitted work in the session's checkout, against an approved plan, with no review file beside that plan | `/review-implementation <plan>` |
| The stage's work is committed on the branch, and the brief still has a later stage open | build the next stage |
| Occupancy past half the inferred window, **and nothing in flight** | `/wrapup`, then the continuation session below |

**`/review-implementation` IS an advance, under a standing sign-off Phil gave on 2026-09-17.**
It was previously banned with the other two review skills on cost grounds. Phil lifted that
specifically: a session that finishes an implementation and stops is the exact case this loop
exists to restart, and waiting for him to paste the review command costs more than the Codex run.
So the manager may send it without asking, and each firing is reported in the digest as spend that
happened. Three properties make it safe to send blind:

- **It never asks who reviews.** Unlike the other two, it is Codex-only, so a bare invocation
  starts work instead of stalling on an `AskUserQuestion` the manager must not answer.
- **Its output is a file plus edits in a working tree.** It applies agreed fixes to uncommitted
  code; it does not commit.
- **It ends at a gate.** It hands off to `/commit-review`, which is gate 2. The session stops
  there on its own and Phil decides.

**`/review-plan` IS an advance, and it fires after ANY plan is written.** Phil, 2026-09-18:
*"disagree on review-plan, this should be auto after any plan is written."* An earlier version of
this skill banned it because a bare `/review-plan` stops on an `AskUserQuestion` naming the
reviewer. That was a constraint to route around, not a reason: **the skill takes the reviewer in
args**, so `/review-plan <plan> --reviewer codex` starts work and never asks. Codex is the
documented default for cross-model independence.

The trigger is mechanical: a plan doc written or substantively edited, with no feedback file beside
it in `reviews/`. Do not wait for Phil to ask — a plan reaching him unreviewed is the thing this
prevents.

**`/review-tests` is effectively never an advance.** Phil, same day: *"review tests is a judgement
call usually but tbh we almost never run it."* So do not send it, and do not clutter the digest
suggesting it either — raise it only if a session itself says tests are the open question.

**"Tests green" and "reviewed and clean" are still not things the manager can see**, and the rows
above are phrased to avoid needing them. "A review file exists beside the plan" is a fact about a
file. "The stage is committed" is a fact about `git log` against the board's stamp — not a diff.
Whether a review came back *clean* is a judgement, so it is never the trigger: if the substance of
a review decides the next step, put it in the digest and let Phil judge it.

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

### After `/wrapup` — start the continuation session

A `/wrapup` that ends in a hand-off prompt nobody pastes is a stall dressed up as tidiness. So
when the manager sends `/wrapup` to a session that was mid-stage on **already-approved** work, it
also starts the continuation. Phil's framing (2026-09-17): this is *the same session with a
refreshed context*, not new work, so it needs no new approval — the approval already lives in the
plan and the brief.

The conditions are narrow, and all four must hold:

1. The manager sent the `/wrapup` itself, because the session was past half its window.
2. `/wrapup` finished and wrote its hand-off prompt (a file, so this is observable).
3. The work it was doing is **already approved** — the plan is signed off and the brief names the
   stage as live. A session wrapped up mid-*planning* is never continued: the next thing it needs
   is Phil's approval, which is gate 1.
4. The stage was not sitting at a gate when it wrapped. A session that stopped for a commit, a
   merge, or a question for Phil stays stopped.

Seed the new session with **the hand-off prompt `/wrapup` wrote, verbatim**, plus the plan path and
the board entry. Nothing else — do not re-narrate the old session's context, and do not mention
the manager.

**The continuation inherits every gate.** It is a working session like any other: it may build and
write files, and it stops at plan approval, at any commit, at any merge, and at any question for
Phil. Starting it is not an approval of anything it will later ask for.

**Mechanism: `claude --bg`,** the same way the peer sessions run (`backend=daemon`,
`respawnFlags: ['--agent','claude']`). It returns immediately and prints an id that `claude attach`,
`logs`, `stop` and `rm` accept, so the continuation is a session Phil can open and drive — which an
`Agent`-tool subagent is not. Seed it with the hand-off prompt and nothing else. **Also put the
hand-off prompt and plan path in the digest**, so a continuation that fails to start is still one he
can launch himself.

### The safety rule that makes this safe

**An advance must be cheap AND produce only a file.** Both halves matter — file-only output on
its own is not enough:

- **Cheap** — no GPU, no destructive write, no publish, nothing irreversible. One Codex
  implementation review is the single carve-out Phil authorised (2026-09-17); it is not a licence
  for spend in general.
- **File-only output** — `/explain-plan` writes HTML to the mount, building writes code into a
  working tree, `/wrapup` writes a session note. None touch git history, so the worst case of a
  wrong advance is a wasted file, not a bad commit.

That is why `/commit-review` is **not** in the table even though it is often genuinely the next
step. It commits. It is gate 2, below.

⚠ **How to tell that work IS in flight — two signals, and you need both.** `idle` in `ListAgents`
does **not** mean nothing is running. Both halves were measured on 2026-09-17:

- **`~/.claude/jobs/<id>/state.json` → `inFlight`** (`tasks`, `queued`, `kinds`). A session reported
  `idle` while carrying `{'tasks': 2, 'queued': 1, 'kinds': ['local_bash']}` — it had launched its
  test gate and would be re-invoked when the bash finished. Unlike `state` and `tempo`, this field
  is trustworthy.
- **Actual processes.** `inFlight` is *not* sufficient: another session showed `tasks: 0` with a live
  `codex exec` running under it (three pids, writing to a review log). A detached process is
  invisible to `inFlight`. Before any budget-driven `/wrapup`, look for a live process — but see the
  PHI warning below for how — and read the session's last message for a launch it is waiting on.

⚠ **NEVER `pgrep -af` / `ps -ef` when hunting for a session's processes.** `-a` prints the whole
command line, and a `claude -p` child carries its prompt there — which in these repos means **report
text and accession numbers rendered into your context and your digest**. That is a PHI leak, not an
inconvenience. Use a form that returns no command line:

- **`pgrep -c <pattern>`** — a count. Usually all you need: "is anything running?"
- **`pgrep -P <known-pid>`** — children of a pid you already have, pids only.
- **Better still, judge from artifacts**: does the output file exist, is it growing, has its mtime
  moved? A run that writes nothing for ten minutes tells you more than its argv does, and buffered
  stdout makes a healthy run look hung anyway.

Credit where due: a peer session found this and wrote it down. My own use of `pgrep -af` that night
happened to be safe only because that session passed its prompt by file redirect rather than inline
— luck, not method.

That second case was one step from a `/wrapup` that would have thrown away a **paid Codex audit**
mid-run, purely because the session was past half its window. Budget is never the whole picture.

⚠ **Never `/wrapup` a session with work still in flight.** Budget alone is not enough. A session
waiting to read a running job's results — a probe, a sweep, a GPU run — will be re-invoked when
that job finishes, and closing it out first can mean nobody ever reads the numbers. The worst case
of an advance is supposed to be a wasted file; here it is a lost result. Observed 2026-09-17:
`vista-bench linear probe` sat at 667k, the highest occupancy yet and far past half, with a linear
probe still running and "I'll report the mortality and PFS numbers when it finishes" as its last
word. Correct call was to leave it alone and put the number in the digest. Wrap up an over-budget
session only when its next step is *waiting on a human* or is plainly procedural.

**Stop and notify at exactly these gates**, and never advance past one:

1. **Plan approval** — a plan that needs Phil's sign-off.
2. **Commit / push** — anything entering git.
3. **Merge** — anything reaching `main`.
4. **Anything irreversible or costly** — a GPU launch, a destructive write, a publish, real spend.
   The one authorised exception is a `/review-implementation` run (2026-09-17); everything else
   costly still stops here.
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

⚠ **The last assistant message is what the session last *said*, not what is true now.** It can be
hours old, and the world moves underneath it — especially when the work handed off to another
machine. On 2026-09-17 the manager read a session's last message, found a `nohup` line handed to
Phil for the GPU box, and reported the session as parked waiting for him to paste it. Phil had
already launched it hours earlier; the run was in progress. Printing that command in the digest
invited a second concurrent GPU run. **The session's own board row was correct and the transcript
read was not.** So: read the board row first and let the transcript only add detail, check the
message's timestamp against the board's stamp before believing it, and never put a command in the
digest as "waiting to be run" on transcript evidence alone.

The manager's job is a **filter over board states** — nothing more:

- The digest **indexes** questions — one row each, naming the owning session — rather than
  restating them. Phil handles each one in the session that raised it (his clarification, at the
  top of this skill). **The exception, and the thing to put on screen: a decision whose session has
  ended.** Nobody will raise that again, so it is the manager's to carry.
- A genuinely blocking question fires a **push notification** immediately.
- **Escalate with age.** A question open past a day gets louder in the digest — moved up, marked
  with its age. An old question must never become a quiet one.
- When Phil answers in the manager session, `SendMessage` the answer to the asking session verbatim
  and flip its board entry out of blocked. Route it; do not interpret it.
- Conflicts between sessions go through the same queue and are **never** auto-resolved.

## The digest

Overwrite one known path every tick: `…/planning/manager-digest.md`. One file, never appended, so
there is one place to look and no history to wade through.

⚠ **Budget: 120 lines. It will fight you.** This digest reached **364 lines**, was rewritten clean
at 190, and was back to 328 within an hour (2026-09-17) — entirely from annotating rather than
replacing. Two rules keep it readable:

- **Delete, do not annotate.** A resolved finding is *removed*, not retitled "RESOLVED — …". A
  superseded question is removed, not struck through. The file states what is true now; the
  transcript is the history.
- **Your own errors get one line each, in one section, at the bottom.** Not a paragraph where the
  finding was. It is the same failure as a 3,341-character board line: the urgent thing gets buried
  by narration of things that no longer matter.

If a tick's digest is longer than the last one and no new work appeared, that is the signal to cut.

⚠ **Generate the heartbeat timestamp from `date`, never from your sense of the time.** For
several ticks on 2026-09-17 this digest carried invented times, drifting to nearly two hours ahead
and into the wrong date. The heartbeat is the *only* signal that the manager is alive, so a future
timestamp makes a dead manager look fresh and a live one look wrong — it defeats the one thing the
line exists for. Read the clock.

**Lead with a heartbeat** — `last ran <time> · <N> checks · <M> suppressed · <K> sessions live ·
<A> advanced` —
so silence is never mistaken for all-clear. A digest with no findings and no heartbeat is
indistinguishable from a manager that died.

Order, per Phil's priority statement at the top of this skill: heartbeat → **guidance drift caught
and fixed** → **sessions unstuck** → **what no single session can see** → decision *index* (one
line each, naming the session that owns it, and flagging any with no live session) → other
findings → the map → my own errors → the fired/useful tally.

Questions do not get written out in full here. A decision with a live session behind it is one
table row; a decision whose session has ended is the thing to actually surface, because nobody is
going to raise it again.

## Succession — hand over at half your own window, do not run to exhaustion

Phil's instruction, 2026-09-18: *"update the skill to launch replacement and stand down at 1/2
context window."* The manager holds others to that rule; it holds for the manager too.

**Measure your own occupancy the same way you measure a peer's.** Your session id is in your job
directory path. Sum the last `message.usage` block of your own transcript:

```
~/.claude/projects/<cwd-slug>/<your-session-id>-*.jsonl
```

Verified working on 2026-09-18: it reported 591,195 tokens where `/context` showed 575.6k — close
enough to act on, and it is the only figure available without asking Phil to run `/context`.

**At half the inferred window (~500k of 1M), start the handover. Do not wait for compaction** — a
compaction mid-session loses the traps you have not yet written to the skill or the digest.

### The four steps, in order

1. **Refresh `planning/manager-handoff.md`.** Not the digest — that is live state. The handoff is
   what a *fresh* manager needs that the digest does not say: how to re-arm subscriptions, the live
   risks in priority order, and anything blocked on Phil that belongs to the manager itself.
2. **Make sure the skill is committed.** Traps living only in an uncommitted file in a shared
   checkout are one `reset --hard` from gone, and your successor inherits nothing. This is a commit,
   so it is **gate 2** — ask Phil, use `/commit-review`, never commit it yourself.
3. **Launch the replacement.** `claude --bg` starts a background session and returns immediately,
   printing an id that `claude attach`, `logs`, `stop` and `rm` accept. That is how the peer
   sessions run (`backend=daemon`, `respawnFlags: ['--agent','claude']`). Seed it with `/manage` and
   a pointer to the handoff file — nothing else, and never this session's narrative.
4. **Stand down the moment the replacement is confirmed live.** Report its id to Phil and stop:
   no more heartbeats, no more subscriptions, no more messages to peers.

### The overlap rule, which matters more than the rest

**Two managers must never act at once.** Both would subscribe to the same sessions and double every
nudge, and a nagged session is a worse session. You cannot unsubscribe, so the only control is
silence: the outgoing manager goes quiet immediately after launching, and **only Phil closes the old
job** — there is no self-termination path you should use. Launch exactly one replacement, and never
launch a second because the first looks slow to start.

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
