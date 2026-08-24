---
name: review-tests
description: Independent test-coverage audit of uncommitted code by Codex CLI or a fresh Claude Code subagent, against a plan doc, then *apply* agreed test stubs by default. Use after `/review-implementation`, BEFORE `/commit-review`, when the implementation introduces new branches / contracts / edge cases that warrant regression-protection tests. Invoked explicitly via `/review-tests <path-to-plan> [<output-path>] [--reviewer codex|claude]`. Also offered proactively at the end of `/review-implementation`. **Reviewer is never silently defaulted** — if not specified in args, the skill asks. Scoped strictly to uncommitted code; aborts when the working tree is clean. Runs the chosen reviewer over the diff + plan + existing test layout + prior implementation feedback, classifies each gap as agree/disagree/uncertain, then by default *applies* test stubs at the suggested locations and runs them. Only surfaces findings for adjudication where Claude genuinely disagrees with the reviewer. Hands off to `/commit-review` on completion. SKIP for typo fixes, doc-only changes, or anything where the existing test suite already gates the change end-to-end.
---

# review-tests

Get an independent audit of test coverage for uncommitted code against the plan it was meant to implement. The reviewer's lens differs from Claude's; the delta surfaces silent regression risk — code paths the implementer wrote but didn't think to assert.

This skill is distinct from `/review-implementation`. That skill audits *fidelity* (drift, contracts, missing pieces) and surfaces test gaps as one section among several. `/review-tests` is the deeper version — focused exclusively on coverage, with apply-mode stubs and a re-run gate. Run it after `/review-implementation` when the implementation introduces new branches, raise paths, optional params, or boundary conditions that need regression protection.

Two reviewer options, picked explicitly at invocation:

- **Codex** — cross-model (GPT family). Different blind spots from Claude. Default-recommended.
- **Fresh Claude Code subagent** — same model family, but spawned without conversation context (so it reads the diff + plan cold). Useful when Codex is unavailable, when running a second-reviewer pass after Codex, or when the user explicitly wants a same-model take.

The skill exists because the author of code reviewing their own test coverage is not independent — Claude wrote the code; Claude already believes the coverage is adequate. Always invoke either Codex via `codex exec` or a fresh subagent via the `Agent` tool — never silently substitute the *current* Claude session as the reviewer.

## When to offer

Proactively offer at the end of `/review-implementation` — Phase 7 of that skill hands off to here when the implementation review surfaced any "Test Gaps" findings or when the diff introduces non-trivial new branches. Gate the offer behind `AskUserQuestion`:

- *Codex test-coverage review (Recommended — cross-model independence)*
- *Fresh Claude Code subagent (same model, no conversation context)*
- *I'll run it myself in another tab*
- *Skip — coverage is adequate as-is*

Do not auto-invoke. Skip the offer for typo fixes, doc-only updates, single-file bug fixes, or refactors where the existing test suite already exercises every branch end-to-end.

**When to recommend the fresh Claude subagent over Codex** (i.e., when to make it the first option):

- Codex isn't installed / authed in this environment (verify with a quick `command -v codex`).
- The user has *just* run a Codex review on this plan/diff and now wants a second-reviewer pass.
- The user has explicitly asked for a "Claude" or "fresh agent" review.

In all other cases recommend Codex first — model-family independence is the bigger win.

## Phase 1 — Resolve paths, reviewer, scope

Args: `/review-tests <plan-path> [<output-path>] [--reviewer codex|claude]`.

- **plan-path** — required. Verify it exists. If invoked without args, ask via `AskUserQuestion` using the same plan-doc detection logic as `/read-plan` Phase 1.
- **reviewer** — required, but never silently defaulted. If `--reviewer codex` or `--reviewer claude` was passed in args, use that. **Otherwise, ask via `AskUserQuestion`** before doing anything else (unless the proactive offer already produced the choice in the same turn — carry it forward).
- **output-path** — optional. Default depends on reviewer:
  - `codex` → `docs/plans/reviews/<plan-stem>-test-coverage-feedback.md`
  - `claude` → `docs/plans/reviews/<plan-stem>-test-coverage-feedback-claude.md`
  Create the parent dir if missing. Distinct filenames matter — running both reviewers should not overwrite.
