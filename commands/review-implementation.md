---
name: review-implementation
description: Independent implementation audit of uncommitted code by Codex CLI against a plan doc, then *apply* agreed fixes to the code by default. Use after a non-trivial implementation completes, BEFORE invoking /commit-review. Invoked explicitly via `/review-implementation <path-to-plan> [<output-path>]`. Also offered proactively after substantial implementation work — gated by AskUserQuestion since not every change warrants a Codex audit. Runs `codex exec` over the uncommitted diff + the plan, classifies each finding as agree/disagree/uncertain, then by default *applies* agreed code edits directly. Only surfaces findings for adjudication where Claude genuinely disagrees with Codex. Hands off to /commit-review on completion. SKIP for typo fixes, single-file refactors, doc-only changes, or anything where the plan-vs-code mapping is trivial.
---

# review-implementation

Get a Codex-side independent audit of uncommitted code against the plan it was meant to implement. Codex's lens differs from Claude's; the delta surfaces drift, missed contracts, and quiet shortcuts.

The skill exists because Claude reviewing its own implementation is not an independent check — Claude wrote the code; Claude already believes the plan was followed. Always invoke Codex via `codex exec` — never substitute Claude as the reviewer.

## When to offer

Proactively offer after finishing substantive implementation work — multi-slice refactors, schema changes, cross-module rewrites, anything that would be expensive to revert if drift is uncaught. Gate the offer behind `AskUserQuestion`:

- *Yes — run Codex implementation review now (Recommended for multi-slice work)*
- *I'll run it myself in another tab*
- *Skip — change is small enough to commit directly*

Do not auto-invoke. Skip the offer for typo fixes, doc-only updates, single-file bug fixes, or trivial refactors where the plan-vs-code mapping is obvious.

This skill runs **before** `/commit-review`, not after. The intended chain is:

```
implementation → /review-implementation → /commit-review → push
```

`/commit-review` checks appropriateness of content; `/review-implementation` checks fidelity to the plan. They answer different questions.

## Phase 1 — Resolve paths and assemble prompt

Args: `/review-implementation <plan-path> [<output-path>]`.

- **plan-path** — required. Verify it exists. If invoked without args, ask via `AskUserQuestion` using the same plan-doc detection logic as `/read-plan` Phase 1 (most-recently-referenced plan in this session, or scan `docs/plans/`).
- **output-path** — optional. Default: `docs/plans/reviews/<plan-stem>-implementation-feedback.md`. Create the parent dir if missing.
- **Repo-local checklist** — look for `.claude/references/implementation-review-checklist.md`. If found, include in the Codex prompt. If not found, proceed with the generic prompt and warn once that a repo-grounded checklist would yield a sharper review.
- **Sibling repo docs** — if `docs/claude_ops.md` and/or `docs/lessons.md` exist, include them as required reads.
- **Diff scope** — capture the current uncommitted state via `git status` and `git diff` (both staged and unstaged) plus a list of untracked files. Codex needs to know exactly what code it's auditing. Include the diff stat (`git diff --stat`) and the names of untracked files in the prompt; let Codex read full file contents itself for anything it needs to inspect deeply.

Verify there is *something* to review:

- If the working tree is clean (no staged, unstaged, or untracked changes), abort with a clear message: "No uncommitted changes — nothing to review against the plan."
- If only doc files changed (no code), warn and ask via `AskUserQuestion` whether to proceed (doc-only changes rarely benefit from a Codex audit).

## Phase 2 — Invoke Codex

Build the prompt; pipe via stdin (cleaner than escaping a multi-line argv string):

