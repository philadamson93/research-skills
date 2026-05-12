End-of-session cleanup. Do the seven steps below in order.

## Scope

**Recently-touched docs only.** Pass over `docs/` files you edited or created this session, or files modified since the last commit on the current branch (use `git diff --name-only` and `git status` as fallbacks when session memory isn't enough). Do **not** do a full-tree doc consolidation pass here — that's a deliberately separate, heavier-context task.

## Asking discipline

Use judgment and act. Raise an `AskUserQuestion` only when a call is **both high-importance and genuinely ambiguous** — e.g., an irreversible structural move with real downside risk, or a fork in convention where reasonable choices conflict. Routine cleanup, inline rewording, normal pruning, and obvious bootstrapping decisions are yours to make. *Asking by default is the wrong posture for this skill.*

## Step 1 — Doc-reorg pass on recently-touched docs

For each `docs/` file you touched this session:

- Skim for stale content, duplication, bloated sections, content sitting in the wrong file, unclear ordering.
- **Tighten inline** — typo fixes, dead-link cleanup, redundant-paragraph removal, light rewording for clarity, section-header renames.
- **Small-to-moderate reorgs are encouraged when they clearly help findability**: split a bloated doc into focused files, move a section to a doc where it belongs better, merge two docs that should be one, restructure a list, reorder major sections. Update inbound links when you move content. The asking discipline above governs the rare high-stakes ambiguous cases (e.g., renaming a doc that's heavily linked from external repos or external systems).
- **Out of scope here**: full-tree consolidation, gathering scattered content from many untouched docs, large architectural reorganizations of `docs/` as a whole. Defer to a separate, deeper-context skill (or note the opportunity in `next.md` / `backlog.md` for a future pass).
- Goal: optimize for *future-agent findability*. You're reorganizing for your own sake on the next session, not for a human reader.

Update any plan/status tables (e.g., `docs/plans/README.md`) if work shipped or got promoted to a plan doc this session. *Review-status sync is handled separately in Step 2.*

## Step 2 — Plan-doc review-status sync

If the project has a plan-tracking index (`docs/plans/README.md` or equivalent), maintain a **Reviewed** column with three values:

- `Yes` — the user has reviewed the current content (typically via `/read-plan` Phase 5 completion).
- `No` — never reviewed.
- `Stale` — was `Yes`, but the plan has been substantively edited since.

**Sync rules during wrapup**:

- **New plan doc created this session** → ensure README row exists with `Reviewed: No`.
- **Existing plan doc substantively edited this session** ("substantive" = content/section changes; *not* typo fixes, formatting, dead-link cleanup, or whitespace): if the row is currently `Yes`, demote to `Stale`. If `No` or `Stale`, leave as-is.
- **Never silently promote `No` / `Stale` → `Yes`.** Only `/read-plan` (on user-confirmed completion) flips a row to `Yes`. If the user states inline that they've reviewed a plan, point them at `/read-plan` to record it — don't shortcut the promotion here.
- **No plan-tracking index exists, but `docs/plans/` (or equivalent) does**: bootstrap a `README.md` with `Plan | Status | Reviewed | Description` columns and populate `Reviewed: No` for all existing plan docs.
- **No `docs/plans/` directory at all**: skip this step.

Surface unreviewed plans (`No` or `Stale`) in the Step 6 summary so the next session can pick them up.

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

## Step 6 — Global skills sync (separate repo)

The user's global skills live in their own git repo, which is **a different repo from the project being worked on** — it has its own commit gate and its own push target. There are often TWO related paths to consider:

- **Runtime cache** — `~/.claude/commands/` and `~/.claude/skills/`. These are what Claude Code loads at session start. Often its own local git repo, but may accumulate untracked drift since the canonical source is elsewhere.
- **Canonical repo** — a user-maintained git repo with a GitHub remote, often named `*-skills` / `claude-skills` / `research-skills` and located under the user's `~/Documents/` or projects directory. Authoritative source of truth.

**Detection:**
1. Always check the runtime cache: `git -C ~/.claude/commands status --short` (and `git -C ~/.claude/skills status --short` if that path exists).
2. Check the canonical repo if one exists. Look for `~/.claude/canonical-skills-repo` (a single-line file containing the absolute path to the canonical repo). If that pointer file doesn't exist, fall back to scanning common locations (`find ~/Documents -maxdepth 4 -type d \( -name 'research-skills' -o -name 'claude-skills' \) 2>/dev/null | head -5`) and surface a candidate via `AskUserQuestion` if exactly one match is found. If zero or many, skip and surface in Step 7 summary as "no canonical skills repo detected."
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
3. **"Skip"** — leave global-skills changes uncommitted; flag in the Step 7 summary as needing attention.

Based on the answer:

- *Commit and push* / *Commit only*: stage only the files you touched (`git -C <repo> add <file1> <file2>`; do **not** use `git -C <repo> add -A`), then commit with a short single-line thematic message describing what changed (e.g., `plan-handoff-readiness: add implementation-forward principle`). No AI attribution lines, matching the project commit-message convention. Push only if the option chosen requires it.
- *Skip*: do nothing; surface in Step 7 summary.

The `-C <path>` form keeps the project's cwd intact; do not `cd` into the skills repo.

**Why a separate gate from Step 7:** two independent repos, two independent push targets. The user might want to push the project but defer the skills sync, or vice versa. One gate per repo.

## Step 7 — Summary + commit gate

**Summarize as bullet points** (not a paragraph). Use these headings; omit any that are empty:

- **Shipped this session**: what concretely landed (1–3 bullets).
- **Doc changes worth flagging**: any moderate-or-higher reorgs from Step 1 — file splits, cross-doc moves, doc merges, major section reorders, new files bootstrapped. Skip if all doc work was inline tightening.
- **Plans needing review**: any rows currently `No` or `Stale` in the plan-tracking index after Step 2 — name the path so the next session can run `/read-plan <path>`. Skip if all plans are `Yes` or no plan-tracking index exists.
- **Next**: what comes after this session (1–3 bullets).
- **Blocked on user**: things the next session can't unblock itself (1–3 bullets).

**Then raise an `AskUserQuestion` at the commit gate** with three structured options:

1. **"Commit and push" (Recommended)** — commit the cleanup changes and push to the tracking remote in one action.
2. **"Commit only (no push)"** — create the commit locally; defer the push.
3. **"Skip commit"** — don't commit; leave changes uncommitted.

Inline free-text yes/no is the wrong shape here — the answer space is enumerable; structured choices are clearer and faster. This single gate replaces what would otherwise be two asks (commit gate here + push gate inside `commit-review`).

**Based on the user's answer**:
- *Commit and push*: invoke `commit-review` with `args: "push-authorized"`. Signals that the push decision has already been gated, so commit-review skips its own main-push prompt.
- *Commit only*: invoke `commit-review` with `args: "no-push"`. Commit-review commits and skips the push step entirely.
- *Skip commit*: end the wrapup flow without invoking commit-review.

Do not auto-commit. Do not run `git commit` inline — always go through `commit-review`, which handles the appropriateness review and project commit conventions in one step.

---

For deeper, full-tree doc consolidation (across files you didn't touch this session), use a separate, heavier-scoped skill — that's a different task with different context needs and shouldn't be folded into routine end-of-session wrapup.
