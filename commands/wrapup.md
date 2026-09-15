End-of-session cleanup. Do the nine steps below in order.

**Open with a one-line context header naming the repo and current branch** — e.g. `research-skills · main` (add the worktree path when you're in a non-primary checkout: `research-skills · feat/foo · .claude/worktrees/foo`). Phil launches sessions across ~50 repos and multiple worktrees of the same repo, so stating *where you are* up front makes it unambiguous which checkout the cleanup and commit gate act on. Derive it from `git worktree list` + `git branch --show-current`, and repeat it in the Step 9 summary so the landed state is self-documenting.

## When to invoke

Recommended cadence: invoke around **~200k tokens of context** (or earlier at a clean cutoff), preserve session state, then start a fresh session with `/next`. Long sessions past that point get noticeably slower (cache misses on every turn, drift in long-tail context) and the marginal value of staying in-session keeps falling.

`/wrapup` is **state-preservation first, commit second**. Its job is to leave the next session everything it needs to resume — the repo's board and the brief it names (both on the mount), `MEMORY.md`, `docs/session/` docs, and the resume block — none of which require a commit. Committing is **opt-in** at the Step 9 gate and defaults to *skip*: reserve it for work that is finished and worth sharing (per `claude_ops.md` → When to commit). Ending a session mid-workflow on a token budget is the common case, and it needs no commit — so no commit-time PHI gate fires — with the resume block plus the git-ignored `docs/session/` docs carrying the state forward. (Not committing is not license to relax authorship discipline: never write raw PHI into any doc, git-ignored ones included — see `claude_ops.md` → What gets committed.)

## Scope

**Recently-touched docs only.** Pass over `docs/` files you edited or created this session, or files modified since the last commit on the current branch (use `git diff --name-only` and `git status` as fallbacks when session memory isn't enough). Do **not** do a full-tree doc consolidation pass here — that's a deliberately separate, heavier-context task.

## Asking discipline

Use judgment and act. Raise an `AskUserQuestion` only when a call is **both high-importance and genuinely ambiguous** — e.g., an irreversible structural move with real downside risk, or a fork in convention where reasonable choices conflict. Routine cleanup, inline rewording, normal pruning, and obvious bootstrapping decisions are yours to make. *Asking by default is the wrong posture for this skill.*

## Step 1 — Reorg pass on recently-touched files (docs and code dirs)

For each `docs/` file you touched this session:

- Skim for stale content, duplication, bloated sections, content sitting in the wrong file, unclear ordering.
- **Tighten inline** — typo fixes, dead-link cleanup, redundant-paragraph removal, light rewording for clarity, section-header renames.
- **Small-to-moderate reorgs are encouraged when they clearly help findability**: split a bloated doc into focused files, move a section to a doc where it belongs better, merge two docs that should be one, restructure a list, reorder major sections. Update inbound links when you move content. The asking discipline above governs the rare high-stakes ambiguous cases (e.g., renaming a doc that's heavily linked from external repos or external systems).
- **Out of scope here**: full-tree consolidation, gathering scattered content from many untouched docs, large architectural reorganizations of `docs/` as a whole. Defer to a separate, deeper-context skill (or note the opportunity on the board / in `backlog.md` for a future pass).
- Goal: optimize for *future-agent findability*. You're reorganizing for your own sake on the next session, not for a human reader.

**Also glance at any code directory you touched this session** (same recently-touched, no-full-tree scope): if it has drifted into a flat dump of unrelated files, propose a small, in-scope split and update inbound imports/references. Placement should have been settled at plan time (`claude_ops.md` → Writing code) — this is the retrospective safety net, not a substitute for it, so keep the move small and note it in the commit message.

Update any plan/status tables (e.g., `docs/plans/README.md`) if work shipped or got promoted to a plan doc this session. *Review-status sync is handled separately in Step 2.*

## Step 2 — Plan-doc review-status sync

If the project has a plan-tracking index (`docs/plans/README.md` or equivalent), maintain a **Reviewed** column with three values:

- `Yes` — the user approved the plan's **rendered explainer** and that explainer is in sync with
  the plan's current content.
- `No` — never reviewed.
- `Stale` — was `Yes`, but the plan has been substantively edited since.

**Staleness is measured against a hash of the plan's own content, not a git SHA.** Plans are now
authored on the shared mount and never enter git, so most of them have no commit to anchor to. Use
the same hash the explainer records in its own header, so the two agree by construction.

**Sync rules during wrapup**:

- **New plan doc created this session** → ensure README row exists with `Reviewed: No`.
- **Existing plan doc substantively edited this session** ("substantive" = content/section changes; *not* typo fixes, formatting, dead-link cleanup, or whitespace): if the row is currently `Yes`, demote to `Stale`. If `No` or `Stale`, leave as-is.
- **Never silently promote `No` / `Stale` → `Yes`.** There is exactly **one** promotion path: an
  approved explainer whose content hash matches the plan. `/read-plan` no longer promotes anything
  — Phil does not read markdown, so opening the markdown is not a review. If he says inline that
  he reviewed a plan, ask which artifact he read; if it was the explainer, record it, and if the
  explainer is out of sync, regenerate it first.
- **No plan-tracking index exists, but `docs/plans/` (or equivalent) does**: bootstrap a `README.md` with `Plan | Status | Reviewed | Description` columns and populate `Reviewed: No` for all existing plan docs.
- **No `docs/plans/` directory at all**: skip this step.

Surface unreviewed plans (`No` or `Stale`) in the Step 9 summary so the next session can pick them up.

## Step 3 — Board hygiene (this repo's status board on the mount)

The repo's board is the authoritative statement of what is live here:
`/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/boards/<repo>.md`. It lives on the mount, so
one file serves every checkout of the repo and the Mac. Edit it directly — it is not in git, so
this costs no review.

Upsert the entry for whatever you touched this session, in the board's own format:

```
<short name> · program <brief-slug> stage N/M · <state> · <MM-DD>
next: <one line> → <path to the plan, or "no plan doc">
```

- **Only active items.** When something finishes, take it **off** the board — its status lives in
  the brief's stage table, which is the historical record. A board that accumulates finished work
  is the failure this replaced.
- **States**: `▶` in flight, `⛔` blocked (say on what in the `next:` line), `○` not started,
  `⚠` ran but the result cannot be trusted yet.
- **Hard cap: one screen, under 100 lines.** If it does not fit, something on it is finished or was
  never really active.
- **Also update the brief** when the stage moved: set the stage row's status, and if the user made
  a real decision this session, append one dated line to the brief's `Decided already` ledger. That
  ledger is what stops the same decision being re-argued next month, and this step is its only
  writer.
- **Don't grow the in-repo `docs/next.md`.** It is legacy: a committed file edited inside many
  checkouts, which is why vista-eval's existed in 8 different versions across 9 checkouts. If it
  still holds real content, move that content to the board rather than updating both.

## Step 4 — Backlog hygiene (`backlog.md` or equivalent)

If a separate backlog file exists (e.g., `docs/backlog.md`), apply the same pointer discipline: prune items actually finished, promote items into the immediate-tracking doc when priorities have shifted, leave the rest as terse pointers.

If no backlog file exists but the immediate-tracking doc has a "Deferred / Backlog" or similar section that has grown unwieldy, bootstrap a separate backlog file by migrating that section out. Note the migration in the commit message so it's traceable. Per the asking discipline, only raise a question if the right destination file is genuinely ambiguous (e.g., the project has multiple plausible homes for it).

**Contract for both the board and `backlog.md`**: short, structured indexes. Substance lives in `docs/plans/`, `docs/journal/`, `docs/specs/`, or wherever the project keeps it. If you're writing more than ~3 lines per item, promote the detail and leave a pointer.

## Step 5 — Auto-memory pass

Update `MEMORY.md` to reflect the current project state, open items, and any new preferences or facts learned this session. Evict stale entries. Save new memories per the auto-memory rules in the system prompt — do not duplicate facts already covered by `CLAUDE.md` or derivable from the code.

## Step 6 — Cross-repo view (nothing to maintain)

**There is no separate cross-repo index any more, and nothing to do in this step beyond Step 3.**

This used to be `vista-pm/personal/in-flight.md` — Mac-only, git-ignored, and absent on the VM, so
the cross-repo view did not exist on this machine at all. It is now the set of per-repo boards on
the mount, which both machines read. Step 3 already upserted this repo's board, so the cross-repo
picture is current the moment that write lands.

Deliberately *not* a single combined file. One file covering ten programs is exactly how the old
tracker reached 706 lines. To read across projects, list the boards directory; to answer "which of
my checkouts do I pick back up", read the boards and the briefs they name.

If `vista-pm/personal/in-flight.md` still exists on the Mac, it is retired — stop updating it, and
say so once in the Step 9 summary so it does not quietly drift alongside the boards.

## Step 7 — Global skills sync (separate repo)

The user's global skills live in their own git repo, which is **a different repo from the project being worked on** — it has its own commit gate and its own push target. There are often TWO related paths to consider:

- **Runtime cache** — `~/.claude/commands/` and `~/.claude/skills/`. These are what Claude Code loads at session start. Often its own local git repo, but may accumulate untracked drift since the canonical source is elsewhere.
- **Canonical repo** — a user-maintained git repo with a GitHub remote, often named `*-skills` / `claude-skills` / `research-skills` and located under the user's `~/Documents/` or projects directory. Authoritative source of truth.

**Detection:**
1. Always check the runtime cache: `git -C ~/.claude/commands status --short` (and `git -C ~/.claude/skills status --short` if that path exists).
2. Check the canonical repo if one exists. Look for `~/.claude/canonical-skills-repo` (a single-line file containing the absolute path to the canonical repo). If that pointer file doesn't exist, fall back to scanning common locations (`find ~/Documents -maxdepth 4 -type d \( -name 'research-skills' -o -name 'claude-skills' \) 2>/dev/null | head -5`) and surface a candidate via `AskUserQuestion` if exactly one match is found. If zero or many, skip and surface in Step 9 summary as "no canonical skills repo detected."
3. If the output is empty in all candidate paths, **skip this step silently** — nothing to sync.

**Sync direction matters.** Edits often happen in the runtime cache (because that's what Claude Code is reading from), but the canonical repo is the source of truth that gets pushed to GitHub. Before committing, copy your session edits from the runtime cache → canonical:

```bash
cp ~/.claude/commands/<file>.md <canonical-repo>/commands/<file>.md
# (or cp ~/.claude/skills/<name>/SKILL.md → <canonical-repo>/commands/<name>.md
#  if the canonical repo uses the flatter `commands/<name>.md` convention)
```

Then commit + push in the canonical repo. Optionally cp the canonical version back to the runtime cache to keep them in sync (so the next session reads the same content the remote has).

If non-empty AND any of the changed files were touched by you this session (cross-check against your edit log; do not commit unrelated drift the user may have stashed there for their own reasons):

Raise an `AskUserQuestion` with three options:

1. **"Commit and push global skills" (Recommended)** — commit your session changes and push to the configured remote in one action.
2. **"Commit only (no push)"** — create the commit locally; defer the push.
3. **"Skip"** — leave global-skills changes uncommitted; flag in the Step 9 summary as needing attention.

Based on the answer:

- *Commit and push* / *Commit only*: stage only the files you touched (`git -C <repo> add <file1> <file2>`; do **not** use `git -C <repo> add -A`), then commit with a short single-line thematic message describing what changed (e.g., `review-plan: fold in the fresh-session-readiness check`). No AI attribution lines, matching the project commit-message convention. Push only if the option chosen requires it.
- *Skip*: do nothing; surface in Step 9 summary.

The `-C <path>` form keeps the project's cwd intact; do not `cd` into the skills repo.

**Why a separate gate from Step 9:** two independent repos, two independent push targets. The user might want to push the project but defer the skills sync, or vice versa. One gate per repo.

## Step 8 — Write the session state doc (`docs/session/`)

The resume loop's **write side**. Because commit is opt-in and most sessions close uncommitted (Step 9 gate), the `docs/session/` state doc — not a commit — is what carries this session's substance to the next one. The resume block below points at it, and `/next` (Phase 1 + Phase 4) reads it to resume; if this step doesn't write it, that pointer dangles and the loop never closes.

For each in-flight task advanced this session, write (or update) a state doc at `docs/session/<task-slug>-readback.md` — `mkdir -p docs/session` first if the dir is absent. Match `<task-slug>` to the resume block's DOC / OPEN lines so the pointer resolves. Capture the substance a fresh session needs to resume without re-deriving it from git:

- **Where things stand** — what was done this session and the current state of the work.
- **What's next** — the recommended first concrete action, plus the remaining steps.
- **Open questions / blockers** — anything unresolved or waiting on the user.
- **Key coordinates** — branch / worktree, relevant file paths, the plan-doc pointer, and any verification run + its result.

**Authorship discipline applies unchanged**: never write raw PHI (patient identifiers, sample rows, report text) into the state doc. Git-ignoring controls *commit* exposure, not what may be written — the standing rule that Claude never echoes PHI into any doc applies to git-ignored files exactly as to committed ones (`claude_ops.md` → What gets committed).

**Mechanics**: `docs/session/` is git-ignored — edit it in place; never stage or commit it. In a guarded background session where direct edits to a sibling checkout are blocked, write to scratch and `cp` it in (Bash isn't guarded).

**Skip** only for sessions that advanced no resumable work (pure doc-tweak, vista-pm-only) — the same sessions that skip the resume block.

## Step 9 — Summary + commit gate (opt-in)

**Summarize as bullet points** (not a paragraph). Lead with the `<repo> · <branch>` context header (per the top-of-skill note), then use these headings; omit any that are empty:

- **Shipped this session**: what concretely landed (1–3 bullets).
- **Doc changes worth flagging**: any moderate-or-higher reorgs from Step 1 — file splits, cross-doc moves, doc merges, major section reorders, new files bootstrapped. Skip if all doc work was inline tightening.
- **Plans needing review**: any rows currently `No` or `Stale` in the plan-tracking index after Step 2 — name the path so the next session can run `/explain-plan <path>` — the only thing that can record a review. Skip if all plans are `Yes` or no plan-tracking index exists.
- **Next**: what comes after this session (1–3 bullets).
- **Blocked on user**: things the next session can't unblock itself (1–3 bullets).

**Then raise an `AskUserQuestion` at the commit gate** with three structured options. Commit is **opt-in** — the default is to skip it and let the resume block + `docs/session/` docs carry state forward. Only offer commit as the recommended choice when this session's changes reached a **finished, shareable state** (per `claude_ops.md` → When to commit): an approved plan, a completed and verified implementation, or results ready to hand off. For the common mid-workflow / budget-out close, skip.

1. **"Skip commit" (Recommended for a mid-workflow close)** — don't commit; leave changes in the working tree. State is preserved by the board, the brief, `MEMORY.md`, `docs/session/`, and the resume block. Nothing is staged, so no commit-time PHI gate fires.
2. **"Commit and push"** — commit the changes and push to the tracking remote in one action. Choose this when the work is finished and worth sharing.
3. **"Commit only (no push)"** — create the commit locally; defer the push.

Recommend the option that matches the session's state (Skip for mid-workflow, Commit for a milestone), and put it first. Inline free-text yes/no is the wrong shape here — the answer space is enumerable; structured choices are clearer and faster. This single gate replaces what would otherwise be two asks (commit gate here + push gate inside `commit-review`).

**Based on the user's answer**:
- *Skip commit*: end the wrapup flow without invoking commit-review.
- *Commit and push*: invoke `commit-review` with `args: "push-authorized"`. Signals that the push decision has already been gated, so commit-review skips its own main-push prompt.
- *Commit only*: invoke `commit-review` with `args: "no-push"`. Commit-review commits and skips the push step entirely.

Do not auto-commit. Do not run `git commit` inline — always go through `commit-review`, which handles the appropriateness review and project commit conventions in one step. `docs/session/` is git-ignored, so readbacks and session docs there are never staged for a commit regardless of the choice above.

### Resume block — print last, always

**Open it with the program and the stage**, then the repo and branch — e.g.
`per-CT landmark tasks · stage 5 of 9 · vista_bench · feat/foo`. That is the line that survives
into the next session, and "which program, which stage" is the question worth answering first.
Name the brief's path too, so the next session can read the why without re-deriving it.

After the commit gate resolves (whether or not you committed), the **final output** is a copy-paste **resume block** — the coordinates the next session uses to pick the work back up without re-deriving it from git. Most sessions close **uncommitted** (commit is opt-in), so the block defaults to pointing at the working tree and `docs/session/` docs in this checkout; the pushed-SHA form applies only when this session committed at a milestone. Print one block per in-flight branch/worktree you touched this session (reuse the Step 3 board entries — usually just one):

**Uncommitted close (the common case):**
```
Resume ▸ per-CT landmark tasks · stage 5 of 9
  PROGRAM per-CT landmark tasks — stage 5 of 9
  BRIEF   <mount>/planning/programs/per-ct-landmark-tasks.md
  REPO    research-skills
  BRANCH  feat/foo   [WORKTREE .claude/worktrees/foo]
  DOC     docs/plans/foo.md (plan) · docs/session/foo-readback.md (state)
  STATE   ⚠ uncommitted — resume from the working tree in this checkout
  OPEN    cd <checkout> && cat docs/session/foo-readback.md   # substance + what's next
```

**Committed-and-pushed close (milestone):**
```
Resume ▸ per-CT landmark tasks · stage 5 of 9
  PROGRAM per-CT landmark tasks — stage 5 of 9
  BRIEF   <mount>/planning/programs/per-ct-landmark-tasks.md
  REPO    research-skills
  BRANCH  feat/foo   [WORKTREE .claude/worktrees/foo]
  DOC     docs/plans/foo.md (plan)
  SHA     <pushed short sha>
  SYNC    git fetch origin && git checkout feat/foo && git pull --ff-only   # run FIRST; verify: git rev-parse --short HEAD → <sha>
```

If the work maps to no program, write `PROGRAM (none — not on any board)` rather than dropping the
line. A blank is indistinguishable from forgetting; an explicit "none" is a finding the next session
can act on.

- **BRANCH / WORKTREE** — the branch/worktree the work sits on (`main` or a `feat/…`), plus `[WORKTREE <path>]` when you're in a non-primary checkout.
- **DOC** — the plan doc this session advanced and/or the `docs/session/` doc carrying its substance and next steps. Omit for a pure-hygiene session with no doc to resume from.
- **STATE / SHA** — *uncommitted close:* `STATE` states the work lives in the working tree of this checkout. *Milestone close:* `SHA` is the pushed short SHA.
- **OPEN / SYNC — the runnable first action.** *Uncommitted close:* the files are already in this checkout, so the next session just opens it and reads the `docs/session/` doc — no fetch. *Milestone close:* the local branch is stale relative to the pushed `<sha>`, so fetch + checkout + pull **before** surveying git — "can't find the branch / doc" means *fetch first*, not *improvise*. Shared / dirty tree or non-ff → `git worktree add ../<repo>-<slug> <sha>` rather than `reset --hard`.
- Skip the resume block only for sessions that advanced no work worth resuming (pure doc-tweak or vista-pm-only sessions).

---

For deeper, full-tree doc consolidation (across files you didn't touch this session), use a separate, heavier-scoped skill — that's a different task with different context needs and shouldn't be folded into routine end-of-session wrapup.
