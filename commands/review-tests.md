---
name: review-tests
description: Test-coverage review of new code by a fresh Claude Code subagent (Codex only if Phil asks), against a spec (Done when + Deliverables) or an older plan doc (Files to Modify + Verification), then *apply* agreed test stubs and run them. Use after /review-implementation, BEFORE /commit-review, when the change adds branches, raise paths, optional parameters or boundary conditions worth protecting against regressions. Invoked via `/review-tests <path-to-spec-or-plan> [<output-path>] [--reviewer claude|codex]`. Also offered at the end of /review-implementation. Classifies each gap agree/disagree/uncertain, writes agreed tests, runs them, and asks Phil only about real disagreements. SKIP for typo fixes, doc-only changes, or when existing tests already cover the change end to end.
---

# review-tests

Find code paths the change added that no test exercises, then write the tests. `/review-implementation`
asks whether the work matches the spec; this asks only whether it's protected against regressions.
The builder already believes coverage is fine, so a fresh subagent does the review, never the
current session.

## Phase 1 — Resolve inputs

Args: `/review-tests <path> [<output-path>] [--reviewer claude|codex]`.

- **path** — the spec or older plan. Read *Done when* / *Decided* from a spec, or *Verification* /
  resolved Open Questions from an older plan: those are the behaviors tests should pin.
- **Reviewer** — default is a fresh Claude Code subagent. Codex CLI is broken as of 2026-10; use
  it only when Phil names it, with the same flags and gotchas as `/review-implementation`.
- **Diff baseline** — merge-base with `main` plus uncommitted changes. Empty: stop. Only docs or
  only tests changed: ask whether it's worth it.
- **Prior implementation feedback** — `<plan-stem>-implementation-feedback.md` in the same reviews
  directory. The reviewer must not re-flag what was already settled there.
- **output-path** — default `<reviews-dir>/<plan-stem>-test-coverage-feedback-claude.md` (or
  without `-claude` for Codex), reviews directory as in `/review-implementation`.
- **Checklist** — include `.claude/references/test-review-checklist.md` if it exists.

## Phase 2 — Run the reviewer

`Agent` tool, `subagent_type: "general-purpose"`, foreground. Give it the paths above, tell it to
write the feedback file despite its no-report-files rule (this path is the skill's contract), not
to write tests or edit code, and to reply with one sentence. Its brief:

A gap is a path, branch or contract that this diff added or changed, that no current test
exercises, and that could regress silently. Look for:

- Branches with an untested arm; raise paths with no test of the exception type and message.
- Optional or keyword parameters that change behavior; changed defaults.
- Decisions from the spec baked into code with nothing asserting them.
- Boundaries: zero, empty, exact window edges, off-by-one.
- Cross-module wiring (manifest → embedding → parquet metadata) with no round-trip test.
- **Substring checks on rendered SQL, JSON or config** used as the main test. At vista-ct,
  `'ABD(OMEN)?' in rendered_sql` passed because the pattern sat in two unrelated fields; a helper
  swap would have passed too. Ask of each assertion "what behavior does this prove?" Prefer a
  diff against a baseline, row-count parity, an assert on the registry the render depends on.
- **Logical invariants the data requires**: 2-year survival positives ⊂ 3-year; one row per
  (person_id, task, split); labels in {0, 1, -1}.
- **Domain sanity checks, relative not absolute**: Stage IV mortality > Stage I; end date ≥ start
  date. Never pin a positive rate or a percentage — that breaks on legitimate data drift. When
  unsure an invariant holds, mark the gap Uncertain for Phil rather than drop or invent it.

Out of scope: bugs and design (that's `/review-implementation`), unchanged code, style nits in
existing tests. Gaps that need a GPU or heavy batch compute: name the constraint, don't propose a
fake test.

Feedback structure: **Verdict** (adequate / add tests before commit / gap blocks merge) →
**Coverage map** (one row per touched module: branches added, branches asserted) → **Must-fix
gaps** (what, production `path:line`, how it would regress, test layer and a 1-3 line stub, test
file) → **Nice-to-have** → **Boundary values** → **Noted, out of scope** (max 5) → **What couldn't
be checked** (BigQuery, GPU, VM-only fixtures) → **Files inspected**.

Check the file exists and is non-empty before going on.

## Phase 3 — Classify, apply, run

Classify each gap: **Agree** (it's real), **Disagree** (a test the reviewer missed covers it —
show which, after a grep across `tests/`), **Uncertain** (rare: the test design itself is unclear
and matters).

- **Agreed** — write the test at the suggested location. One `Edit`/`Write` per test file. If the
  right assertion is unclear (the error message, the exact expected output), ask Phil before
  writing it. A wrong assertion pins behavior nobody wanted.
- **Disagreed / Uncertain** — ask Phil via `AskUserQuestion` only when the answer changes what we
  can conclude; otherwise decide and note it in the feedback file's last section.
- **Run the new tests**, in one scoped pytest call. A failing new test is information, not
  something to quietly fix. Ask Phil which it is: the code is wrong (fix the code, keep the test),
  the assertion is wrong (revert the test), or the fixture is wrong (fix it and re-run).
- **Noted, out of scope** items: show them to Phil; don't file them anywhere yourself.

## Phase 4 — Hand off

> Test review: <n> tests added, all passing; <m> decided by Phil. Feedback at <path>. Ready to
> `/commit-review`?

With unresolved items, list them and stop. Don't commit here.