```bash
codex exec --full-auto - <<'PROMPT'
You are doing a read-only implementation audit. The user has implemented a plan; verify the uncommitted code matches the plan's spec. Do not edit any code or docs. Do not commit.

Plan: <plan-path>
Output: <output-path>
Repo-local checklist: <checklist-path-or-"none">
Diff scope (uncommitted): <git diff --stat output>
Untracked files: <list>

Required reads (in order):
1. docs/claude_ops.md (if it exists)
2. docs/lessons.md (if it exists)
3. The repo-local checklist (if specified)
4. The target plan
5. The uncommitted diff: run `git diff` (unstaged) and `git diff --staged`, and read each untracked file in full.

Then audit the implementation against the plan:

- For each item in the plan's "Files to Modify" / "Slicing" / "Files / Slices" section, verify the corresponding code change exists and matches the spec.
- Verify behavior contracts the plan calls out (manifest schemas, output paths, SQL fragments, cross-repo paths) are honored byte-for-byte where the plan demands bit-identical behavior, and structurally where it allows refactoring.
- Read touched files deeply; verify imports, registrations, and call sites are wired (don't trust that "added file X" means "X is reachable").
- Check tests: did the plan call for test layers / migration tests / new test files? Are they present and asserting the spec'd contracts (not just smoke-passing)? Flag any test that reads `assert 'X' in rendered_<output>` (substring assert on rendered SQL / JSON / config / formatted output) — those test what's trivially true in source and pass coincidentally when the substring lives in unrelated fields (canonical example: `'ABD(OMEN)?' in rendered_sql` passed at vista-ct because the pattern lived in BOTH `study_include_patterns` AND `series_include_pattern`). The contract should instead be checked behaviorally: end-to-end output diff (EXCEPT-DISTINCT against baseline, row-count parity, schema-set equality), upstream-contract assert on the registry the render depends on, or cross-task logical invariants (2yr-survival ⊂ 3yr-survival for the same cohort).
- Source precedence when sources disagree: actual code > tests > docs > plan text. If the code diverges from the plan, decide whether the divergence is a defensible improvement (call it out) or drift (flag it).

Write feedback to <output-path> with this structure:

  Reference: docs/claude_ops.md

  # Implementation Feedback: <Plan Title>

  ## Verdict
  Ready to commit / Revise before commit / Blocked. 1-2 sentence summary.

  ## Plan Coverage
  Slice / section | Status (Done / Partial / Missing / Drifted) | Evidence: path:line | Notes

  ## Critical Drift
  - Severity: Critical | What the plan says vs. what the code does | Evidence: path:line | Required fix

  ## Missing Pieces
  - Plan item | Where it should land | Why it matters | Suggested code change

  ## Contract Violations
  - Manifest / SQL / output-path / cross-repo / labels contract that drifted from the plan's stated shape

  ## Test Gaps
  - Tests the plan called for that are missing, weak, or assert the wrong thing

  ## Defensible Deviations
  - Code that diverges from the plan but appears intentional and an improvement; flag for the author to confirm

  ## Suggested Code Edits
  - Specific edits the implementer should make (file:line + concrete change)

  ## Questions For The Author
  - True ambiguities or high-risk decisions only

  ## Audit Trail
  - Files inspected (paths only)

Standards:
- Lead with highest severity.
- Cite file paths and line numbers for every finding.
- Be specific about what the plan says vs. what the code does — quote both sides briefly.
- If something matches the plan, say so in Plan Coverage and move on; don't pad findings.
- Do not write generic feedback like "looks good" or "add more tests".

Stop after writing the feedback file. Do not implement. Do not edit the plan or any code.
PROMPT
```

Notes on flags:

- `--full-auto` enables sandboxed auto-execution with read-only access to the working tree.
- `-C <repo-root>` if invoked from a subdir — Claude Code generally runs at repo root, so usually unnecessary.

Stream Codex's output so the user sees progress. Codex will exit when the feedback file is written. Verify the output file exists and is non-empty before proceeding.

If `codex exec` fails (not installed, auth issue, sandbox refusal): surface the failure verbatim. **Do not** fall back to Claude doing the audit — that defeats the purpose of this skill.

## Phase 3 — Read the critique

Read the feedback file in full. Note each finding's severity and category. Don't summarize yet — go straight to classification.

## Phase 4 — Classify each finding

For each finding (in severity order: Critical Drift → Missing Pieces → Contract Violations → Test Gaps → other), classify:

- **Agree** — the finding is correct. Draft the code edit; you'll apply it in Phase 5.
- **Disagree** — the finding is wrong (Codex misread the plan, missed an existing wire-up, or proposes a regression). Articulate the rationale: what Codex got wrong, what the implementation actually does, with cited evidence stronger than Codex's.
- **Uncertain** — should be rare. The default expectation is that you can decide between agree/disagree based on the cited evidence + a quick spot-check (Read the file Codex cited; confirm or refute). Only mark as Uncertain when the choice has high blast radius (changes architecture / output contracts) AND you genuinely can't decide from available evidence.

Bias strongly toward agreement when Codex cites specific code/tests with file:line and your spot-check confirms. Disagreement is the highest bar — only if you have stronger evidence than Codex did.

