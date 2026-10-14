---
name: review-plan
description: Second-opinion design review of a plan or spec by a fresh Claude Code subagent (or Codex, if Phil asks), then *apply* the agreed critique to the doc. Not a standard step — a spec from /grill is approved by the interview and goes straight to building. Use only (a) on an older long-format plan doc (Approach / Files to Modify / Open Questions / Verification) that is being finished on its own terms, or (b) when Phil explicitly asks for a second opinion on a spec or plan. Invoked via `/review-plan <path> [<output-path>] [--reviewer claude|codex]`. For a spec it checks four things — can each Done-when check fail, are the Deliverables complete, does the Program line resolve, could a fresh session build it. For an older plan it also checks sibling-repo contracts and whether the plan builds something it doesn't need yet. Classifies each finding agree/disagree/uncertain, applies agreed edits, and asks Phil only about real disagreements. Do NOT offer it after /grill or after every plan. SKIP for trivial plans and typo passes.
---

# review-plan

Get a design review of a plan doc from a reviewer that hasn't seen this session. The author of a
plan reviewing their own plan is not independent, so the reviewer is always a fresh subagent (or
Codex) — never the current session.

## When to use it

- **An older long-format plan** (Approach / Files to Modify / Open Questions / Verification /
  Landing & cleanup) that is still being finished. Don't convert it to a spec; review it as it is.
- **Phil asks for a second opinion** on a spec or a plan.

Not otherwise. A spec written by `/grill` is approved when Phil confirms the interview; there is no
pre-build review (`claude_ops.md` → Specs). Don't offer this after `/grill`, and don't put it
between a spec and the build.

## Phase 1 — Resolve inputs

Args: `/review-plan <path> [<output-path>] [--reviewer claude|codex]`.

- **path** — required. If missing, ask via `AskUserQuestion` using `/read-plan`'s detection logic.
- **Format** — a doc with *Done when* and *Deliverables* is a **spec**. One with *Files to Modify*
  and *Verification* is an **older plan**. The checks differ (Phase 2).
- **Reviewer** — default is a fresh Claude Code subagent. Codex CLI is broken as of 2026-10; use
  it only when Phil names it (`--reviewer codex`), and check `command -v codex` first.
- **output-path** — default is a `reviews/` directory beside the plan on the mount:
  `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/<repo>/reviews/`. For a plan still in a
  repo's `docs/plans`, use that repo's mount tree at the same path, not the checkout — an in-repo
  review either costs a read at commit time or, where `docs/plans` is git-ignored, has no copy
  anywhere. File name: `<plan-stem>-feedback-claude.md` or `<plan-stem>-feedback.md` (Codex), so
  two reviewers never overwrite each other. Create the directory if missing.
- **Repo-local checklist** — include `.claude/references/plan-review-checklist.md` if it exists.
  It is authoritative for sibling-repo contracts, schema and dataset versions, and reuse precedents.
- **Repo docs** — include `docs/claude_ops.md` and `docs/lessons.md` as required reads if present.

## Phase 2 — Run the reviewer

### What the reviewer checks

**For a spec**, four things:

1. **Can each Done-when check fail?** A check that passes whatever the code does proves nothing.
   Each needs a concrete pass condition (exit code, a file that must exist and be non-empty, a
   number in a stated range) and the spec needs a *Stop and come back if* line.
2. **Are the Deliverables complete?** Every file, table, run and doc the Goal and Done-when imply
   is on the checkbox list. A deliverable implied but not listed is the one that goes unbuilt.
3. **Does the `Program:` line resolve?** The brief file exists; the stage numbers exist in its
   Stages table; the brief's row for this stage doesn't contradict the spec; nothing in the spec
   re-opens a dated entry in the brief's *Decided already* ledger. No `Program:` line: flag it,
   unless no brief covers this work yet.
4. **Could a fresh session build it?** With only the spec, the code, and what the spec points at:
   are the sibling-repo contracts, the out-of-scope, the *Expensive steps* (host, one-line command,
   pass condition) and the *Landing* (branch, what clears before merge, cleanup) all there? Specs
   carry no implementation steps by design — don't flag their absence.

**For an older plan**, the same last two checks plus:

- **Cross-repo contracts.** For each sibling repo touched, name the API / schema / manifest / output
  contract at stake and check the plan covers its version pin, columns or keys, and migration story.
- **Reuse vs. building something not needed yet.** Where the plan adds config knobs, registries,
  helpers or layer splits, does a realistic use exist (a sibling task, a named cohort, a planned
  migration)? Where new code overlaps existing code, list what is reused vs. re-implemented —
  small re-implementations (routing tables, id-column dicts, dtype rules, status precedence) are
  where drift starts. Flag each; don't assume the one-off is right.