- **Repo-local checklist** — look for `.claude/references/test-review-checklist.md`. If found, include in the reviewer prompt. If not found, proceed with the generic prompt and warn once that a repo-grounded checklist would yield a sharper review.
- **Sibling repo docs** — if `docs/claude_ops.md` and/or `docs/lessons.md` exist, include them as required reads. Otherwise omit those references.
- **Prior implementation feedback** — look for `docs/plans/reviews/<plan-stem>-implementation-feedback.md`. If found, include in the prompt with explicit instructions: "do not re-flag items already adjudicated here." This avoids the reviewer rediscovering gaps the user already kept-or-dismissed.
- **Diff scope** — capture the current uncommitted state via `git status` and `git diff` (both staged and unstaged) plus a list of untracked files. Include the diff stat (`git diff --stat`) and untracked filenames in the prompt; let the reviewer read full file contents itself.
- **Codex availability check** — if reviewer = `codex`, run `command -v codex` first. If absent, surface and offer to switch to the fresh Claude subagent (the one auto-fallback path; user-visible).

**Strict scope verification — abort if nothing to review:**

- If the working tree is clean (no staged, unstaged, or untracked changes), abort with: "No uncommitted changes — nothing to test-review against the plan. /review-tests audits *uncommitted* implementation work; if the plan was already merged, run on the implementer's branch before merge."
- If only doc files changed (no production code), warn and ask via `AskUserQuestion` whether to proceed (a doc-only diff is rarely worth a deep test-review).
- If only test files changed (no production code), warn and ask similarly (tests-only diffs are usually self-evident).

## Phase 2 — Invoke chosen reviewer

Branch on reviewer. Both branches produce a feedback file at `<output-path>` matching the same structure (defined once below) so Phases 3–7 are reviewer-agnostic.

### Phase 2a — Codex (`reviewer = codex`)

Build the prompt; pipe via stdin:

