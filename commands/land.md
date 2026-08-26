---
name: land
description: Merge a finished feature branch into main — the per-branch-close bookend to /next (session-open) and /wrapup (session-close). Runs a single-repo sibling-branch/worktree conflict scan (the merge-time coordination check that otherwise falls through the gaps), gates review-status, supersession, and green-gate freshness (does the branch's verification still describe the tree after main moved under it?), then — behind an explicit gate — performs the merge (ff-only or PR) and prunes the branch, its worktree, and the tracker/in-flight entries. TRIGGER when a feature branch is ready to land: the user says "land this", "merge to main", "ship it", "this is done — merge it", or invokes /land. SKIP for doc-only fixes / minor bug fixes committed directly on main (no branch to land), and when the branch isn't finished (route to /commit-review to land the branch first). Do NOT auto-trigger the merge — the write-to-main always waits behind an AskUserQuestion gate.
---

# land

The missing bookend. `/next` opens a session and surveys worktrees; `/wrapup` closes a *session* and preserves its state (committing only at a milestone, via its opt-in commit gate). Neither closes a *branch* — the moment a feature is done and you integrate it into `main`. That moment is where sibling-branch coordination matters most (whichever of two branches touching the same files lands second eats a rebase) and where, historically, nobody runs the check because the merge-to-main *action* had no skill to attach it to. This is that skill.

**Open with a one-line context header naming the repo and the branch being landed** — e.g. `vista-eval · feat/survival-eval-v1_6-runner → main` (add the worktree path when landing from a non-primary checkout). Phil launches sessions across ~50 repos and multiple worktrees of the same repo; stating *which branch is about to hit main* up front makes the whole operation unambiguous. Derive it from `git worktree list` + `git branch --show-current`, and repeat it in the Phase 4 summary so the landed state is self-documenting.

## When to invoke / when to skip

- **Invoke** when a feature branch is finished and ready to integrate into `main` — committed, pushed, review gates satisfied.
- **Skip** for doc-only or minor-bug-fix commits that (per `claude_ops.md` → Git Practices) go **directly on main** — there's no branch to land.
- **Skip and route** when the branch isn't actually done: uncommitted work or unlanded commits → `/wrapup` + `/commit-review` land the *branch* first; come back to `/land` once the branch is clean and pushed.
- This is a **per-feature** action, not a per-session one — it may fire many sessions after the branch's last commit. That decoupling from `/wrapup` is exactly why it's a separate skill.

## Machine posture (read first)

Merging is a git operation, not repo code — `git merge` / `git push` / `gh pr` are fine on **any** machine. Repo tests/linters/python that need GPU or high-throughput compute still don't belong on the Mac (per `claude_ops.md` → Machine-Aware Operating Mode; the VM fleet has that capacity, the Mac doesn't) — don't run those as part of landing. If the branch's correctness still depends on an unrun GPU/high-throughput step, that's a **Phase 1 blocker**, not something `/land` resolves — surface it and stop. Pushing `main` is the one outward-facing act here; it lives behind the Phase 3 gate and is never silent.

## Phase 0 — Enumerate + refresh (do this FIRST)

Same discipline as `/next` Phase 0, scoped to **this repo**:

1. `git worktree list` — the branch being landed may live in a sibling worktree, and its siblings-to-scan (Phase 2) certainly do.
2. `git fetch --all --prune` — so behind/ahead counts and the sibling scan see true remote state, not stale local refs (a VM readback may have pushed on this very branch).
3. Confirm the branch-to-land is **clean and pushed**: `git -C <wt> status -sb`. Dirty or ahead-of-origin → **stop and route** to `/wrapup` + `/commit-review` (see "When to skip"). `/land` lands *finished* branches; it does not do the branch's own commit hygiene.

## Phase 1 — Pre-flight: is this branch landable?

Gate the branch against the conditions that make a merge premature. Surface any that fail; do not merge past a red.

**Follow the plan's *Landing & cleanup* section if it has one** (per `claude_ops.md` → Plan Document Structure): it states the intended branch, landing gate, and — for multi-branch work — the merge sequence, all reviewed *with* the plan. `/land` follows that design; surface any drift from it rather than silently re-deriving the merge order in Phase 2.

