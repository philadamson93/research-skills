Reference: claude_ops.md
Program: `<mount>/chaudhari_lab/phil/planning/programs/planning-layer.md` — stages 1-6 of 6

# A planning layer above plan docs, and moving plans off git

**Status: Completed** (2026-09-16) — all seven stages landed. Stage 0 @892ffb5 · Stage 1 @22ae467 (paper-trail symlink @09f8905) · Stages 2-4 on the mount (7 briefs, 12 boards, 1,377 plan files copied, 30 plans stamped) · Stage 5 @788882e · Stage 6 @6e1afc2. Approved 2026-09-14 (Phil), Reviewed: Yes. Live status now lives in the program brief at `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/programs/planning-layer.md`, not here.

## Goal

Give every piece of work a written answer to "why are we doing this, and what stage are we at",
and stop paying a PHI review on documents that carry no patient data.

The motivation, the measurements behind it, and the decisions already taken are in the program
brief named at the top of this file. Read that first — it is the one-page version. This document
is only the how.

Scope is the six repos in active use: **vista-eval, vista_bench, vista-ct, rad-eval, paper-trail,
agentic-label-opt** — 262 plan docs, 467 review docs, 117 rendered explainers, spread over 127
checkouts. `research-skills` is in scope for the skill changes but its own plans stay in git.

| Repo | Plan docs | Reviews | Explainers | Checkouts | Remote |
|------|----------:|--------:|-----------:|----------:|--------|
| vista-eval | 94 | 182 | 47 | 51 | VISTA-Stanford org |
| vista_bench | 81 | 155 | 38 | 35 | VISTA-Stanford org |
| vista-ct | 45 | 35 | 4 | 15 | VISTA-Stanford org |
| rad-eval | 27 | 71 | 22 | 19 | personal |
| agentic-label-opt | 5 | 16 | 4 | 6 | personal |
| paper-trail | 10 | 8 | 2 | 1 | personal |
| **Total** | **262** | **467** | **117** | **127** | |

Nobody on the org reads these plan docs on GitHub (Phil confirmed), so moving new work off git
costs no visibility. And the existing 262 are **not** deleted — they stay frozen in git (already
reviewed, so free where they sit) and get copied to the mount for cross-project context. The PHI
saving is on *new* work: from Stage 4 on, plans and reviews are authored on the mount and never
enter git, so they never cost a review.

Seven stages (0-6). Stages 0 and 1 each land on their own; 2 to 5 are sequential; the manager
(Stage 6) needs only the boards from Stage 3.

## Approach

### Stage 0 — Fix the mount-delete hook (urgent, lands alone, unblocks the rest)

This is the one part blocking daily work *today*, and it has to come first because Stages 2-4 write
to the mount constantly. The current gate (`hooks/mnt-delete-gate.sh`) fires whenever a command
contains the literal string `/mnt` **and** any destructive verb, with no check on the actual
target — so `mkdir -p <mount>/boards && rm -rf /tmp/scratch` nags, and so does every `cp x
<mount>/ && rm scratch`. It nags on safe writes and, worse, it *misses* the genuinely dangerous
`rm -rf docs/plans/` that resolves through a symlink to the mount (no `/mnt` string in the command).

Rewrite it to be target-bound: extract each destructive verb's path argument, resolve it with
`realpath -m`, and then — **DENY** outright for the protected bucket roots (the catastrophic
whole-bucket-delete case, which is the entire reason the hook exists); **PASS** for targets inside a
named write-zone allowlist (`planning/`, `session-docs/`, `plan-explainers/`, the `tmp/` dirs);
**ASK** only for a mount delete *outside* the zone. This nags far less and is strictly safer than
the string match — a prototype tested against eight real commands passed the safe writes, denied the
bucket roots. (It also catches a delete that resolves onto the mount through *any* symlink — a
latent case even though the copy-only Stage 4 no longer creates one — which the string-matching gate
waves through.)

### Stage 1 — Standing rules in `claude_ops.md`

Edits to one file, each with immediate effect on every session in every repo, since 39 repos
symlink this file.