```bash
codex exec --full-auto - <<'PROMPT'
You are doing a read-only test-coverage audit. Scope: tests only. Identify code paths, branches, edge cases, and contracts added by this plan's uncommitted changes that are NOT exercised by any test. Do not edit any code (the implementer will apply your suggestions if agreed).

Plan: <plan-path>
Output: <output-path>
Repo-local checklist: <checklist-path-or-"none">
Diff scope (uncommitted): <git diff --stat output>
Untracked files: <list>
Prior implementation feedback: <path-or-"none">

Required reads (in order):
1. docs/claude_ops.md (if it exists)
2. docs/lessons.md (if it exists)
3. The repo-local checklist (if specified)
4. The target plan
5. The prior implementation-feedback file (if specified) — note adjudicated items; do NOT re-flag them
6. The uncommitted diff: run `git diff` (unstaged) and `git diff --staged`; read each untracked file in full
7. The current `tests/` layout — `ls -R tests/` plus skim of test files matching the touched modules

Then audit test coverage of the diff:

A TEST GAP is a code path / branch / edge case / contract that:
- Was introduced or materially changed by this diff (must show up in the changes), AND
- Is not exercised by any test in the current branch (unit / integration / migration), AND
- Has a plausible regression mode (silent wrong output, mis-routing, schema drift, etc.).

Look for, but do not limit to:
- New if/elif/match branches with no test hitting each arm.
- New error-raise paths with no test asserting the raise type AND the message regex.
- New optional/keyword params that change behavior but aren't parametrized.
- New protocol implementations whose contract isn't checked end-to-end.
- Plan-listed "Resolved decisions" baked into code without assertions.
- Boundary conditions (date windows, slice counts, threshold edges) without exact-boundary tests (the off-by-one cases).
- New cross-module wires (e.g., manifest → embed → parquet metadata) without round-trip coverage.
- New default values whose behavior changes when explicitly overridden.
- **Substring/structural asserts on generated code as primary verification** (the antipattern). Tests of the form `assert 'X' in rendered_sql` (or rendered JSON / config / formatted output) test what's trivially true in source code, not behavior — they pass coincidentally when the substring lives in unrelated fields. Canonical example: `'ABD(OMEN)?' in rendered_sql` passed at vista-ct because the pattern lived in BOTH `ABD_PEL.study_include_patterns` AND `ABD_PEL.series_include_pattern` (semantically distinct fields used by different helpers); a helper-swap refactor would silently pass. Replace with: render-smoke (acceptable but minimal); upstream-contract assert on the registry/config the render depends on (`CHEST.overlap_with == ('abd_pel',)`); end-to-end behavioral (EXCEPT-DISTINCT, row-count parity, schema-set equality, materialize-and-diff); cross-task behavioral consistency (e.g. 2yr-survival labels ⊂ 3yr-survival labels for the same cohort — death is monotonic); domain-knowledge sanity checks (Stage IV 5yr-mortality > Stage I — cancer biology). Diagnostic question for any assertion in the diff: *"What behavior does this prove?"* — if the only honest answer is "imports + render didn't crash," flag it.
- **Missing cross-task / cross-label logical invariants.** Where data semantics make a relationship logically necessary (2yr survival ⊂ 3yr survival; PFS event ⇒ alive-at-PFS-time; uniqueness on (person_id, task, split); label values ∈ {0, 1, -1}), the absence of an assertion is a gap — these are the highest-leverage tests because they catch label-derivation bugs that branch-coverage misses entirely.
- **Missing domain-knowledge sanity checks.** Be creative, but **prefer relative invariants over absolute assumptions about the data distribution**. Pinning specific percentages ("5yr-survival positive rate is 40-70%") locks in the current cohort's distribution and breaks under legitimate data drift; use relative orderings, ratios, and self-consistency instead. Good shapes: Stage IV mortality > Stage I (relative across stages); 1yr-survival positive rate ≥ 5yr-survival positive rate for the same cohort (relative across time horizons); treatment end-date ≥ start-date per row; median time from diagnosis to first imaging < median time from diagnosis to first treatment (relative across tasks). Bad shapes: absolute thresholds on positive rates, percentages of patients meeting a condition, or any assertion that pins the data distribution. **When you can't decide whether a domain invariant actually holds, mark the gap as Uncertain** so the user can confirm or refute — the user has the domain expertise. Don't drop these; don't fabricate them.

Out of scope:
- Bugs, design critiques, code quality (those are /review-implementation territory).
- Tests for code unchanged by this diff.
- Style nits in existing tests.
- Gaps that fundamentally require compute unavailable in this checkout (GPU, high-throughput batch). Flag explicitly with the constraint; do not synthesize a fake test.
- Items already raised in the prior implementation-feedback file.

Write feedback to <output-path> with this structure:

  Reference: docs/claude_ops.md

  # Test Coverage Feedback: <Plan Title>

  ## Verdict
  Coverage adequate / Add tests before commit / Coverage gap blocks merge. 1-2 sentence summary citing gap count by severity.

  ## Coverage Map
  | Slice / module | Branches added | Branches asserted | Gap? |
  Brief grid; one row per touched module. Use this to ground the rest of the report in measurable terms.

  ## Must-Fix Gaps (block merge)
  - **What:** one-line description of the uncovered branch/contract
  - **Where:** `path:line` of the production code
  - **Why it matters:** plausible regression mode (be specific — "silent CT fallback masks manifest bug", not "could regress")
  - **Suggested test:** layer (unit / migration Layer N / integration) + 1-3 line stub showing the assertion shape (test name + key assertion)
  - **Test file location:** existing test file path, or "new: tests/<path>"

  ## Nice-to-Have Gaps
  - Same shape as Must-Fix, briefer.

  ## Boundary / Edge Cases Worth Pinning
  - Specific values (zero, exact-window-day, empty-collection, single-element) that aren't asserted. One bullet each: value + why it would flip silently.

  ## Out-of-Scope-but-Noted
  - Max 5 items: drift, duplicate sources of truth, hard-coded constants. One line each. Surface once, do not synthesize tests.

  ## Confidence Note
  - One paragraph: what couldn't be verified (BQ-gated, GPU-gated, VM-only fixtures, mounts unavailable). Be specific about which gaps are blocked by which constraint.

  ## Audit Trail
  - Files inspected (paths only).

Standards:
- Lead with highest severity.
- Cite file paths and line numbers for every gap.
- Quote the production-code branch + show the assertion that would close it.
- If a code path IS covered, say so in Coverage Map and move on; don't pad findings.
- Do not write generic feedback like "add more tests" or "improve coverage".
- Suggested tests must be runnable on this checkout — flag infra-blocked gaps separately.

Stop after writing the feedback file. Do not write any test code. Do not edit production code.
PROMPT
```