- **Behind main?** `git -C <wt> rev-list --left-right --count origin/main...<branch>`. If the branch is behind `origin/main`, a clean ff is impossible — it needs `origin/main` merged/rebased in first. Surface the behind-count and the choice (rebase vs merge-main-in); don't force it.
- **Green-gate freshness — has main moved under the branch?** The branch's tests/verification prove the tree that was *checked*; that equals the tree landing on main only when main hasn't advanced past the branch's merge-base. Read it off the **same left-right count** above — the trigger is identical to "Behind main?", but the concern is semantic (does the green run still describe the post-merge tree?), not textual (does the ff apply?):
  - **main-ahead == 0** → a clean ff, so the branch's existing green run already covers the exact tree that becomes main. Say so and re-verify nothing — this is the trivial path, keep it unblocked.
  - **main-ahead > 0** → landing needs a rebase / merge-main-in first, yielding an integrated tree that was never actually checked (classic logical merge: branch green alone, main green alone, merged tree possibly broken). Run the **Phase 2** diff/intersect on *main's* new commits — `git diff --name-only $(git merge-base origin/main <branch>)..origin/main` — against the branch's changed files. **Empty intersection** → textually independent, low logical-merge risk → note in one line and proceed. **Non-empty** → the green gate is stale w.r.t. the shared file(s); name them and recommend a re-verify on the rebased tree before landing. A flag to clear (same posture as review-status), not an auto-block.
  - Same idea if the branch itself gained commits *after* its last gate (main-ahead still 0, ff fine): the newest tree is unproven — worth a one-line nod, though that's the branch's own verify concern, closer to `/wrapup` than to integration risk.
- **Review-status.** If the repo has `docs/plans/README.md`, find the plan doc for this branch and check its **Reviewed** column. `No` / `Stale` (per `/wrapup` Step 2 semantics) → surface it — many of Phil's branches gate on `/read-plan` sign-off before landing. Not an automatic block, but a flag the user must clear.
- **GPU / high-throughput step outstanding?** If the plan's *Verification* section names a standalone-runner-script step that was never actually run (no output on the shared mount to point at), the branch may be unproven. Surface it; let the user decide whether landing is appropriate.
- **PHI.** Merging to main is a push of already-committed content — it does **not** re-vet. The PHI gate belongs at *commit* time (`/commit-review` → `/phi-vet`). If this branch's content was committed without that gate in a medical-data repo, flag it here and route to `/phi-vet` before landing rather than pushing unvetted content to main.

## Phase 2 — Sibling-branch / worktree coordination scan (the heart)

Run the **single-repo slice** of the cross-branch conflict analysis specified in **`/vista-drift` Step 2b** — reuse that computation, don't duplicate it. The read-only helper `personal/to-dos/branch_conflict_survey.py` already implements it (`git merge-base` + `git diff --name-only` intersection are read-only inspection, fine on the Mac). Scope it to **this repo** and to **the branch being landed vs its recently-active siblings**, rather than vista-drift's full cross-repo sweep.

Per `/vista-drift` Step 2b, for each recently-active unmerged sibling branch/worktree, intersect its changed-file set (vs merge-base) with the landing branch's, and classify:

- **CODE overlap** — a shared non-doc file (`.py`/`.sh`/`.sql`/config). **Real** rebase/conflict risk: landing this branch now means the sibling eats a conflict on that file. Name the file(s) and the sibling. A file touched by **3+** live branches is a hotspot — call it out.
- **doc/registry overlap only** — `docs/plans/README.md`, `docs/next.md`, task `.md`s, generated `.html`. **Low** risk (append-y registries resolve trivially). Note in one line; don't alarm.
- **same-workstream layering** — the landing branch is strictly ahead of (and effectively contains) a sibling, or vice-versa. This is **supersession, not conflict**: the sibling is likely mergeable-into / deletable-after this land, or *this* branch is superseded by a sibling that should land instead. Surface the relationship — landing the wrong one of a layered pair is a real mistake.

**Output**: (a) is it safe to land this branch *now*, or should a sibling go first? — recommend a **merge order** (land the foundational/smaller branch first, rebase the big rename/refactor last, unless the refactor is a prerequisite). (b) Which sibling(s), if any, will need a rebase after this lands, and on which files.

## Phase 3 — Merge gate + execute

