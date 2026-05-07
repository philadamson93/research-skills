---
name: review-plan
description: Independent design audit of a plan doc by Codex CLI or a fresh Claude Code subagent, then *apply* the critique to the plan by default. Use when finishing a critical plan, before the user reads it themselves. Invoked explicitly via `/review-plan <path-to-plan> [<output-path>] [--reviewer codex|claude]`. Also offered proactively after substantial plan-doc work — gated by AskUserQuestion (which surfaces the reviewer choice) since not all plans warrant a review. Codex is preferred for cross-model independence; a fresh Claude Code subagent is the alternative when Codex is unavailable, when the user wants a same-model second opinion, or as a follow-up second-reviewer pass after Codex. **Reviewer is never silently defaulted** — if not specified in args, the skill asks. Runs the chosen reviewer against the plan + repo-local checklist (`.claude/references/plan-review-checklist.md` if present), classifies each finding as agree/disagree/uncertain, then by default *applies* agreed edits directly to the plan. Only surfaces findings for adjudication where Claude genuinely disagrees with the reviewer (not where it flagged user-decision questions — those are preserved in the plan's "Open questions" section). Hands off to `/read-plan` so the user reads the *revised* plan. SKIP for trivial plans, typo-fix passes, or when the user already invoked `/read-plan` for this plan in this session.
---

# review-plan

Get an independent audit of a plan doc by a reviewer that doesn't share the current session's context. Two reviewer options, picked explicitly at invocation:

- **Codex** — cross-model (GPT family). Different blind spots from Claude. Default-recommended for plans that warrant a review.
- **Fresh Claude Code subagent** — same model family, but spawned without conversation context (so it reads the plan + codebase cold). Useful when Codex is unavailable, when running a second-reviewer pass after Codex, or when the user explicitly wants a same-model take.

The skill exists because the author of a plan reviewing their own plan is not independent. Always invoke either Codex via `codex exec` or a fresh subagent via the `Agent` tool — never silently substitute the *current* Claude session as the reviewer.

## When to offer

Proactively offer after finishing substantive plan-doc work — multi-slice plans, schema changes, cross-module refactors, anything that would be expensive to redo if the design is off. Gate the offer behind `AskUserQuestion`. The proactive prompt is the place to surface the reviewer choice:

- *Codex review (Recommended — cross-model independence)*
- *Fresh Claude Code subagent (same model, no conversation context)*
- *I'll run it myself in another tab*
- *Skip — not critical enough*

Do not auto-invoke. Skip the offer for typo fixes, doc tweaks, trivial single-section additions, or refactors that are pure prose-cleanup.

**When to recommend the fresh Claude subagent over Codex** (i.e., when to make it the first option):

- Codex isn't installed / authed in this environment (verify with a quick `command -v codex`).
- The user has *just* run a Codex review on this plan and now wants a second-reviewer pass.
- The user has explicitly asked for a "Claude" or "fresh agent" review.

In all other cases recommend Codex first — model-family independence is the bigger win.

## Phase 1 — Resolve paths, reviewer, and assemble prompt

Args: `/review-plan <plan-path> [<output-path>] [--reviewer codex|claude]`.

- **plan-path** — required. Verify it exists. If invoked without args, ask via `AskUserQuestion` using the same plan-doc detection logic as `/read-plan` Phase 1.
- **reviewer** — required, but never silently defaulted. If `--reviewer codex` or `--reviewer claude` was passed in args, use that. **Otherwise, ask via `AskUserQuestion`** before doing anything else:
  - *Codex (Recommended — cross-model independence)* — unless one of the "recommend Claude" conditions in "When to offer" applies, in which case the Claude option leads with `(Recommended)` instead.
  - *Fresh Claude Code subagent (same model, no conversation context)*
  Don't silent-default — the choice has cost/blind-spot tradeoffs and the user should make it explicitly. The only exception: if the proactive offer (the four-option AskUserQuestion above) already produced the reviewer choice in the same turn, carry it forward without re-asking.
- **output-path** — optional. Default depends on reviewer:
  - `codex` → `docs/plans/reviews/<plan-stem>-feedback.md`
  - `claude` → `docs/plans/reviews/<plan-stem>-feedback-claude.md`
  Create the parent dir if missing. The distinct filenames matter — running both reviewers on the same plan should not overwrite each other's output.
- **Repo-local checklist** — look for `.claude/references/plan-review-checklist.md`. If found, include in the reviewer prompt. If not found, proceed with the generic prompt and warn once that a repo-grounded checklist would yield a sharper review. The checklist is authoritative for repo-specific specifics: sibling-repo contracts, schema/dataset versions, materialized output shapes, VM verification recipes, modularity precedents. The three universal lenses below (VM verification, cross-repo contracts, modularity-vs-YAGNI) are always-on regardless of whether a checklist exists.
- **Sibling repo docs** — if `docs/claude_ops.md` and/or `docs/lessons.md` exist, include them as required reads in the prompt. Otherwise omit those references.
- **Codex availability check** — if reviewer = `codex`, run `command -v codex` first. If absent, surface the failure and offer to switch to the fresh Claude subagent (this is the one auto-fallback path; it's user-visible, not silent).

## Phase 2 — Invoke the chosen reviewer

Branch on reviewer. Both branches produce a feedback file at `<output-path>` matching the same structure (defined once below) so Phases 3–7 are reviewer-agnostic.

### Phase 2a — Codex (`reviewer = codex`)

Build the prompt; pipe via stdin (cleaner than escaping a multi-line argv string):

```bash
codex exec --full-auto - <<'PROMPT'
You are doing a read-only design audit of a plan doc. Do not implement. Do not edit the plan file.

Plan: <plan-path>
Output: <output-path>
Repo-local checklist: <checklist-path-or-"none">

Required reads (in order):
1. docs/claude_ops.md (if it exists)
2. docs/lessons.md (if it exists)
3. The repo-local checklist (if specified)
4. The target plan

Then:
- Map what modules / docs / tests / configs / output contracts the plan affects.
- Read the touched files deeply; verify the plan's assumptions with rg and file reads.
- Source precedence when sources disagree: current code > tests > docs > plan text. Flag conflicts.
- **VM verification (always-on lens)**: confirm the plan names the critical post-merge checks needed to verify the implementation in the *real* runtime — which queries / scripts to run on the VM, against which dataset version, with what inputs, what to compare against. "Unit tests pass on local" is not VM verification. If the plan is silent or hand-wavy about VM-side checks, flag as a Verification Gap with a concrete recipe the plan should add. Defer to the per-repo checklist for the canonical VM verification patterns.
- **Cross-repo contracts (always-on lens)**: identify sibling repos the plan touches (the per-repo checklist enumerates which siblings matter in this codebase). For each, name the specific API / schema / manifest / output contract at stake and verify the plan addresses it: what version pin, what columns/keys/labels, what migration story if breaking. Flag undocumented or broken contracts as Contract Checks. The per-repo checklist is authoritative for which sibling repos exist and what their contracts are.
- **Modularity vs. YAGNI (always-on lens)**: when the plan introduces complexity that *could* be modularized (config knobs, registries, helper extractions, parameterizations, layer splits), assess whether the modular shape would serve a realistic use case the user / project actually has — not a hypothetical one. Bias modular when realistic use is identifiable (a sibling task, a planned migration, a cohort the user has named). Flag as a question for the user when realistic use is unclear. Do NOT silently default to YAGNI just because the immediate task only needs one shape; the user explicitly wants modularity surfaced rather than collapsed by default. The per-repo checklist captures the modularity precedents that already exist in the repo so the reviewer can ground recommendations in them.

[Feedback structure — see "Feedback file structure" below]

Stop after writing the feedback file. Do not implement. Do not edit the plan.
PROMPT
```

Notes on flags:

- `--full-auto` enables sandboxed auto-execution. If your `codex` config requires different flags for non-interactive runs, adjust here.
- `-C <repo-root>` if invoked from a subdir — but Claude Code generally runs at repo root, so usually unnecessary.

Stream Codex's output so the user sees progress. Codex will exit when the feedback file is written. Verify the output file exists and is non-empty before proceeding.

If `codex exec` fails mid-run (not the pre-check above — an actual exec error): surface the failure verbatim. Offer to retry with the fresh Claude subagent; do not auto-retry.

### Phase 2b — Fresh Claude Code subagent (`reviewer = claude`)

Use the `Agent` tool with `subagent_type: "general-purpose"`. The subagent inherits the parent's model but has no conversation context — that's the independence. Prefer foreground (so the user sees progress) unless the user has explicitly asked for background.

**Permission prerequisite:** the subagent must be able to `Write` to the output path. By default subagents can't write outside their allowlist. Before the first invocation in a project, ensure `Write(docs/plans/reviews/**)` is allowlisted in `~/.claude/settings.local.json` (user-level, applies to all repos) or the project's `.claude/settings.local.json`. If the subagent reports Write denials, that's the missing allowlist — surface this and offer to add it via `/update-config`.

Critical instructions to include in the prompt:

- "You have NOT seen any prior conversation about this plan; you're coming to it cold, which is the point."
- "Do not read any existing feedback file" — list the path to skip if a prior reviewer already wrote one (e.g., the Codex feedback file when this is a follow-up pass). Otherwise the subagent's "independence" leaks via prior reviewers' framing.
- Working directory and absolute paths for plan + output, since subagents start with no working-directory context from the parent.
- "Stop after writing the feedback file. Do not implement. Do not edit the plan. Do not commit."
- Tell the subagent to reply with one sentence noting the feedback file path and the verdict — the harness surfaces the rest, and verbose reply burns the parent's context.
- The `general-purpose` subagent's system prompt may include a rule against writing report/summary/findings/analysis .md files. That rule has an exception for **structured plan-review artifacts at controlled paths under `docs/plans/reviews/*-feedback*.md`** — instruct the subagent to write the feedback file regardless of the no-summary rule, since the path and structure are part of the skill's contract.

The prompt body otherwise mirrors the Codex prompt: required reads, mapping step, source precedence, verification of specific plan claims (the parent should pre-list which assumptions to spot-check, since the subagent has no other source for "what to look closely at"), and the Feedback file structure block below.

Verify the output file exists and is non-empty before proceeding to Phase 3. If the subagent finished without writing it, that's likely the missing allowlist — surface and offer to fix.

### Feedback file structure (reviewer-agnostic)

Both reviewers must write to `<output-path>` with this structure. The first-line header should distinguish the reviewer (`(Codex review)` vs `(Fresh Claude Code review)`) so future readers can tell them apart at a glance.

```
Reference: docs/claude_ops.md

# Feedback: <Plan Title> (<reviewer label>)

## Verdict
Ready / Revise / Blocked. 1-2 sentence summary.

## Critical Gaps
- Severity: Critical | Gap | Why it matters | Evidence: path:line | Required fix

## Failure Modes
- Scenario | Why the plan misses it | What to add

## Contract Checks
- In-repo and cross-repo contracts (query / manifest / labels / embeddings / sibling-repo APIs / schema or dataset versions) that need explicit coverage. For sibling-repo contracts, name the owner repo and the specific surface at stake.

## Modularity vs. YAGNI
- Decision point | Plan's current choice | Modular alternative + the realistic use case it would serve | Recommendation, OR "raise to user" when realistic-use is unclear. Do not silently default to YAGNI.

## Verification Gaps
- Missing tests, checks, or rollout validation — including critical VM-side verification recipes (which queries / scripts / dataset diffs to run after merge to confirm correctness in the real runtime, not just unit-test passage)

## Suggested Revisions
- Specific edits the plan author should make

## Questions For The Author
- True ambiguities or high-risk decisions only

## Audit Trail
- Files inspected (paths only)
```

Standards (apply to both reviewers):

- Lead with highest severity.
- Cite file paths and line numbers.
- Be specific about what is wrong, not just what to read.
- If something is correct, say so briefly and move on.
- Do not write generic feedback like "looks good" or "add more tests".

## Phase 3 — Read the critique

Read the feedback file in full. Note each finding's severity and category. Don't summarize yet — go straight to classification.

## Phase 4 — Classify each finding

For each finding (in severity order: Critical → Gap → Failure Mode → other), classify:

- **Agree** — the finding is correct and the proposed fix is right. Draft the plan edit; you'll apply it in Phase 5.
- **Disagree** — the finding is wrong or the proposed fix would harm the plan. Articulate the rationale: what the reviewer got wrong, what the plan's existing approach handles correctly, with cited evidence stronger than the reviewer's.
- **Uncertain** — should be rare. The default expectation is that you can decide between agree/disagree based on the cited evidence + a quick spot-check. Only mark as Uncertain when the choice has high blast radius (changes the plan's core direction) AND you genuinely can't decide from available evidence.

Bias strongly toward agreement when the reviewer cites specific code/tests with file:line and your spot-check confirms. Disagreement is the highest bar — only if you have stronger evidence than the reviewer did. *User-decision questions* the reviewer flagged in its "Questions For The Author" section are NOT findings to classify — they're preserved separately in Phase 6.

**Modularity findings are Uncertain by default.** Whether a modular shape is worth the complexity is fundamentally a user-side product judgment about realistic future use — Claude can't decide it from code alone. Surface modularity findings via `AskUserQuestion` in Phase 5 (with the reviewer's modular alternative as one option, the plan's YAGNI default as another, and Claude's leaning called out) UNLESS the plan author already documented why YAGNI applies here AND the reviewer's evidence is weak. The user has explicitly asked to err toward modularity when realistic use exists, and toward raising-the-question rather than silent defaults when it doesn't.

**Note for fresh-Claude-subagent reviews:** the subagent shares your model family, so it may surface findings that confirm your prior reasoning rather than challenge it. Counter-bias toward stricter spot-checks: if a fresh-Claude finding lines up suspiciously with what you already believed, verify against current code with extra care before applying.

## Phase 5 — Apply Agreed findings; surface only genuine disagreements

The user invokes `/review-plan` to get the plan *revised* before they read it. Gating each agreed edit on user confirmation creates friction before they've even read the plan. So:

- **Agreed** — apply the plan edit directly via `Edit`. Don't ask first. Don't batch-confirm.
- **Disagreed** — surface via `AskUserQuestion` for adjudication. Articulate Claude's rationale and the reviewer's claim. User picks: side with Claude (no edit) or side with the reviewer (apply edit).
- **Uncertain** — surface via `AskUserQuestion` for adjudication, same shape as Disagreed.

If there are 0 Disagreed and 0 Uncertain (the common case when the reviewer's evidence is solid), skip `AskUserQuestion` entirely and go straight to Phase 6.

When applying many related edits, group them into one `Edit` call per plan section (e.g., one Edit for the Cohort section, one for Anatomy, one for Migration tests) rather than dozens of micro-edits.

Do not open the feedback file in an app — that's `/read-plan` territory. Mention the path in the Phase 7 summary so the user can open it themselves if they want.

## Phase 6 — Resolve disagreements; preserve open questions

After Phase 5:

- Apply user's adjudication for any disagreements.
- **Reviewer's "Questions For The Author"** — these are explicit user-decision items, not findings. Append them to the plan's "Open questions" (or equivalent) section verbatim, so the user encounters them during their `/read-plan` pass and can resolve them then. Don't auto-resolve. If a question overlaps an Open Question already in the plan (common on a second-reviewer pass), merge rather than duplicate — keep the version with sharper phrasing.
- For "side with Claude" outcomes (user dismissed a reviewer finding), append a one-liner to the feedback file's Audit Trail noting which finding the user dismissed and why (for future readers).

Summarize in one bullet: "Applied: <n> reviewer findings + <n> user-sided. Not applied: <n> Claude-sided. Open questions preserved: <n>." Include which reviewer ran (Codex or fresh Claude) so the summary is unambiguous when both reviews exist for a single plan.

## Phase 6.5 — Concision pass

Reviews add content; the plan has almost certainly grown. Review-driven additions tend toward verbose prose (full "why" explanations, defensive wording, duplicated code blocks, multi-paragraph rationale around one-line rules). A fresh agent ships the plan — tighter prose helps them scan. **Default behavior: tighten without dropping any edge case.**

**When to run:**
- The plan grew by >~20% from its pre-review line count (track this; the parent saw both versions). OR
- More than 5 findings were applied. OR
- The user has previously flagged plan-doc verbosity as a concern (memory-checkable).

**When to skip:**
- The plan grew by <10% (already tight; the review found little).
- The user explicitly said to keep the doc verbose.
- The plan is already <100 lines (no room to compress).

**When in doubt, ask via `AskUserQuestion`:** "Run a concision pass? Trim ~20–30% lines without dropping edge cases." Three options: tighten prose only (recommended), aggressive (drop borderline edge cases too — surface which), keep as-is.

**How to compress (in priority order):**

1. **Collapse repeated table rows.** When 3+ rows in the file table say the same thing (e.g., per-template fix language for templates with identical fixes), merge into one grouped row + a compact line-number list.
2. **Trim multi-paragraph "why" prose around load-bearing facts.** Each gotcha is a rule + a fix; the rationale fits in one sentence, not three. Same for Open Question recommendations.
3. **Remove duplicated code blocks.** Show each canonical example once; cross-reference the rest. (Common: a code block in the Knobs section AND a referenced re-show in a step — pick one location.)
4. **Compress option enumerations.** "(a) Pros... Cons... (b) Pros... Cons... Recommendation: (a)" → "(a) [one-line], (b) [one-line]. Recommendation: (a) — [one-line why]."
5. **Drop preamble framing.** "This section captures..." / "What follows is..." — fresh agents read top-down; framing wastes attention.

**Don't drop:**
- File paths, line numbers, exact code identifiers, rule-of-fact bullets — these are load-bearing.
- Any genuine edge case the review surfaced. The point is to make edge cases findable in less prose, not to delete them.
- Code blocks where the surrounding prose can't substitute (e.g., the exact thoracic ICD-O-3 code list, the policy-validation assert block, the EXCEPT-DISTINCT diff query).

**Verify:** line-count delta should be 20–30%. If it dropped <10%, the doc was already tight — that's fine. If it dropped >40%, you probably cut content — re-check by diffing pre/post and confirming each removed paragraph has its load-bearing fact preserved elsewhere in the doc.

Report the line delta in the Phase 7 hand-off line so the user knows the pass ran.

## Phase 7 — Hand off

Offer next step in one line, naming the reviewer used and the concision pass result if it ran:

> Plan revised against <Codex|fresh Claude> review (<n> findings applied; <m> open questions; concision pass <pre>→<post> lines, -X%). Want to `/read-plan` it now, run the *other* reviewer (`/review-plan <plan-path> --reviewer <other>`) for a second pass, `/plan-handoff-readiness` first, or commit?

Do not auto-invoke any of these. Suggesting the other reviewer is a useful prompt when the first review found mostly trivial gaps (a sign the plan was already strong) or when the user explicitly wants both perspectives — but it's just an offer; don't push.

## Permission prompts

- `Bash(codex exec:*)` — prompts every invocation unless allowlisted. After the first Codex prompt, mention once that the user can allowlist via `/update-config`. Don't re-mention on subsequent runs.
- `Agent` (subagent_type=general-purpose) — typically allowlisted in the harness; if it prompts unexpectedly, surface the prompt and let the user decide whether to allowlist.

## What NOT to do

- **Don't auto-invoke.** Always gate via `AskUserQuestion`. Reviewer runs cost money and time; not every plan deserves it.
- **Don't silently substitute the current Claude session as the reviewer.** This skill exists *because* the plan's author reviewing the plan isn't independent. If `codex` isn't installed or `codex exec` fails, the only sanctioned fallback is the fresh Claude subagent — and that fallback must be user-visible (offer it; don't auto-switch). Never use this Claude session (with full conversation context) as the reviewer.
- **Don't silent-default the reviewer choice.** If the user invoked `/review-plan` without `--reviewer codex|claude`, ask. The choice has cost and blind-spot tradeoffs the user owns.
- **Don't write a feedback file yourself.** The chosen reviewer writes it.
- **Don't implement the plan.** Process the critique, propose plan edits, hand off.
- **Don't skip uncertainties.** "Maybe right, maybe not" is the most valuable signal — surface it explicitly for user adjudication.
- **Don't summarize the critique before classifying.** Go straight to per-finding classification.
- **Don't let the fresh Claude subagent read prior reviewer feedback.** That would launder the prior reviewer's framing into a "fresh" pass and erode independence. List the prior feedback path in the prompt as a do-not-read.