- **Verification.** Does each step say what a good result looks like and what should stop the
  work? Are forks decided in advance?
- **Handoff detail.** Files and line ranges, the sister file to copy from, the schema-of-record and
  every surface that must change with it, coordination with in-flight branches. Flag Open Questions
  scaffolding left behind after every question was resolved.

Plan docs often sit behind an ignored symlink, so `rg` in the checkout finds nothing. Search the
mount (`/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/`) when a claim turns on another plan.
Source precedence when sources disagree: code > tests > docs > plan text.

### Fresh Claude subagent (default)

`Agent` tool, `subagent_type: "general-purpose"`, foreground. Tell it:

- It has not seen any conversation about this plan; that's the point.
- The working directory and absolute paths for the plan, the checklist and the output file.
- The checks above for this doc's format, and the specific claims you want spot-checked (it has
  no other way to know where to look hard).
- Not to read any earlier feedback file — name the path if one exists. Reading it launders the
  first reviewer's framing into a "fresh" pass.
- To write the feedback file even though its system prompt discourages report files; this path
  and structure are the skill's contract.
- Not to edit the plan, implement, or commit. Reply with one sentence: the file path and verdict.

If it reports a Write denial on the mount, offer to add the planning root to
`permissions.additionalDirectories` via `/update-config`. Don't grant it pre-emptively.

### Codex (only if Phil asks)

```bash
codex exec -s workspace-write --add-dir /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning - <<'PROMPT'
<same instructions as the subagent prompt, plus the feedback structure below>
PROMPT
```

- `workspace-write` (not `read-only`): Codex must write its own feedback file.
- `--add-dir` is required. Without it the mount isn't writable, no file appears, and the run looks
  like it worked.
- Check the feedback **file** exists and is non-empty, never the exit code — a piped invocation
  reports the pipeline's status. `--full-auto` no longer exists; use `-s`.
- Don't put `cd ... &&` in front of `codex`.

### Feedback file structure

```
Reference: docs/claude_ops.md

# Feedback: <Title> (Fresh Claude review | Codex review)

## Verdict
Ready / Revise / Blocked. 1-2 sentences.

## Findings
- Severity (Critical | Gap) | Check it falls under | What's wrong | Evidence: path:line | Fix

## Questions For Phil
- Real ambiguities whose answer changes the results, the cost, or what we can conclude.

## Audit Trail
- Files inspected (paths only)
```

Lead with the highest severity, cite paths and lines, and skip generic advice.

## Phase 3 — Classify each finding

Read the whole file, then classify each finding before summarizing anything:

- **Agree** — the finding holds up on a spot-check. Draft the edit.
- **Disagree** — you have stronger evidence than the reviewer. Write down what it got wrong.
- **Uncertain** — rare. Only when the choice changes the plan's direction and the evidence can't
  settle it.

Reuse-vs-one-off findings are Uncertain by default: whether the reusable shape is worth it depends
on future use only Phil can judge. A fresh Claude reviewer shares your model, so a finding that
matches what you already believed deserves a harder spot-check, not a softer one.

## Phase 4 — Apply, then ask only what matters

- **Agreed** — apply the edit directly. Don't ask first. One `Edit` per section, not dozens.
- **Disagreed / Uncertain** — sort by what the answer changes (`claude_ops.md` → Standing rules).
  Changes the results, the cost, or what we can conclude: ask Phil via `AskUserQuestion`, naming
  what changes with each answer and your default. Changes only the shape of the doc or code:
  decide, apply, and record it. A review that asks Phil six shape-of-the-code questions has failed
  this step.
- **Questions For Phil** — for a spec, ask them via `AskUserQuestion` and add each answer to the
  spec's *Decided* list with the date. For an older plan, add them to its Open Questions section,
  merging with any question already there.
- When Phil sides against the reviewer, add a line to the feedback file's Audit Trail saying which
  finding and why.

A spec must stay about one page (~80 lines). If the fixes push it past that, it is two pieces of
work — say so rather than letting it grow. For an older plan that grew more than ~20%, tighten the
prose without dropping any path, number or edge case.

If the plan has a sibling explainer HTML, the edits made it stale. Say so and offer
`/explain-plan` to regenerate it.

## Phase 5 — Hand off

One line: which reviewer ran, findings applied, questions asked or added, the feedback file path.
Then the next step — building, for a spec Phil has approved. Don't offer to commit the doc here:
a spec is committed with the first code that builds it, or never where `docs/plans` is the mount
symlink (see `claude_ops.md` → Specs).

## What not to do

- Don't use the current session as the reviewer, and don't write the feedback file yourself.
- Don't switch reviewers silently. If the chosen one fails, say so and offer the other.
- Don't let a second reviewer read the first one's feedback.
- Don't implement the plan.