Summarize Phases 1–2 as bullets (landable? review-status? behind main? green-gate fresh or stale-vs-moved-main? conflict findings + merge order?), then **gate the write-to-main with an `AskUserQuestion`** — structured options, never inline yes/no, never silent:

1. **Merge (ff-only) + push** *(default when the branch is ahead-of-main with a clean ff and no red flags)* — `git checkout main && git merge --ff-only <branch> && git push`. Report the SHA. Fast-forward keeps history linear and refuses if a true merge would be needed (safety by construction).
2. **Open a PR** — `gh pr create` (per the `gh-cli-local-bin-new-mac` memory: `gh`, not anonymous API; VISTA-Stanford is mostly private). For branches that want a review record or CI on GitHub before merge. Report the PR URL.
3. **Hold** — don't touch main; leave the pre-flight + conflict findings as the record. For when a sibling should land first, or a flag needs clearing.

Never force-push. Never merge past an unresolved Phase 1 red without the user explicitly overriding it. If the ff-only merge is refused (branch diverged / behind main from Phase 1), report it and hand back — do not fall back to a non-ff merge silently.

## Phase 4 — Post-merge cleanup

Only after a merge actually landed (skip entirely for **Hold** / PR-not-yet-merged):

- **Prune the branch** — delete local (`git branch -d <branch>`) and remote (`git push origin --delete <branch>`) once merged. Use `-d` (safe, refuses if unmerged), not `-D`.
- **Remove the worktree** — if the branch lived in a worktree, `git worktree remove <path>` (or `ExitWorktree` if landing from inside it). A stale worktree on a deleted branch is exactly the litter `/next` Phase 0 later trips over.
- **Mark the plan doc done** — `**Status: Completed** (<date>)` at the top of the plan doc; flip its `docs/plans/README.md` row to Completed / `Reviewed: Yes` as appropriate (per `/wrapup` Step 2 rules — don't silently promote review-status; the merge itself is the completion signal, not a review).
- **Prune trackers** — remove the landed item from the repo's `docs/next.md` (leave a pointer if follow-ups remain), and remove its entry from `vista-pm/personal/in-flight.md` (**planner-Mac only**, per `/wrapup` Step 6 — the `personal/` tree is git-ignored and absent on the VM; edit via scratch + `cp` in a guarded bg session).
- **Warn the siblings** — for any Phase 2 CODE-hotspot sibling that now needs a rebase, offer (via an `AskUserQuestion`) to add a short `⚠ Parallel-branch note` to that sibling's plan doc naming the now-landed files + that a rebase is due, so the next agent picking it up is warned. Same caveats as `/vista-drift`: editing a sibling plan doc is a **write** (name the file, use the bg-safe worktree path); **never touch sibling code — plan docs only**.

## Phase 5 — Summary

Bullet summary led by the `<repo> · <branch> → main` header: SHA/PR landed, branch + worktree pruned (or why not), plan-doc/tracker updates, and — if Phase 2 flagged them — which siblings now owe a rebase and in what order they should land. Close by pointing at the next branch in the recommended merge order, if any.

## Composition

- **`/vista-drift` Step 2b** — the canonical cross-branch conflict computation. `/land` runs its single-repo, single-branch slice; it does not re-implement the diff/intersect/classify. (If this reuse proves load-bearing, extract Step 2b's algorithm into a shared `references/cross-branch-conflict-survey.md` that both skills point at — a follow-up refactor, not a prerequisite.)
- **`/wrapup`** — owns *session*-close doc/memory/tracker hygiene and the branch's own **opt-in** commit gate (it doesn't commit by default — only at a milestone). `/land` reuses its Step 2 review-status semantics and Step 6 `in-flight.md` discipline rather than redefining them. Land a branch's final commits via `/wrapup` → `/commit-review` *before* `/land`.
- **`/commit-review`** / **`/phi-vet`** — content-appropriateness and PHI gates at *commit* time. `/land` does not re-vet committed content; it routes back to these only if a branch reached `/land` without having passed them.
- **`/next`** — the session-open counterpart. Its Phase 0 worktree-litter check is downstream of `/land` doing its Phase 4 prune: a `/land` that skips cleanup is what leaves the stale branches `/next` later has to reconcile.