**(a) A close-out block after every chunk of work, not just at session end.** Today the only
structured summary comes from `/wrapup`, which fires once per session. Phil's complaint is that
after a block of work finishes he has to scroll and ask "what did we do, what's the stopping
point, what's next". Add a standing rule: at the end of any implementation, verification or
review block, print exactly this, and nothing decorative around it:

```
Program  <name> — stage 3 of 5
Done     <what concretely finished>
Verified <the command and what it printed>
Next     <the one next action>
Yours    <the decision needed from Phil, or "none">
```

Same five labels every time so it is readable at a glance rather than parsed.

**The block writes, it does not only print** (research finding, planning + memory surveys). A
terminal print dies with the session — the next session cannot read it, which is the very reason
Phil loses the thread across sessions. So the block's side effect is to upsert this item's board
entry (stage 3) and, when the `Yours` line recorded a decision, append one dated line to the
brief's `Decided already` ledger. That single change gives the decision ledger its otherwise-missing
writer: without it, nothing appends to the ledger and it freezes on the day it was hand-typed —
worse than useless, because a session reading a frozen ledger concludes nothing has been decided
since. This is the highest-value single mechanism the research surfaced.

**(b) A materiality filter on questions.** Phil gets asked things he doesn't care about, and
sometimes questions get invented to fill a section. Three tiers, stated as a rule:

- Changes the results, the cost, or what we can conclude → ask him.
- Changes only the shape of the code → decide it, record it in the plan, don't ask.
- Reversible in under an hour → just do it.

Plus a hard test: every question must name what changes in the outcome depending on the answer,
*and* the default that gets taken if he shrugs. Being unable to name the consequence is proof it
should not be a question. Options must describe outcomes, never mechanisms — that part already
exists in the file and only needs sharpening.

**(c) `## Open Questions` may legitimately be empty.** The header stays — it is an identifier
parsed by three skills and present in 2,018 plan docs, so it must not be renamed or removed. But
the template will state that "None — the defaults below are mine to make" is a valid and often
correct body. This is the structural cause of invented questions: a required section with nothing
real to put in it.

**(d) The plan template gains a `Program:` line** directly under `Reference:`, naming the brief
and the stage, as this file demonstrates.

**(e) Repair paper-trail so it actually receives the above.** `paper-trail/docs/claude_ops.md` is
a real 181-line file, not a symlink, and predates the 2026-09-11 rewrite — so it has been missing
standards updates for a while and would miss all of stage 1. Replace it with a symlink to the
canonical file like the other 39 repos. That is one commit in paper-trail, and it changes the
standards that repo operates under, so it is worth Phil knowing rather than doing silently.
(`contrastive-3d-onc` has the same defect; it is not in the active six and stays on the backlog.)

**(f) Every plan doc gets its explainer generated automatically, and the HTML is the review
surface.** Phil does not read markdown. Today `/explain-plan` is invoked on request and the
markdown is the default review path, which means the artifact he actually reads is the optional
one. Invert it: a standing rule that any plan doc written or substantively edited is handed over
*with* its explainer already generated — on this VM, already copied to the mount where he can open
it. Nothing else about the plan template changes. The trivial-plan exception takes care of itself,
because trivial changes do not get plan docs at all under the existing rules.

### Stage 2 — The brief format, and a brief per live program

A brief is one page, and its shape is fixed: **Why** (one paragraph, plain English, no file or
function names), **Done when**, **Stages** (a table: number, stage, repo, status, plan link),
**Decided already** (dated one-liners), **Order and dependencies**, **Not doing**.

The `Why` paragraph carries the whole point of the format. If it mentions a function name it has
failed, because the thing being protected is the part Phil can still read in two weeks.

`Decided already` is the ledger that stops decisions being re-litigated. Every entry is dated and
one line. When a session proposes something that contradicts an entry, that is a flag, not a
fresh question.

Work: enumerate what is actually in flight, which means reading the 140-line memory index, the
per-repo boards, and the unmerged branches across the six repos; group them into programs; write
one brief each. Estimate 10-15 briefs across the six. Then add the `Program:` header line to the
plan docs that belong to each — only the live ones, not all 262.

