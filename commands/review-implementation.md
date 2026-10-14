---
name: review-implementation
description: Fresh-context check of finished work against its spec or plan by the `evaluator` agent (Codex only if Phil asks), then *apply* agreed fixes and re-check. The finishing step for any work built from a spec (Done when + Deliverables) or an older plan doc (Files to Modify + Verification) — run it after the Done-when checks pass and BEFORE /commit-review. Invoked via `/review-implementation <path-to-spec-or-plan> [<output-path>] [--reviewer evaluator|codex]`. The evaluator returns PASS or NEEDS_WORK; each finding is classified agree/disagree/uncertain, agreed fixes are applied directly, and only real disagreements go to Phil. Hands off to /commit-review. SKIP for small work with no spec, typo fixes and doc-only changes.
---

# review-implementation

Have a reviewer that didn't build the work check it against the spec. The builder believes the
spec was followed, so it can't grade its own work (`claude_ops.md` → When the work is finished).

```
build → Done-when checks → /review-implementation → (/review-tests) → /commit-review → /land
```

`/commit-review` checks whether the content is fit to commit; this checks whether it does what the
spec said. Different questions.

## When to run it

Every piece of work built from a spec or a plan doc, once the builder has run its *Done when* (or
*Verification*) checks and has their output to hand. No `AskUserQuestion` gate: for spec'd work this
is a required step, not an offer. Skip for small work that had no spec.

## Phase 1 — Resolve inputs

Args: `/review-implementation <path> [<output-path>] [--reviewer evaluator|codex]`.

- **path** — the spec or plan. If missing, use the one this session built from, or ask via
  `AskUserQuestion` using `/read-plan`'s detection logic.
- **Format** — a spec has *Done when* and *Deliverables*. An older plan has *Verification* and
  *Files to Modify*; treat those as its Done-when checks and its deliverables. Don't convert it.
- **Reviewer** — default is the `evaluator` agent. Codex CLI is broken as of 2026-10; use it only
  when Phil names it.
- **Diff baseline** — the merge-base with `main` plus uncommitted changes, so work already
  committed on a branch is in scope. If both are empty, stop: nothing to review.
- **Evidence** — list what the builder can point to for each check: the commands run and what they
  printed, logs, results files and reports on the mount. The evaluator opens these itself; missing
  evidence is a finding, so gather it now rather than after a NEEDS_WORK.
- **output-path** — default `<reviews-dir>/<plan-stem>-implementation-feedback.md`, where the
  reviews directory is `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/<repo>/reviews/` (for
  a plan still in a repo's `docs/plans`, that repo's mount tree at the same path, never the
  checkout). `/review-tests` reads this file later.
- **Repo-local checklist** — include `.claude/references/implementation-review-checklist.md` if
  it exists.

## Phase 2 — Run the reviewer

### Evaluator (default)

`Agent` tool, `subagent_type: "evaluator"`, foreground. Its own definition covers reading the spec,
the diff and the evidence, and the PASS / NEEDS_WORK reply. If the Agent tool doesn't list
`evaluator`, this machine is missing the `~/.claude/agents` symlink (README → Once per machine): make
it, or give the text of `agents/evaluator.md` to a `general-purpose` subagent as its brief. Give it:

- The repo path, the spec or plan path, and the diff baseline.
- For an older plan: "Treat *Files to Modify* as the deliverables and *Verification* as the
  Done-when checks."
- The evidence list from Phase 1, with paths.
- The checklist path, if any.
- These checks on top of its standard ones:
  - Wiring: a new file, function or registry entry is actually reachable from where it's called.
  - Contracts the spec names (output paths, schemas, manifests, sibling-repo surfaces) hold exactly
    where the spec says they must.
  - Tests that only check a substring of rendered SQL, JSON or config (`assert 'X' in rendered_sql`)
    prove nothing on their own. At vista-ct, `'ABD(OMEN)?' in rendered_sql` passed because the
    pattern appeared in two unrelated fields. Flag these; behavioral checks (diff against baseline,
    row-count parity, cross-task invariants) are what count.
  - Code that departs from the spec: say whether it looks like a deliberate improvement or drift.

The evaluator has no Write tool. Save its reply verbatim to the output path, then check the file is
non-empty. Its definition forbids quoting PHI, and the file stays on the mount inside the secure
environment, so this is a plain copy. This saved file is the durable record of the verdict that
`/land` and `/manage` look for.

### Codex (only if Phil asks)

Pipe the same instructions, plus "write your findings to <output-path>, beginning with PASS or
NEEDS_WORK", to `codex exec -s workspace-write --add-dir /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning -`
via a heredoc.

- `--add-dir` is required: without it the mount isn't writable and no file appears, though the run
  looks fine. `workspace-write`, not `read-only`, so it can write the file.
- Check the feedback **file**, never the exit code. `--full-auto` no longer exists.
- Don't put `cd ... &&` in front of `codex`. If it fails, show the error and offer the evaluator.

## Phase 3 — Classify each finding

`PASS` with nothing else: go to Phase 5.

For each NEEDS_WORK finding, before summarizing anything:

- **Agree** — a spot-check confirms it (read the cited file). Draft the fix.
- **Disagree** — you have stronger evidence: an existing wire-up it missed, a misread of the spec.
  Write down what it got wrong.
- **Uncertain** — rare. Only when the fix changes architecture or an output contract and the
  evidence can't settle it.

A deliberate departure from the spec is not a fix to make; it goes to Phil in Phase 4.

## Phase 4 — Apply, re-check, ask only what matters

- **Agreed** — fix it directly. One `Edit` per file, not dozens. Fix what was found; don't rewrite
  around it.
- **Missing evidence** — re-run the check and capture its output rather than arguing.
- **Disagreed / Uncertain** — sort by what the answer changes (`claude_ops.md` → Standing rules).
  Changes the results, the cost, or what we can conclude: ask Phil via `AskUserQuestion`, naming
  what changes with each answer and your default. Otherwise decide and note it in the feedback file.
- **Departures from the spec** — ask Phil to keep or revert each one. A kept departure goes into
  the spec's *Decided* list with the date (or the older plan's text).
- When Phil sides against the reviewer, add a line to the feedback file saying which finding and why.

After fixing, run the evaluator **once more** on the new state, telling it which findings were
fixed. PASS: go on. Still NEEDS_WORK: show Phil the remaining findings and stop. Don't loop.

## Phase 5 — Hand off

Offer `/review-tests` (via `AskUserQuestion`, skip as an option) when the evaluator flagged weak or
missing tests, or the diff adds new branches, raise paths, optional parameters or boundary
conditions that no existing test exercises. Otherwise:

> Evaluator: PASS (<n> findings fixed, <m> decided by Phil). Feedback at <path>. Ready to tick the
> deliverables and `/commit-review`?

Ticking the deliverables against commits or `file:line`, and the what-changed explainer, follow
`claude_ops.md` → When the work is finished. Don't commit here.

## What not to do

- Don't use the current session as the reviewer, and don't write findings of your own into the
  feedback file.
- Don't switch reviewers silently.
- Don't skip an Uncertain finding. "Maybe drifted, maybe not" is the most useful signal there is.
