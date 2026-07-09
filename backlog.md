# research-skills — backlog

Known issues and deferred work for the skill repo itself. Per the same pointer-style discipline `/wrapup` enforces on project repos: short entries, link out to substance.

## Runtime cache vs canonical drift

The intended setup is a symlink: `~/.claude/commands → research-skills/commands` (per README "One-shot setup on a fresh VM"). On some machines (e.g., the laptop where this entry was filed, 2026-05-12), `~/.claude/commands/` is instead a *separate git repo* with its own history that has drifted from canonical — wrapup Step 6 + 7 lived in runtime but not canonical until a manual sync. Symptoms:

- `git -C ~/.claude/commands status --short` shows files marked as untracked or deleted that are actually tracked in canonical.
- New skill versions edited in `~/.claude/commands/` don't propagate to GitHub unless manually `cp`'d to canonical and committed there.

**Resolution options when picking this up:**
- (A) Convert `~/.claude/commands/` to a symlink per the README setup, after backing up any local-only files. Requires reconciling pre-existing drift first.
- (B) Keep two separate repos but automate sync (a pre-session hook that rsyncs canonical → runtime).
- (C) Document the manual `cp`-and-commit ritual in `wrapup`'s Step 6 (already partially done — the post-2026-05-12 wrapup spec calls out "sync direction matters" and the `cp` recipe).

Filed 2026-05-12 during `/wrapup` after discovering the laptop's runtime cache had Step 6 + 7 but canonical didn't.

## rad-eval has no per-repo plan-review-checklist

Three repos have a `.claude/references/plan-review-checklist.md` (vista_bench, vista-eval,
vista-ct); rad-eval does not. Until one is seeded, the generic archetype menu (and, once it
lands, the canonical `references/verification-and-handoff-design.md` spec) carries more weight
for rad-eval plan reviews than for the others. Worth a small followup plan to author a
rad-eval checklist grounded in its extraction / seed-gate / equivalence verification patterns.

Filed 2026-07-08 while scoping the verification-and-handoff-design agent (moved out of that
plan's open questions so the plan doesn't carry a stale cross-repo reference).

## (Future entries — add as encountered)