*Defensible Deviations* are not findings to fix — they are deltas Codex wants confirmed. Surface them in Phase 6 alongside the user-decision questions.

## Phase 5 — Apply Agreed findings; surface only genuine disagreements

The user invokes `/review-implementation` to get the code *fixed* before they commit. Gating each agreed edit on user confirmation creates friction:

- **Agreed** — apply the code edit directly via `Edit`. Don't ask first. Don't batch-confirm.
- **Disagreed** — surface via `AskUserQuestion` for adjudication. Articulate Claude's rationale and Codex's claim. User picks: side with Claude (no edit) or side with Codex (apply edit).
- **Uncertain** — surface via `AskUserQuestion` for adjudication, same shape as Disagreed.

If there are 0 Disagreed and 0 Uncertain (the common case when Codex's evidence is solid), skip `AskUserQuestion` for those and go straight to Phase 6.

When applying many related edits, group them into one `Edit` call per file or logical unit (e.g., one Edit per slice's files) rather than dozens of micro-edits.

Do not open the feedback file in an app — that's `/read-plan` territory. Mention the path in the Phase 7 summary so the user can open it themselves if they want.

## Phase 6 — Resolve disagreements; surface deviations and questions

After Phase 5:

- Apply user's adjudication for any disagreements.
- **Defensible Deviations** — surface to the user via `AskUserQuestion` (or inline if just one): "Codex flagged these as deltas from the plan that look intentional. Confirm each is correct, or revert." For each, the user picks: keep deviation / revert to plan.
- **Codex's "Questions For The Author"** — these are explicit user-decision items. List them inline for the user to address before commit. Don't auto-resolve.
- For "side with Claude" outcomes (user dismissed a Codex finding), append a one-liner to the feedback file's Audit Trail noting which finding the user dismissed and why (for future readers).

Summarize in one bullet: "Applied: <n> Codex findings + <n> user-sided. Not applied: <n> Claude-sided. Deviations confirmed: <n>. Open questions: <n>."

## Phase 7 — Hand off

If the implementation is now aligned with the plan, decide whether to offer a deeper test-coverage review before commit. **Offer `/review-tests` when** any of the following hold:

- The Codex feedback file's "Test Gaps" section was non-empty (whether or not it was acted on).
- The diff introduces non-trivial new branches, raise paths, optional/keyword params, protocol implementations, or boundary conditions.
- The plan's "Resolved decisions" or contracts include items not obviously asserted by existing tests.

Skip the offer for typo fixes, doc-only changes, or refactors where the existing test suite already exercises every new branch end-to-end.

When offering, surface via `AskUserQuestion`:

- *Codex test-coverage review (Recommended — cross-model independence)*
- *Fresh Claude Code subagent (same model, no conversation context)*
- *Skip — coverage is adequate as-is*

If the user picks a reviewer, invoke `/review-tests <same-plan-path> --reviewer <choice>` in the same turn — `/review-tests` owns its own flow from there. If the user picks Skip, or no offer was warranted, hand off to commit:

> Implementation review complete. Ready to `/commit-review`?

If material deviations or unresolved questions remain from the implementation review itself, surface them and pause:

> Implementation review found <n> unresolved items. Address them before `/commit-review`.

Do not auto-invoke `/commit-review` or `/review-tests`. The user decides whether to add tests and when to commit.

## Permission prompts

`Bash(codex exec:*)` will prompt every invocation unless allowlisted. After the first prompt, mention once that the user can allowlist via `/update-config`. Don't re-mention on subsequent runs.

## What NOT to do

- **Don't auto-invoke.** Always gate via `AskUserQuestion`. Codex runs cost money and time.
- **Don't proxy Claude as the reviewer.** This skill exists *because* Claude self-review isn't independent. If `codex` isn't installed or `codex exec` fails, surface the failure — don't fall back to Claude doing the audit.
- **Don't write a feedback file yourself.** Codex writes it.
- **Don't commit.** This skill stops at "ready to commit"; `/commit-review` owns the commit step.
- **Don't re-implement.** Apply Codex's specific edits as found; don't rewrite swathes of code under the cover of "fixing drift".
- **Don't skip uncertainties.** "Maybe drifted, maybe not" is the most valuable signal — surface it explicitly for user adjudication.
- **Don't summarize the critique before classifying.** Go straight to per-finding classification.
- **Don't audit clean working trees.** No diff = nothing to review; abort early.
