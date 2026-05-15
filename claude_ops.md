# Claude Code Operating Standards

This document defines how Claude Code should operate across all VISTA repos. Reference this file at the start of every planning document.

---

## Core Principles

1. **Plan before you code.** Always enter Plan mode (Shift+Tab twice) before writing any code. Iterate on the plan until it's solid, then execute.

2. **Re-enter plan mode when direction changes.** If you discover a new issue, architectural concern, or change in direction while implementing, pause and re-enter plan mode to get feedback before continuing.

3. **A wrong fast answer is slower than a right slow answer.** Prioritize correctness over speed. Use thinking mode for complex tasks.

4. **You don't trust; you instrument.** Always provide verification mechanisms. Feedback loops multiply output quality 2-3x.

5. **YAGNI (You Aren't Gonna Need It).** Don't build for hypothetical futures. Implement what's needed now, nothing more.

---

## Environment Constraints

- **No code execution on this machine.** All training, evaluation, and pipeline runs happen on a separate VM. This machine cannot run Python, tests, formatters, linters, or any code.
- **Do not run `ruff`, `black`, `isort`, `mypy`, `pytest`, or similar tools.** They are not installed or configured correctly on this machine. Verification is structural code review only.
- **Data paths are VM-specific.** Paths like `/mnt/su-vista/...` reference the VM filesystem, not this machine.

This is the *simple single-machine default* — assumed by all VISTA repos. Repos where execution depends on which machine you're on should declare so explicitly and override this rule via the Machine-Aware Operating Mode section below.

---

## Machine-Aware Operating Mode

For repos where the executor / planner split is hostname-dependent (a project VM holds the runtime + credentials, the local Mac is planner-only), this section overrides **Environment Constraints** above.

1. **At session start, run `hostname`** to determine which mode applies.
2. **The repo declares its machine posture** — typically in `CLAUDE.md` or a dedicated registry like `docs/machines.md`. The registry names known hosts and assigns each one Executor or Planner role, plus PHI posture if relevant.
3. **Executor mode** (a project VM with data, credentials, and a runtime):
   - Run queries, scripts, and exploration as directed by plan docs.
   - Minor iterative corrections when data reveals something unexpected.
   - Commit results frequently.
   - Don't broad-plan or major-rewrite without user confirmation — if scope changes significantly, document the finding and defer to a new plan.
4. **Planner mode** (typically the local Mac):
   - Planning, template authoring, spec writing, doc review.
   - Do not run code or query data — credentials and data paths usually aren't here.
5. **Unknown hostnames**: ask the user which mode applies rather than hard-refusing or assuming. After confirming, offer to register the hostname in the repo's machine registry so the next session doesn't re-prompt.

Repo-specific bindings (concrete hostnames, package-manager rules, sibling-repo paths, PHI gate choice) live in the repo's `CLAUDE.md` or machine registry — not here. This section defines the *pattern*; each repo declares its *parameters*.

---

## Session Start

Quickly check if the global skills repo (canonical path: `~/code/research-skills`) is substantially behind `origin/main` before starting work:

```bash
git -C ~/code/research-skills fetch --quiet 2>/dev/null && \
  git -C ~/code/research-skills log HEAD..origin/main --oneline 2>/dev/null | head
```

If the local clone is **3+ commits behind**, suggest a `git -C ~/code/research-skills pull --ff-only` before starting — mid-session skill-spec drift (a `/wrapup` or `/review-plan` invocation reading a different version than expected) is harder to reason about than a clean pull at the start. If 0–1 commits behind or the path doesn't exist on this machine, skip silently.

---

## Planning Workflow

### Starting a Task

1. Enter Plan mode before any implementation
2. **Read relevant documentation first.** Search `docs/` and the codebase for existing patterns, utilities, and context before proposing solutions. Understand what exists before suggesting changes.
3. Draft the plan in plan mode's internal file (the only file plan mode allows writing to)
4. Begin the plan document with:
   ```
   Reference: docs/claude_ops.md
   ```
5. Articulate both *what* you're building and *why*
6. Ask: "Are there any points of ambiguity about this plan?" to surface underspecified requirements
7. Iterate on the plan until solid, then exit plan mode

### Saving the Plan (after exiting plan mode)

**Important: Plan mode limitation.** Claude Code's plan mode can only write to its internal plan file (`~/.claude/plans/`). It **cannot** write to `docs/plans/` in the repo. This creates a two-step process:

1. **Exit plan mode** — this approves the *plan content*, not implementation
2. **Immediately save to `docs/plans/`** — copy the plan to the repo with a descriptive filename (not `plan_01.md`). This ensures traceability and allows the user to review plans across sessions.
3. **Stop and confirm** — ask the user before starting implementation. Do not create task lists, write code, or make any changes beyond saving the plan doc.

Exiting plan mode ≠ "start coding." Treat it as "plan content approved, now persist it."

### When to Re-enter Plan Mode

- Discovering the current approach won't work
- Uncovering a new requirement or constraint
- Realizing the scope is larger than expected
- Finding an architectural issue that affects the design
- Any time you're uncertain whether to proceed

### Plan Document Structure

```markdown
Reference: docs/claude_ops.md

# [Descriptive Task Title]

## Goal
What are we building and why?

## Approach
How will we implement this?

## Files to Modify
- path/to/file.py - description of changes

## Open Questions
- Any ambiguities to resolve?

## Verification
How will we know this works?
```

### After Completing a Plan

- **Update all affected documentation** when a plan is implemented. Fix stale paths, CLI examples, import references, and cross-links in `docs/`.
- **Mark plan docs as completed** by adding `**Status: Completed** (date)` at the top.
- **Update the plans README** (`docs/plans/README.md`) feature table with the new status.

### VM-status docs are for smoke tests only — not for eval results

`docs/vm-status/<date>-<sha>.md` reports are for **smoke-test / verification handoffs** between sessions: aggregator runs needing structural readback, full test sweeps with expected reds to characterize, end-to-end pipeline validation. Once a workstream has moved past smoke tests into producing eval results (linear-probe runs, KNN runs, cross-modality comparisons), don't propose vm-status docs — the user reads results directly from the auto-generated HTML at `<results-root>/<version>/<modality>/<dataset>/reports/<model>_<dataset>.html` plus the on-disk per-task / per-example parquets, and writes any narrative themselves. Backlog / next.md entries that *reference* such results with a one-line pointer are still fine.

---

## Code Quality Standards

### Re-use Over Duplication

- Always check for existing utilities before writing new code
- Extend existing classes/functions rather than creating parallel implementations
- Prioritize modularity and clean code over expediency

### Simplicity

- Write the simplest code that solves the problem
- Avoid unnecessary abstractions
- Don't add features that aren't explicitly requested

### YAGNI vs Modularity — Raise Genuinely Uncertain Cases

YAGNI (Principle #5) and modularity / re-use pull in opposite directions: YAGNI says don't build seams for hypothetical futures; modularity says factor seams so the next caller doesn't duplicate. Use best judgement on the obvious cases (one-off script → inline it; third caller landing in the same module → extract). **When the call is genuinely uncertain — reasonable engineers would disagree — raise it as an `AskUserQuestion` rather than committing silently.** Two right moments to ask:

- **During exploration, before writing the plan doc** — if the shape of the abstraction hinges on a design call you can't make alone, ask before drafting, so the plan opens on the chosen branch instead of relitigating it.
- **While writing the plan doc** — surface the fork in `## Open Questions` and / or via `AskUserQuestion` so the user decides before the plan locks in a direction.

Don't paper over the tension with a hedge ("I'll extract it if needed later"); name it and resolve it.

---

## Git Practices

### Before Committing

- **Always check and report the current branch.** Before any commit, verify which branch you're on and tell the user. Never assume you're on the expected branch.
- Confirm with the user if the branch seems unexpected for the task.

### Feature Branching

- **Major changes should be made in a new feature branch**, not directly on main.
- Documentation updates and minor bug fixes can go directly on main.

### Commit Messages

- **No AI attribution.** Never include "Co-Authored-By: Claude" or similar
- **One sentence per commit.** Keep messages concise and descriptive
- **Thematic separation.** Split changes into separate commits by theme:
  - One commit for config changes
  - Another for core logic changes
  - Another for documentation updates

### Commit Frequency

- Commit frequently to maintain clean revert points
- Each commit should represent a coherent, working state

---

## Communication Standards

### Ask Clarifying Questions For:

- Functional requirements (what to build, how it should behave)
- Ambiguous specifications
- Decisions that significantly affect architecture
- Anything where assumptions could lead to wasted work
- **Fallback vs exception behavior**: Don't assume fallbacks are preferred — they can mask upstream errors. Ask the user explicitly.
- **Testing plans**: Brainstorm which aspects are testable, critical to test, and what can be mocked vs needs integration testing. Get user input before writing tests.

### Use Your Judgement For:

- Implementation details (variable names, code patterns)
- Internal structure decisions
- Standard refactoring choices
- Obvious bug fixes

### Document Non-Obvious Decisions

If you make a choice that isn't obvious, note it briefly in:
- Code comments (sparingly)
- Commit messages
- The planning document

---

## Institutional Memory

### When Claude Makes Mistakes

Add learnings to `CLAUDE.md` so they don't repeat. Examples:
- "Don't modify X without also updating Y"
- "Always run Z before committing changes to W"
- "The config parameter `foo` must be set when using feature `bar`"

### When Patterns Emerge

Document recurring patterns in the appropriate `docs/` file to help future sessions.

---

## Pre-Commit Review

For non-trivial changes, use the research-skills review workflows instead of inline subagent prompts:

- **`/review-plan <plan-path>`** — independent design audit of a plan doc (Codex CLI or fresh Claude subagent), then applies agreed feedback. Run after substantial plan-doc work, before implementation.
- **`/review-implementation <plan-path>`** — implementation audit of uncommitted code against the plan. Run after non-trivial implementation completes, before `/commit-review`.
- **`/review-tests <plan-path>`** — test-coverage audit of uncommitted code against the plan. Run after `/review-implementation` when the change introduces new branches / contracts / edge cases worth regression-protection.
- **`/commit-review`** — commit workflow with appropriateness review (catches accidentally-leaked private content) before commit + push. Use this rather than running `git commit` inline.
- **`/phi-vet`** — hard PHI gate for medical-data repos. `/commit-review` escalates to it automatically for repos that touch BigQuery / OMOP / NeuralFrame / DICOM / EHR / WSI / pathology bucket / vista_bench. Do not silently fall back to inline sweeps.
- **`/plan-handoff-readiness`** — pre-implementation handoff check: does the plan POINT AT or STATE DIRECTLY everything a fresh agent needs?

Skip the review skills for trivial changes (single-file fixes, doc tweaks, formatting). Each skill carries its own guidance on what it checks, when to skip, and how findings get applied.

**All spawned subagents must be instructed not to run code.** This machine has no runtime environment — no Python, no GPU, no data. Include "Do NOT run any code" in every subagent prompt.

---

## Context Management

- **Fresh sessions for fresh tasks.** Start new sessions when switching to unrelated work
- **Match rigor to stakes.** Prototypes allow looser constraints; production changes require thorough planning and review

---

## Verification Approaches

Always define how you'll verify changes work. Since code cannot run on this machine, verification means describing expected behavior for the user to confirm on the VM.

Remember: Give Claude a way to verify its work. This is the single most important factor in output quality.

---

## Skill Composition

Slash commands (skills) are a design layer above bespoke code, and the way they're authored, invoked, and composed is itself a discipline:

- **Invocation discipline.** Expensive skills — multi-agent workflows, large parallel-search passes, anything that spends significant context budget — must never be auto-invoked from trigger cues alone. When a candidate situation surfaces, summarize the fork in one sentence and offer the skill via `AskUserQuestion` alongside lighter-weight alternatives. The user owns the decision to spend that budget. Cheap skills (e.g. `/read-plan`, `/next`) can be invoked on direct user signal without confirmation.

- **Skills can reference other skills.** A skill's markdown file is not a self-contained island. When two skills overlap on a procedure, point at the canonical one (e.g. "see `/commit-review` for the appropriateness review step") rather than duplicating the body. The same modularity discipline that applies to code applies to prose: it keeps drift down and lets each skill stay focused on what it uniquely contributes.

- **Need-to-know context delivery for subagents.** When the main session delegates to a subagent, do not pour the full context of the main session into the subagent prompt. Point the subagent at the relevant sub-skill or sub-doc and give it just enough to know what to read. The main session does not need to hold the subagent's full procedure in context — the subagent does, on demand, while it is running.

- **Markdown-first when building larger workflows.** When asked to build out a multi-step workflow, default to writing a skill (markdown) FIRST and only then writing code that the skill will invoke. The default bias is toward bespoke single-purpose Python scripts that solve the immediate task and then rot — markdown skills capture intention, goals, resources, success criteria, and the "when to invoke / when to skip" gates that one-off code drops on the floor. Code still gets written; it is downstream of the skill that frames it. Many small coding tasks will not benefit from this layering — apply it when the workflow has multiple steps, multiple invocation modes, or will be re-run across sessions.

- **Surfacing new skill opportunities.** When the user repeatedly performs the same multi-step workflow (commit + push, cross-repo status checks, deploy verification, etc.), surface the option to extract it as a slash command in `~/.claude/commands/`. Keep the suggestion lightweight — only when the pattern has clearly appeared 2+ times — and follow the markdown-first principle above when authoring it.
