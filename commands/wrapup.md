End-of-session cleanup. Do the nine steps below in order.

**Open with a one-line context header naming the repo and current branch** — e.g. `research-skills · main` (add the worktree path when you're in a non-primary checkout: `research-skills · feat/foo · .claude/worktrees/foo`). Phil launches sessions across ~50 repos and multiple worktrees of the same repo, so stating *where you are* up front makes it unambiguous which checkout the cleanup and commit gate act on. Derive it from `git worktree list` + `git branch --show-current`, and repeat it in the Step 9 summary so the landed state is self-documenting.

## When to invoke

Recommended cadence: invoke around **~200k tokens of context** (or earlier at a clean cutoff), preserve session state, then start a fresh session with `/next`. Long sessions past that point get noticeably slower (cache misses on every turn, drift in long-tail context) and the marginal value of staying in-session keeps falling.

`/wrapup` is **state-preservation first, commit second**. Its job is to leave the next session everything it needs to resume — `MEMORY.md`, `next.md`, `docs/session/` docs, and the resume block — none of which require a commit. Committing is **opt-in** at the Step 9 gate and defaults to *skip*: reserve it for work that reached a landable milestone (per `claude_ops.md` → Commit Cadence). Ending a session mid-workflow on a token budget is the common case, and it needs no commit — so no commit-time PHI gate fires — with the resume block plus the git-ignored `docs/session/` docs carrying the state forward. (Not committing is not license to relax authorship discipline: never write raw PHI into any doc, git-ignored ones included — see `claude_ops.md` → What Gets Committed.)

## Scope

**Recently-touched docs only.** Pass over `docs/` files you edited or created this session, or files modified since the last commit on the current branch (use `git diff --name-only` and `git status` as fallbacks when session memory isn't enough). Do **not** do a full-tree doc consolidation pass here — that's a deliberately separate, heavier-context task.

## Asking discipline

Use judgment and act. Raise an `AskUserQuestion` only when a call is **both high-importance and genuinely ambiguous** — e.g., an irreversible structural move with real downside risk, or a fork in convention where reasonable choices conflict. Routine cleanup, inline rewording, normal pruning, and obvious bootstrapping decisions are yours to make. *Asking by default is the wrong posture for this skill.*

## Step 1 — Reorg pass on recently-touched files (docs and code dirs)

For each `docs/` file you touched this session:

- Skim for stale content, duplication, bloated sections, content sitting in the wrong file, unclear ordering.
- **Tighten inline** — typo fixes, dead-link cleanup, redundant-paragraph removal, light rewording for clarity, section-header renames.
- **Small-to-moderate reorgs are encouraged when they clearly help findability**: split a bloated doc into focused files, move a section to a doc where it belongs better, merge two docs that should be one, restructure a list, reorder major sections. Update inbound links when you move content. The asking discipline above governs the rare high-stakes ambiguous cases (e.g., renaming a doc that's heavily linked from external repos or external systems).
- **Out of scope here**: full-tree consolidation, gathering scattered content from many untouched docs, large architectural reorganizations of `docs/` as a whole. Defer to a separate, deeper-context skill (or note the opportunity in `next.md` / `backlog.md` for a future pass).
- Goal: optimize for *future-agent findability*. You're reorganizing for your own sake on the next session, not for a human reader.

**Also glance at any code directory you touched this session** (same recently-touched, no-full-tree scope): if it has drifted into a flat dump of unrelated files, propose a small, in-scope split and update inbound imports/references. Placement should have been settled at plan time (`claude_ops.md` → File & Directory Placement) — this is the retrospective safety net, not a substitute for it, so keep the move small and note it in the commit message.

Update any plan/status tables (e.g., `docs/plans/README.md`) if work shipped or got promoted to a plan doc this session. *Review-status sync is handled separately in Step 2.*

## Step 2 — Plan-doc review-status sync

If the project has a plan-tracking index (`docs/plans/README.md` or equivalent), maintain a **Reviewed** column with three values:

- `Yes` — the user has reviewed the current content (via `/read-plan` Phase 5 completion, or an approved in-sync `/explain-plan` HTML — its peer visual path).
- `No` — never reviewed.
- `Stale` — was `Yes`, but the plan has been substantively edited since.

**Sync rules during wrapup**:

- **New plan doc created this session** → ensure README row exists with `Reviewed: No`.
- **Existing plan doc substantively edited this session** ("substantive" = content/section changes; *not* typo fixes, formatting, dead-link cleanup, or whitespace): if the row is currently `Yes`, demote to `Stale`. If `No` or `Stale`, leave as-is.
- **Never silently promote `No` / `Stale` → `Yes`.** Only `/read-plan`, or an approved SHA-in-sync `/explain-plan` HTML (its peer visual path), flips a row to `Yes` — both on user-confirmed completion. If the user states inline that they've reviewed a plan, point them at `/read-plan` (or `/explain-plan` if they reviewed the HTML) to record it — don't shortcut the promotion here.
- **No plan-tracking index exists, but `docs/plans/` (or equivalent) does**: bootstrap a `README.md` with `Plan | Status | Reviewed | Description` columns and populate `Reviewed: No` for all existing plan docs.
- **No `docs/plans/` directory at all**: skip this step.

Surface unreviewed plans (`No` or `Stale`) in the Step 9 summary so the next session can pick them up.

## Step 3 — Tracking-doc hygiene (`next.md` or equivalent)

Find the project's "next steps" tracking doc — commonly `docs/next.md`, `TODO.md`, `BACKLOG.md`, or similar. If multiple exist or the canonical one is unclear, ask.

In that doc:

- Remove completed items. Note in the commit message where each was promoted to (plan doc, journal entry, spec).
- Add new items discovered this session.
- **Enforce pointer style**: each item is a 1–3 line reminder + a link to a plan/journal/spec for substance. If an item runs longer than ~3 lines, the detail belongs in a sub-doc — promote it and leave a pointer.
- Update "Last updated" date if the doc has one.

## Step 4 — Backlog hygiene (`backlog.md` or equivalent)

If a separate backlog file exists (e.g., `docs/backlog.md`), apply the same pointer discipline: prune items actually finished, promote items into the immediate-tracking doc when priorities have shifted, leave the rest as terse pointers.

If no backlog file exists but the immediate-tracking doc has a "Deferred / Backlog" or similar section that has grown unwieldy, bootstrap a separate backlog file by migrating that section out. Note the migration in the commit message so it's traceable. Per the asking discipline, only raise a question if the right destination file is genuinely ambiguous (e.g., the project has multiple plausible homes for it).

**Contract for both `next.md` and `backlog.md`**: short, structured indexes. Substance lives in `docs/plans/`, `docs/journal/`, `docs/specs/`, or wherever the project keeps it. If you're writing more than ~3 lines per item, promote the detail and leave a pointer.

## Step 5 — Auto-memory pass

Update `MEMORY.md` to reflect the current project state, open items, and any new preferences or facts learned this session. Evict stale entries. Save new memories per the auto-memory rules in the system prompt — do not duplicate facts already covered by `CLAUDE.md` or derivable from the code.

## Step 6 — Cross-repo resume index (vista-pm)

Keep one cross-repo "in-flight work" index current so the next session can resume the *right* recent work without re-deriving it from git. This is the hub-level rollup of the per-repo `next.md` hygiene in Step 3 — it answers "which of my several worktrees do I pick back up?"

**Planner-Mac only — never on the VM.** This index is a local-only, git-ignored, planner-Mac artifact: the `vista-pm/personal/` tree is never pushed, so there is nothing to pull at session start and it does not exist on the executor VM. Run this step ONLY on the planner Mac; skip it entirely on the executor VM (`phil-sllm-01`) or any host where `vista-pm/personal/` is absent. Per claude_ops Machine-Aware Operating Mode you already know the machine from the session-start `hostname` — `vista-pm/personal/` existing is the operative check.

**Where**: `vista-pm/personal/in-flight.md` (same place the personal to-dos live). Find `vista-pm` as a sibling of the current repo (its parent dir / the `code/` workspace root). Also **skip** for sessions that didn't advance a branch/worktree (pure-doc tweaks, vista-pm-only work, trivial fixes).

**Incremental — do NOT run a cross-repo git sweep.** A wrapup runs inside one repo's session and only cheaply knows *that* repo's work. Upsert only the branch/worktree(s) you touched this session; leave every other repo's entries alone. (Re-deriving the whole index from a full `git worktree list` + push-state sweep across all repos is a separate, occasional reconcile — not this step.)

**Per touched branch/worktree, upsert one entry** under a `## <repo>` heading:

```
## <repo>
- <branch-or-worktree> · <state> · <MM-DD>
  <one line: what it is>
  next: <one line> → <pointer to the repo's docs/next.md or the plan doc>
```

- **`<state>`** — read cheaply from this session's own git knowledge (no sweep): `pushed` (committed and on `origin/<branch>`), `⚠ UNPUSHED` (committed locally, not on origin — lost if the clone/worktree is gone), or `⚠ UNCOMMITTED` (dirty / draft not yet committed). Quick check: `git -C <wt> status -sb` plus whether an `origin/<branch>` ref exists.
- **Order** newest-first within a repo; keep repos most-recently-touched first.
- **Prune on landing**: if the branch merged to main or was abandoned this session, remove its entry (note the removal in the Step 9 summary).
- **Pointer style** (same contract as `next.md`): ≤3 lines per entry; substance lives in the plan doc / `next.md` it points at.

**Editing mechanics**: the file is git-ignored — edit it in place. In a guarded background session where direct edits to a sibling checkout are blocked, write the updated file to scratch and `cp` it in (Bash isn't guarded). Never commit this file.

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

- *Commit and push* / *Commit only*: stage only the files you touched (`git -C <repo> add <file1> <file2>`; do **not** use `git -C <repo> add -A`), then commit with a short single-line thematic message describing what changed (e.g., `review-plan: fold in the handoff-readiness lens`). No AI attribution lines, matching the project commit-message convention. Push only if the option chosen requires it.
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

**Authorship discipline applies unchanged**: never write raw PHI (patient identifiers, sample rows, report text) into the state doc. Git-ignoring controls *commit* exposure, not what may be written — the standing rule that Claude never echoes PHI into any doc applies to git-ignored files exactly as to committed ones (`claude_ops.md` → What Gets Committed).

**Mechanics**: `docs/session/` is git-ignored — edit it in place; never stage or commit it. In a guarded background session where direct edits to a sibling checkout are blocked, write to scratch and `cp` it in (Bash isn't guarded).

**Skip** only for sessions that advanced no resumable work (pure doc-tweak, vista-pm-only) — the same sessions that skip the resume block.

## Step 9 — Summary + commit gate (opt-in)

**Summarize as bullet points** (not a paragraph). Lead with the `<repo> · <branch>` context header (per the top-of-skill note), then use these headings; omit any that are empty:

- **Shipped this session**: what concretely landed (1–3 bullets).
- **Doc changes worth flagging**: any moderate-or-higher reorgs from Step 1 — file splits, cross-doc moves, doc merges, major section reorders, new files bootstrapped. Skip if all doc work was inline tightening.
- **Plans needing review**: any rows currently `No` or `Stale` in the plan-tracking index after Step 2 — name the path so the next session can run `/read-plan <path>`. Skip if all plans are `Yes` or no plan-tracking index exists.
- **Next**: what comes after this session (1–3 bullets).
- **Blocked on user**: things the next session can't unblock itself (1–3 bullets).

**Then raise an `AskUserQuestion` at the commit gate** with three structured options. Commit is **opt-in** — the default is to skip it and let the resume block + `docs/session/` docs carry state forward. Only offer commit as the recommended choice when this session's changes reached a **landable milestone** (per `claude_ops.md` → Commit Cadence): an approved plan, a completed and verified implementation, or results ready to hand off. For the common mid-workflow / budget-out close, skip.

1. **"Skip commit" (Recommended for a mid-workflow close)** — don't commit; leave changes in the working tree. State is preserved by `MEMORY.md`, `next.md`, `docs/session/`, and the resume block. Nothing is staged, so no commit-time PHI gate fires.
2. **"Commit and push"** — commit the changes and push to the tracking remote in one action. Choose this when the work is a landable milestone.
3. **"Commit only (no push)"** — create the commit locally; defer the push.

Recommend the option that matches the session's state (Skip for mid-workflow, Commit for a milestone), and put it first. Inline free-text yes/no is the wrong shape here — the answer space is enumerable; structured choices are clearer and faster. This single gate replaces what would otherwise be two asks (commit gate here + push gate inside `commit-review`).

**Based on the user's answer**:
- *Skip commit*: end the wrapup flow without invoking commit-review.
- *Commit and push*: invoke `commit-review` with `args: "push-authorized"`. Signals that the push decision has already been gated, so commit-review skips its own main-push prompt.
- *Commit only*: invoke `commit-review` with `args: "no-push"`. Commit-review commits and skips the push step entirely.

Do not auto-commit. Do not run `git commit` inline — always go through `commit-review`, which handles the appropriateness review and project commit conventions in one step. `docs/session/` is git-ignored, so readbacks and session docs there are never staged for a commit regardless of the choice above.

### Resume block — print last, always

After the commit gate resolves (whether or not you committed), the **final output** is a copy-paste **resume block** — the coordinates the next session uses to pick the work back up without re-deriving it from git. Most sessions close **uncommitted** (commit is opt-in), so the block defaults to pointing at the working tree and `docs/session/` docs in this checkout; the pushed-SHA form applies only when this session committed at a milestone. Print one block per in-flight branch/worktree you touched this session (reuse the Step 6 entries — usually just one):

**Uncommitted close (the common case):**
```
Resume ▸ research-skills
  REPO   research-skills
  BRANCH feat/foo   [WORKTREE .claude/worktrees/foo]
  DOC    docs/plans/foo.md (plan) · docs/session/foo-readback.md (state)
  STATE  ⚠ uncommitted — resume from the working tree in this checkout
  OPEN   cd <checkout> && cat docs/session/foo-readback.md   # substance + what's next
```

**Committed-and-pushed close (milestone):**
```
Resume ▸ research-skills
  REPO   research-skills
  BRANCH feat/foo   [WORKTREE .claude/worktrees/foo]
  DOC    docs/plans/foo.md (plan)
  SHA    <pushed short sha>
  SYNC   git fetch origin && git checkout feat/foo && git pull --ff-only   # run FIRST; verify: git rev-parse --short HEAD → <sha>
```

- **BRANCH / WORKTREE** — the branch/worktree the work sits on (`main` or a `feat/…`), plus `[WORKTREE <path>]` when you're in a non-primary checkout.
- **DOC** — the plan doc this session advanced and/or the `docs/session/` doc carrying its substance and next steps. Omit for a pure-hygiene session with no doc to resume from.
- **STATE / SHA** — *uncommitted close:* `STATE` states the work lives in the working tree of this checkout. *Milestone close:* `SHA` is the pushed short SHA.
- **OPEN / SYNC — the runnable first action.** *Uncommitted close:* the files are already in this checkout, so the next session just opens it and reads the `docs/session/` doc — no fetch. *Milestone close:* the local branch is stale relative to the pushed `<sha>`, so fetch + checkout + pull **before** surveying git — "can't find the branch / doc" means *fetch first*, not *improvise*. Shared / dirty tree or non-ff → `git worktree add ../<repo>-<slug> <sha>` rather than `reset --hard`.
- Skip the resume block only for sessions that advanced no work worth resuming (pure doc-tweak or vista-pm-only sessions).

---

For deeper, full-tree doc consolidation (across files you didn't touch this session), use a separate, heavier-scoped skill — that's a different task with different context needs and shouldn't be folded into routine end-of-session wrapup.