Briefs live at `<mount>/chaudhari_lab/phil/planning/programs/<name>.md`. `vista-pm` gets a
symlink `docs/programs` pointing there so the hub answer holds from inside a repo.

### Stage 3 — One status board per repo

`<mount>/chaudhari_lab/phil/planning/boards/<repo>.md`. One screen, hard cap. Per active item, one
block and no more:

```
<name> · program <brief> stage 3/5 · <state> · <MM-DD>
next: <one line> → <pointer to the plan>
```

`docs/next.md` in each repo becomes a two-line pointer at the board. The 8,600-word "Earlier
context" log in vista-eval's copy is dropped, not migrated — it duplicates the plan docs and git
history. paper-trail has no `docs/next.md` and no plan index at all, so there the board is
bootstrapped from its branches and plan docs rather than stripped from an existing tracker.

The reason this fixes the divergence is mechanical: a mount path is not per-checkout, so all 51
vista-eval checkouts, all 35 vista_bench checkouts and the Mac read one file instead of many.

### Stage 4 — Copy plans to the mount and author new ones there

No deletion, no untracking from git, no symlink — Phil's call, and it removes the only dangerous
step the plan had. Two moves:

1. **Copy** every repo's existing `docs/plans` tree (plans, reviews, `.html`) to
   `<mount>/chaudhari_lab/phil/planning/<repo>/`, non-destructively, and verify file-by-file
   (count + checksum). Two reasons: it gives the manager (Stage 6) and any session one place to
   read across all six projects, and it seeds the location new work uses. The git originals stay
   exactly where they are, frozen — already committed and already reviewed, so they cost nothing
   sitting there.
2. **Author new plans, reviews and explainers on the mount path** from now on, not in `docs/plans`.
   They never enter git, so they never cost a PHI read — the whole point, landing where it matters
   (going forward). On each substantive save, keep the canonical filename stable and drop a dated
   snapshot in `<stem>/history/` (OQ1's resolution: filename-based history, not bucket versioning —
   Phil: "trivial to add version to filename").

What this trades against the old migrate-and-symlink design: **nothing dangerous happens.** No
`git rm`, no symlink across 127 checkouts, and the two symlink defects found by test — ripgrep
returning zero plan files, and `rm -rf docs/plans/` deleting the real tree through the link —
simply do not exist, because there is no symlink. The cost is a transition period where plans live
in two places: the frozen old ones in each repo's git `docs/plans`, the live ones on the mount. That
split is exactly what Stage 5 teaches the skills — search the mount for current work, fall back to
git `docs/plans` for frozen history. Day to day nobody greps for a plan anyway; the board and brief
are the index.

Because there is no symlink, the in-repo `docs/plans/<name>` path does not resolve for *new* plans,
so their `Reference:` breadcrumb and links point at the mount path. Existing plans keep their
in-repo paths untouched. `research-skills` is excluded throughout — its plans stay in git, where
the plans are the public product.

### Stage 5 — Teach the skills the new layer

- **`/next`** — read the board and the brief first, and lead the response with program and stage
  rather than with a repo and branch. Today it reads five committed trackers, three of which will
  no longer be the truth.
- **`/wrapup`** — Step 2's Reviewed column keys on a content hash, not a git SHA. Step 3 edits the
  board instead of `next.md`. Step 6's cross-repo index moves from `vista-pm/personal/` (which is
  Mac-only and absent on this VM, so the cross-repo view does not currently exist here at all) to
  the mount, where it works on both machines. Step 9's resume block gains program and stage.
- **`/explain-plan`** — the two failures Phil named. Add a program panel at the top: where this
  plan sits, what is done, what it waits on. Lead with the why and the stage, and cut machinery
  until the motivation is the first thing on screen. Swap the git-SHA staleness anchor for a
  content hash. It also stops being opt-in: per stage 1(f) it runs on every plan, so its own
  "when not to use" guidance narrows to plans that never existed as documents.
- **`/read-plan`** — retire its promotion path. It exists to open the markdown in Phil's default
  `.md` app and then record `Reviewed: Yes`; since he doesn't read markdown, an approved in-sync
  explainer becomes the *only* route to that promotion. The skill stays usable for opening a file,
  but `/wrapup` Step 2's rule is rewritten to name one promotion path instead of two.
