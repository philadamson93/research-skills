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

## Pre-Commit Review Agents

Before committing, run two independent review passes using subagents. These are mandatory for any change that touches production code or tests — **except minor changes** (single-file fixes, small refactors, config tweaks, doc-only updates), which can skip review agents.

**All spawned subagents must be instructed not to run code.** This machine has no runtime environment — no Python, no GPU, no data. Include "Do NOT run any code" in every subagent prompt.

### Test Review Agent

**Always run this agent for any production code change.** It has two jobs: (1) review any new/modified test code for quality, and (2) assess test coverage gaps and suggest new tests that should be written.

The agent should check:

**If tests were written or modified:**
- **Behavior over implementation.** Tests should assert observable outcomes (query results, DataFrame contents, return values), not implementation details (string counts, internal SQL structure, JOIN types).
- **Fragility.** Would the test break if an unrelated part of the code changes? If yes, rewrite.
- **Coverage.** Do the tests cover the cases listed in the plan doc? Any gaps?
- **False positives.** Could the test pass even if the feature is broken? (e.g., an assertion that's always true)
- **Fixture reuse.** Are existing fixtures reused where possible, or is there unnecessary duplication?
- **Data contracts.** Do tests validate critical stage-boundary contracts (required fields, nullability, key uniqueness, and type invariants)?

**Always (even if no tests were written):**
- **Coverage gaps.** What new tests should exist for the implemented features? Be specific — name the test functions, describe what they assert, and identify which module they belong in.
- **Unit tests:** New public functions, edge cases, error paths.
- **Integration tests (within repo):** End-to-end flows within the repo.
- **Cross-repo integration:** If changes affect contracts between repos (e.g., schema, column names, path conventions), are there tests on both sides that would catch breakage?
- **Priority ranking.** Rank suggested tests by importance (critical / nice-to-have) so the user can decide what to write.

Prompt template:
```
IMPORTANT: Follow docs/claude_ops.md. Do NOT run any code — this machine has no runtime environment. Your job is read-only review.

Review all new/modified test code in this session (if any). For each test, assess:
1. Does it test behavior or implementation details?
2. Is it fragile (would unrelated changes break it)?
3. Does it match the plan doc spec?
4. Could it produce false positives?

Then assess test coverage for ALL implemented features — even if no tests were written yet:
- What new tests should exist? Name specific test functions and describe what they assert.
- Unit tests: New public functions, edge cases, error paths.
- Integration tests (within repo): End-to-end flows.
- Cross-repo integration: Contract tests for shared schemas/paths.
- Rank each suggested test as critical or nice-to-have.

Report issues with specific file:line references and suggested fixes.
```

### Implementation Review Agent

After completing implementation, spawn a separate subagent to review all changes for fidelity and standards. The agent should check:

- **Plan fidelity.** Do the code changes match what the plan doc specifies? Any deviations, missing pieces, or scope creep?
- **claude_ops compliance.** Were operating standards followed? (plan doc created, thematic commits, no AI attribution, docs updated, etc.)
- **Code quality.** YAGNI, simplicity, no unnecessary abstractions, re-use over duplication.
- **Completeness.** Are all files listed in the plan's "Files to Modify" section actually modified? Are docs/README updated?
- **Security.** No PHI exposure, no credentials, safe SQL construction.

Prompt template:
```
IMPORTANT: Follow docs/claude_ops.md. Do NOT run any code — this machine has no runtime environment. Your job is read-only review.

Review all changes in this session against the plan doc at docs/plans/<plan>.md. Check:
1. Do changes match the plan spec exactly?
2. Were claude_ops procedures followed?
3. Any code quality issues (YAGNI violations, unnecessary complexity)?
4. Are all docs updated?
Report issues with specific file:line references.
```

---

## Adversarial Debate for Major Design Decisions

For major architectural or design decisions (repo structure, framework choices, API design patterns), use a structured adversarial debate:

1. **Spawn two agents** — one advocates for each option (e.g., monorepo vs. multi-repo)
2. **Each agent prepares an opening argument** (800-1200 words) grounded in the actual codebase — no generic reasoning
3. **The main agent moderates multiple rounds**, raising considerations specific to the use case and desired criteria
4. **Synthesize** the debate into a decision document with clear rationale

This pattern is for decisions where reasonable people disagree, the stakes are high, and the wrong choice is expensive to reverse. Do not use it for routine implementation choices.

**When to trigger:** Cross-repo architecture, build system choices, data contract design, config system design, major API surface changes.

---

## Context Management

- **Fresh sessions for fresh tasks.** Start new sessions when switching to unrelated work
- **Match rigor to stakes.** Prototypes allow looser constraints; production changes require thorough planning and review

---

## Verification Approaches

Always define how you'll verify changes work. Since code cannot run on this machine, verification means describing expected behavior for the user to confirm on the VM.

Remember: Give Claude a way to verify its work. This is the single most important factor in output quality.

---

## Slash Commands

If you notice the user repeatedly performing the same multi-step workflow (e.g., commit + push, deploy review agents, cross-repo status checks), suggest creating a slash command in `~/.claude/commands/` to automate it. Keep suggestions lightweight — only when a pattern has clearly appeared 2+ times.