Notes on flags:

- `--full-auto` enables sandboxed auto-execution with read-only access to the working tree.
- `-C <repo-root>` if invoked from a subdir — Claude Code generally runs at repo root, so usually unnecessary.

Stream Codex's output so the user sees progress. Codex will exit when the feedback file is written. Verify the output file exists and is non-empty before proceeding.

If `codex exec` fails: surface the failure verbatim. Offer to switch to the fresh Claude subagent. **Do not** fall back to inline Claude doing the audit — that defeats the purpose.

### Phase 2b — Fresh Claude Code subagent (`reviewer = claude`)

Spawn a `general-purpose` subagent via the `Agent` tool. The subagent reads the same inputs as the Codex branch, in the same order, and writes the same feedback structure to the same `<output-path>`. Brief it like a smart colleague who hasn't seen this conversation: include the plan path, output path, prior-feedback path, diff scope, and the full audit prompt body (the section between "Then audit test coverage of the diff:" and "Stop after writing the feedback file" above). Cap the subagent's report at <output-path> only — do not let it summarize back; Phases 3–7 read the file.

Run the subagent in the foreground (you need its result before continuing).

## Phase 3 — Read the critique

Read the feedback file in full. Note each finding's severity and category. Don't summarize yet — go straight to classification.

## Phase 4 — Classify each finding

For each gap (in severity order: Must-Fix → Nice-to-Have → Boundary), classify:

- **Agree** — the gap is real. Draft the test stub.
- **Disagree** — the code IS covered (by a test the reviewer missed) OR the gap isn't testable in this checkout (verify the cited code with a Read; verify the absence of coverage with a grep across `tests/`). Articulate the rationale: what test the reviewer missed, with cited evidence.
- **Uncertain** — should be rare. Reserve for high-blast-radius gaps where the test design itself is non-obvious AND you genuinely can't decide. Most gaps cited with file:line evidence resolve to agree/disagree on a quick spot-check.

Bias strongly toward agreement when the reviewer cites specific code/tests with file:line and your spot-check confirms. Disagreement is the highest bar — only if you have stronger evidence than the reviewer did.

*Out-of-Scope-but-Noted* items are not findings to fix — surface them in Phase 6 alongside user-decision questions.

## Phase 5 — Apply Agreed test stubs; surface only genuine disagreements

The user invokes `/review-tests` to get tests *written* before commit. Same gating as `/review-implementation`:

- **Agreed** — `Edit` or `Write` the test file directly at the reviewer's suggested location, using the suggested assertion shape. Don't ask first. Don't batch-confirm.
- **Disagreed** — surface via `AskUserQuestion` for adjudication. Articulate Claude's rationale (what test the reviewer missed) and the reviewer's claim. User picks: side with Claude (no test added) or side with reviewer (apply the stub).
- **Uncertain** — surface via `AskUserQuestion`, same shape.