- **`/review-plan`** — check the `Program:` header resolves and the stage is real; apply the
  stage-1 materiality filter to what it surfaces for adjudication.
- **`/land`** — update the brief's stage row and prune the board entry as part of landing.
- **`/phi-vet`** — note that `docs/plans` is gitignored in the six repos, so the per-doc human
  read now covers a much smaller set. The keyword gate still fires on any staged markdown; that
  behaviour is unchanged and out of scope here.

### Stage 6 — The manager: holds the big picture, advances, reminds, and decides nothing Phil should

Phil runs eight to ten sessions at once, none able to see the others — each one's context is a
single repo. That missing vantage, not missing intelligence, is what lets cross-repo drift and
stage-order mistakes go unnoticed until they cost a re-run. The manager is one long-running session
that supplies the vantage. It merges what were two ideas (a driver that advances, a watcher that
observes). **Hard constraint (Phil): it never makes an important decision a task raised for him.**
Once an individual task judges "this needs Phil," that judgement is authoritative — the manager
passes it through untouched and answers nothing. Its value is altitude and hygiene, not authority.

Five jobs, and the line between them is the whole design:

**1. Holds the big-picture map — the lead value.** It answers "what are the eight things I'm working
on, and where does each fit" by joining three things it already reads: the running sessions (from
transcript last-activity mtime, working dir, and token spend), the boards, and the briefs. Each
session resolves to a row — *this session is on `feat/x`, which is item 3 on the vista-eval board,
stage 4 of the matched-cohort program, plan at `<mount path>`*. With the layer built that is
program-and-stage; before it exists the map degrades gracefully to session → branch → nearest plan
doc or `next.md`, which still answers "where do the docs live". A running session that maps to **no**
board or brief is itself a flagged inconsistency — untracked work — which is exactly the higher-level
thing worth catching.

**2. Watches for high-level inconsistencies (read-only).** Cross-repo drift, stage-order violations,
a board that disagrees with git, two sessions changing one behaviour from opposite ends. Never reads
diffs or code. Surfaces every one as a checkable fact, resolves none.

**3. Advances mechanical steps.** For a session's ready work: uncommitted implementation →
`/review-implementation`; clean and approved → build the next stage; over budget → `/wrapup`. Runs
on the `/loop` skill so Phil need not type `/advance`. This is procedural progress only — it stops
and notifies at the real gates (plan approval, commit/push, merge, anything irreversible or costly),
and it never advances *past* a question a task raised for Phil.

**4. Reminds an agent that drifted from guidance.** The cross-session answer to the research's
sharpest finding: prose rules decay after a few turns and at compaction, so a session forgets its
own standards mid-task. A separate manager holding the guidelines nudges the one drifting session
back — a `SendMessage` to that session, not a broadcast — and its own short, refreshed context does
not decay the same way. This is why the enforcement fork was safe to answer "prose first": the
manager is the backstop. It **includes** nudging an agent that is about to escalate a trivial,
reversible question to instead apply the materiality filter and decide it itself — the nudge goes to
the agent, the decision stays with the agent. The manager never makes the call. (This replaces the
earlier "manager answers trivial questions" job, which Phil ruled out — the manager deciding things
is exactly the risk.)

**5. Routes questions to Phil, and answers none.** Any question a task marked for him reaches him
untouched, through a **board-state queue plus a push for the urgent ones** (Phil's choice). The
session sets its own board entry to `blocked-on-Phil: <question, consequence, default>`; the
manager's "for you" list is a *filter over board states*, so it cannot scroll away under concurrent
pings, it survives the manager dying (the state lives in the mount files, not the manager's context),
and it clears automatically when answered. The digest leads with the open-question count and the
questions themselves, status below the fold; a genuinely-blocking one also fires a push immediately,
and one left open past a threshold escalates — so an old question gets louder, not quieter. Phil
answers in the one manager session; the manager routes each answer to the asking session and flips
its board state out of blocked. Conflicts are surfaced the same way and never auto-resolved — the
research is blunt that auto-resolving cross-session conflicts is where fleets break.

The watcher findings are yes-or-no facts: a branch with no plan doc; two sessions on one worktree; a
session on a Completed-plan branch; a running session mapping to no program; and the highest-value
one — a board whose stage disagrees with the newest commit on the branch it names, so every board
entry carries a last-verified timestamp. Checks retire by measured usefulness (below ~90% over 20
firings), not by a single false alarm — zero-tolerance selects for checks that never fire (Google's
Tricorder runs ~5% false positives deliberately). Two tempting checks are false-positive factories
and are scoped or cut before launch: "no `Program:` line" (only live plans get it) and "uncommitted
work, no session" (fires on every `docs/session/` note). The digest overwrites one known path and
leads with a heartbeat (last ran at T, N checks, M suppressed) so silence is not read as all-clear.

It coordinates through the boards, not by polling peers — reading eight sessions every tick would
burn their context to learn what the boards already say. So the manager needs Stage 3 (the boards)
but nothing after it, and can be built early. Mechanism: the `/loop` skill on a self-paced interval,
`SendMessage` for a targeted reminder or a routed answer, a push notification for what needs Phil.
No new infrastructure.

## Files to Modify

- `claude_ops.md` — stage 1, edits (a) through (d). Canonical; 39 repos symlink it.
- `hooks/mnt-delete-gate.sh` — stage 0, rewrite from string-match to realpath-resolved zones. Plus
  a new case in `hooks/tests/gate_tests.sh` for the symlink-`rm -rf` the old gate missed.
- `paper-trail/docs/claude_ops.md` — stage 1(e), replace the stale real copy with a symlink.
- `commands/next.md` — stage 5.
- `commands/wrapup.md` — stage 5, Steps 2, 3, 6 and 9.
- `commands/explain-plan.md` — stage 5. The largest edit: 577 lines today, and the program panel
  plus the altitude change touch its template and its drift check.
- `commands/review-plan.md` — stage 5.
- `commands/read-plan.md` — stage 5, retire the promotion path.
- `commands/land.md` — stage 5.
- `commands/phi-vet.md` — stage 5, one note about the gitignored plan path.
- `commands/manage.md` — **new file**, stage 6, the always-on manager (advance + watch + remind).
  Subsumes what were two separate files (a driver and a watcher).
- `docs/plans/README.md` — add this plan's row.
- `scripts/copy-plans-to-mount.sh` — **new file**, stage 4, a non-destructive copy+checksum of each
  repo's `docs/plans` tree to the mount. No symlink, no untrack. `research-skills/scripts/` does not
  exist yet and will be created.
- `<mount>/chaudhari_lab/phil/planning/programs/*.md` — stage 2, new briefs. Directory created
  2026-09-14.
- `<mount>/chaudhari_lab/phil/planning/boards/*.md` — stage 3, new boards. Directory created.
- `<mount>/chaudhari_lab/phil/planning/<repo>/` — stage 4, the six migrated plan trees.

- `<repo>/docs/next.md` × 6 — stage 3, reduced to a pointer; **created** for paper-trail, which
  has none.

## Open Questions

Both design forks the research surfaced are now **resolved** by Phil (2026-09-14) and moved to the
brief's decision ledger — recorded here so a fresh reader sees them settled:

- **Rule enforcement:** ship the close-out block and question filter as prose in `claude_ops.md`
  first; measure how often they actually lapse in real sessions; add a Stop hook or output-style
  enforcement only if they do. The block's write-to-board side effect partly self-corrects, so
  prose is the cheap starting point. (The research says prose behavioral rules decay after a few
  turns and at compaction — this accepts that and instruments it rather than pre-building machinery.)
- **No rigor tiers.** Phil's call: these are all research projects and all still need to be correct,
  so a `shared`/`exploratory` split is a distinction without a difference. `/advance` runs one gate
  policy for every repo — no `Tier:` line, no per-repo lookup. This *simplifies* Stage 5 and 6.

Both are now resolved by Phil (2026-09-14):

**1. Versioning — resolved.** Don't depend on the bucket. On each substantive save, keep the
canonical filename stable and drop a dated snapshot in `<stem>/history/`. ("trivial to add version
to filename.") This also gives the change-since-last-review layer real history to diff against.

**2. Org visibility — resolved.** Nobody reads the plan docs on GitHub, so there was no cost to
weigh — and the copy-only Stage 4 leaves the git originals in place anyway, so even that is moot.

No open questions remain.

## Verification

**Stage 1.** No code, so the check is behavioural and runs on the next real session: a session
that finishes a block prints the five-line block unprompted, and a plan authored afterwards has a
`Program:` line and either real open questions or the explicit "none" — and arrives with its
explainer already generated and a mount path to open it, without Phil asking for one. Phil judges whether the
questions that reach him name consequences. For 1(e), `readlink paper-trail/docs/claude_ops.md`
must resolve to the canonical file and `diff` against it must be empty. Nothing else to run.

**Stage 2.** Every brief's stage table links to a plan doc that exists — a script resolves every
link and must report zero misses. Every live plan doc has a `Program:` line resolving to a brief
that exists: `grep -L '^Program:'` over the live set must come back empty. And the readable test,
which is the real one: Phil reads two briefs cold and can say what the program is for without
opening anything else.

**Stage 3.** Each of the six boards is under 100 lines. `docs/next.md` in each repo is under 10
lines. Reading the board from three different vista-eval checkouts returns byte-identical content
— that is the check that the fork is actually gone, and it must be run from three separate
checkouts, not asserted.

**Stage 4.** Per repo, after the copy: file count on the mount equals file count in `docs/plans`,
and every checksum matches — the copy is non-destructive, so a mismatch just means re-copy, nothing
is lost. Then author one new plan at the mount path and confirm its `Reference:` breadcrumb resolves
and a dated snapshot lands in `<stem>/history/`. The git originals are untouched (`git status`
clean, unchanged), which is the check that we did *not* accidentally untrack.

**Stage 5.** Run `/next` in vista-eval and confirm the first line names a program and a stage.
Run `/explain-plan` on one plan and confirm the program panel renders and the motivation is above
the fold. `hooks/tests/gate_tests.sh` must still pass.

**Stage 6 (the manager).** Two checks, run over one day against the real eight-session load. For the
*advance* half: every stop was one Phil would have wanted, and nothing irreversible — spend, a
destructive write, a GPU launch — happened between stops (the count of stops is not the check; that
just measures the counter). For the *watch* half: score every finding true or false and record the
per-check useful/not-useful tally; a check below ~90% useful gets retired, not the whole manager.
It must cost nothing measurable — no peer session's context is touched unless a confirmed finding or
a guideline reminder was sent to that one session.

## Landing & cleanup

- Branch `feat/planning-layer` in `research-skills`. This is a large rewrite of standing rules, so
  it does not go straight on `main` despite the repo's usual doc-fix convention.
- Stage 0 (the hook fix) lands first and alone, straight on `research-skills` main after review —
  it is a self-contained safety fix with its own test, and every later stage depends on writing to
  the mount without the gate nagging.
- Stage 1 can land on its own once reviewed; it has no dependency on the mount layout. Land it
  first so the standing rules are in force while the rest is built. Its paper-trail half is a
  separate one-commit change on that repo's `main`.
- Stages 2-4 touch no code in `research-skills` — they write to the mount (briefs, boards, the
  non-destructive plan copy). No `.gitignore` edits and no untracking, since the copy-only Stage 4
  leaves git alone.
- The manager (Stage 6) lands after Stage 3 at the earliest, since it reads the boards; it does not
  need Stages 4 or 5.
- Stage 5 lands on `feat/planning-layer` after Stage 4, because the skills must point at the final
  layout. `/read-plan`'s promotion path retires in the same commit that makes the explainer the
  sole approval route, so the two never disagree about what counts as reviewed.
- Must be true before merge: `/review-plan` run on this doc and its findings applied; stage 4's
  copy checksum actually run and its output recorded, not asserted.
- Retired afterwards: the `docs/next.md` bodies in six repos, the 8,600-word log in vista-eval's
  copy, and `vista-pm/personal/in-flight.md` as the cross-repo index once the boards replace it.
  This plan's row in `docs/plans/README.md` gets marked Completed, and the brief's stage table
  goes to all-landed.