When the reviewer's suggested assertion is genuinely unclear (e.g., what error-message regex is expected, or what the exact expected output should be), do NOT guess — ask the user inline before writing. Tests with wrong assertions are worse than no tests; they pin behavior the user didn't intend.

When applying many related stubs, group them per-file (one `Edit` or `Write` per test file) rather than dozens of micro-edits.

If there are 0 Disagreed and 0 Uncertain (the common case when the reviewer's evidence is solid), skip `AskUserQuestion` for those and proceed directly to the run gate below.

**Run gate (mandatory):** after writing all agreed stubs, run pytest scoped to the new tests in one invocation. If any fail:

- **Do NOT silently fix.** A failing stub on the first run is information.
- Surface the failure to the user. The cause is one of three:
  1. **The implementation is broken** — genuine catch. Escalate to a code fix; the test stays.
  2. **The reviewer's assertion is wrong** — revert the stub; surface for user to confirm.
  3. **A fixture issue** — fix the fixture and re-run.
- Ask which via `AskUserQuestion`. Don't assume.

If all stubs pass, proceed.

Do not open the feedback file in an app — that's `/read-plan` territory. Mention the path in the Phase 7 summary.

## Phase 6 — Resolve disagreements; surface deviations and questions

After Phase 5:

- Apply user's adjudication for any disagreements.
- **Out-of-Scope-but-Noted** — surface to the user via `AskUserQuestion` (or inline if just one or two): "Reviewer noted these as out-of-scope deltas worth tracking. Add to docs/lessons.md / docs/plans/<followup>.md / dismiss." Don't write them anywhere automatically.
- For "side with Claude" outcomes (user dismissed a reviewer finding), append a one-liner to the feedback file's Audit Trail noting which gap was dismissed and why.

Summarize in one bullet: "Applied: <n> test stubs (passing). Adjudicated: <n>. Dismissed: <n>. Noted-for-followup: <n>."

## Phase 7 — Hand off

If all agreed stubs are passing and no unresolved items remain, the default hand-off is straight to commit:

> Test review complete. <n> tests added, <m> passing. Ready to `/commit-review`?

If unresolved items remain (test stubs failing for unclear reasons, disagreements deferred, or boundary gaps the user wants to address themselves):

> Test review found <n> unresolved items. Address them before `/commit-review`.

Do not auto-invoke `/commit-review`. The user decides when to commit.

## Permission prompts

`Bash(codex exec:*)` will prompt every invocation unless allowlisted. After the first prompt, mention once that the user can allowlist via `/update-config`. Don't re-mention on subsequent runs.

`Bash(pytest:*)` may also prompt for the run-gate step — same advice.

## What NOT to do

- **Don't auto-invoke.** Always gate via `AskUserQuestion`. Reviewer runs cost money and time.
- **Don't proxy inline Claude as the reviewer.** This skill exists *because* self-review isn't independent. If `codex` isn't available and the user declines the Claude-subagent fallback, surface and stop — don't fall back to the current session.
- **Don't write the feedback file yourself.** The reviewer writes it.
- **Don't commit.** This skill stops at "ready to commit"; `/commit-review` owns the commit step.
- **Don't synthesize tests for compute-blocked gaps** (GPU, high-throughput batch). Flag the constraint and stop — a fake test is worse than no test.
- **Don't suppress test failures from the run gate.** A failing stub is information; surface it.
- **Don't skip the boundary-case section.** That's where the highest-leverage gaps usually live (off-by-one, exact-window, empty-collection).
- **Don't re-flag items already adjudicated** in the prior implementation-feedback file. Read it first.
- **Don't audit clean working trees.** No diff = nothing to review; abort early per Phase 1.
- **Don't guess at unclear assertions.** Ask the user. A wrong assertion pins wrong behavior.
