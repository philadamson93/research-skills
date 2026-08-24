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

- **Code execution is allowed on this machine**, gated by the same `phi-vet` discipline that already governs commits — not blocked outright. Claude Code for Education covers Phil's Mac and his project VMs alike, so "no PHI clearance here" is no longer a reason to refuse.
- **GPU training and high-throughput batch still run on the VM fleet** — a capacity constraint, not a compliance one. This machine typically lacks that hardware; `ruff`, `black`, `isort`, `mypy`, `pytest`, and similar tools may still not be installed/configured for a given repo's env here (check the repo's own `uv` env / machine registry), but that's a per-repo setup question, not a blanket prohibition.
- **Data paths may be VM-specific or locally mounted**, depending on the repo. Paths like `/mnt/su-vista/...` reference the VM filesystem; check the repo's machine registry (Machine-Aware Operating Mode below) before assuming a path isn't reachable from here.

This is the *simple single-machine default* — assumed by all VISTA repos. Repos where execution depends on which machine you're on (GPU/throughput routing, not PHI) should declare so explicitly and override this rule via the Machine-Aware Operating Mode section below.

---

## Machine-Aware Operating Mode

Any machine running Claude Code — the Mac, a project VM, whichever — has **full parity**: plan,
implement, verify, and commit, the same discipline everywhere. There is no "planner" role
confined to one machine and an "executor" role confined to another; a session discovering that
a plan assumption was wrong doesn't hand off to a different machine to decide what to do about
it — it reconsiders, revises the approach, documents the revision, and keeps going, the same
way Core Principle #2 already asks of any session facing a direction change.

The one real machine-dependent split left is **hardware capacity**: GPU training, embedding
generation, and high-throughput batch (parallel linear-probe / KNN, bulk preprocessing) need
hardware the Mac doesn't have, so those specific steps route to whichever box has it.

1. **At session start, run `hostname`** to know which box you're on — mainly relevant for which
   data mounts / GPU capacity are local. Repo-specific bindings (concrete hostnames,
   package-manager rules, sibling-repo paths) live in the repo's `CLAUDE.md` or machine registry
   (e.g. `docs/machines.md`), not here.
2. **On any Claude-Code-capable machine**, do everything a plan calls for: run queries and
   scripts, commit results frequently, and when a finding contradicts a plan assumption — revise
   the approach inline and keep going. Escalate only when a call is genuinely
   architecture-significant or you're actually uncertain (Communication Standards below already
   asks this of every session, machine notwithstanding) — not because of which box you're on.
3. **GPU / high-throughput compute with no Claude Code running there** (a bare GPU box, a
   high-throughput CPU box driven by a script rather than interactively) is the one place a real
   split remains — not an authority question, just a fact that no agent is present to make any
   judgment call there:
   - The deliverable is a **standalone runner script** (env setup — `uv sync` + any env exports
     — plus the run, in one command) that gets copy-pasted onto that box and invoked directly.
   - The script writes its output to the **shared bucket mount** (`su-vista-uscentral1`, mounted
     on both the Mac and the Claude-Code-capable VMs — see `vista-pm/README.md`), not into a
     rendered handoff doc. Whichever Claude-Code session needs the results reads them straight
     off the mount.
   - Give the script real Expected/Stop-style assertions (exit codes, files that must exist &
     be non-empty, metric ranges) — since no agent is there to eyeball an ambiguous result, the
     script itself has to know pass from fail.
4. **Unknown hostnames**: ask the user which capacity class applies rather than hard-refusing or
   assuming. After confirming, offer to register the hostname in the repo's machine registry so
   the next session doesn't re-prompt.

---

## Session Start

**Always** check whether the global skills repo (canonical path: `~/code/research-skills`) is behind `origin/main` before starting work — fetch first so the check sees the true remote state, not a stale local view:

```bash
git -C ~/code/research-skills fetch --quiet 2>/dev/null && \
  git -C ~/code/research-skills log HEAD..origin/main --oneline 2>/dev/null | head
```

If the local clone is behind by **any** commits, tell the user how far behind it is, show the unpulled commit subjects, and ask whether to `git -C ~/code/research-skills pull --ff-only` before starting — don't pull unprompted, but don't skip silently either. Mid-session skill-spec drift (a `/wrapup` or `/review-plan` invocation reading a different version than expected) is harder to reason about than a clean pull at the start, and even a single unpulled commit can change a skill's behavior. Only stay silent when the clone is already up to date (0 commits behind) or the path doesn't exist on this machine.

### Fetch before you survey — your local refs lag the other machine

VISTA work is **cross-machine**: any session on any machine — the Mac, a project VM, whichever
— may have pushed (plans, `next.md` pointers, branches, SHAs) since you last synced, so your
local refs, **`main` included**, are stale by default regardless of which box you're on. Before
you survey git to *find* something another session produced (`git log` / `git ls-files` / a
branch-or-file lookup), before you check out a named branch or SHA, and before you conclude
*"not found"*, run `git fetch origin` **first**. A commit that was never fetched is invisible to
a stale tree, so "can't find the branch / doc / SHA" means *fetch first* — never *it was never
authored, so improvise a plausible substitute*. This is the operating-standard root of the
resume-block `SYNC` line `/wrapup` prints. It's orthogonal to the shared-checkout check below:
that guards against *local* clobbering, this against *stale remote* refs.

### Check for parallel work in the same checkout (before you touch anything)

VISTA repos are **shared single checkouts** — several Claude sessions (usually other agents, often on unrelated tasks) may `cd` into the *same* repo subfolder at once. They then share one working tree, one index, and one HEAD. A branch switch, `git reset`, `git stash`, or commit by any one session is immediately visible to — and can silently clobber — the others. This has already caused real data loss: a commit landed on a parallel session's branch, and the `git reset --hard` used to relocate it discarded three of that session's uncommitted docs. Because git had never staged those edits, no blob existed to restore — the loss was permanent.

So **before beginning work in a repo, take stock of what else is in flight there:**

```bash
git -C <repo> status --short          # uncommitted work you didn't create?
git -C <repo> branch --show-current   # is HEAD on an unexpected feature branch?
git -C <repo> worktree list           # are sibling worktrees already active?
```

Also cross-check `MEMORY.md` / `docs/next.md` for concurrently-active branches. Read any of these as a sign a parallel session is live in this checkout:
- tracked files modified, or untracked files present, that aren't yours;
- HEAD sitting on a feature branch you didn't check out;
- the user mentioning another agent or session working this repo.

**When parallel work is present (or likely), isolate in your own git worktree before editing** — `EnterWorktree` (this project authorizes it for exactly this case) or `git worktree add`. A worktree gives you a private working dir + branch, so your branch switches, commits, stashes, and any destructive tree ops can't reach the other session's tree. When the checkout is clearly yours alone and no other worktrees are active, working in place is fine — just re-verify the branch at commit time (see Git Practices → Before Committing).

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

**For plans with a step that needs GPU / high-throughput hardware**: name the standalone
runner script that step needs as a deliverable in *Files to Modify*, and state its Expected/Stop
criteria in the plan's *Verification* section (see Plan Document Structure below) — the same
place any other step's success criteria live. There's no separate co-design pass for this; it's
one more thing a thorough plan states plainly.

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
  (for new files, name the target directory; flag any new dir — see Code Quality Standards → File & Directory Placement)

## Open Questions
- Any ambiguities to resolve?

## Verification
How will we know this works? State the success criteria *here* so they are reviewed **with the
plan** (via `/review-plan`), not invented later:
- **What runs, and where** — commands / scripts / tests, in order. Most work runs wherever the
  session implementing it happens to be (Mac or a Claude-Code VM — no distinction). Only name a
  specific machine for a step that genuinely needs GPU / high-throughput hardware.
- **Expected** (per step) — how you'll know it worked: exit codes, files that must exist &
  be non-empty, metric ranges, skip-logs.
- **Stop** (per step) — the halt-and-report conditions: precondition / failure / decision-gate.
- **Anticipated forks** — where you can predict a fork (a metric near a threshold, an optional
  path), pre-encode it as a **decision gate** ("if X → A, else B") so it resolves inline instead
  of costing a pause to re-decide. A finding that contradicts a plan assumption isn't a
  hand-off — reconsider inline, revise the approach, document the revision, keep going.
- **If a step needs GPU / high-throughput hardware with no Claude Code running there**: name the
  **standalone runner script** as a deliverable in *Files to Modify* (env setup + the run, one
  command), state where its output lands (the shared bucket mount, not a rendered doc), and give
  it real Expected/Stop assertions of its own — no agent is present there to interpret an
  ambiguous result.

## Landing & cleanup
How this work reaches `main` and how its branch is retired — planned here so the merge and
the branch-deletion are *designed*, not improvised at the end. `/land` executes this: it
should be **following** this section, not inventing the sequence.
- **Branch** — the feature branch this lands on (`feat/…`), or "direct on main" for doc-only /
  minor-fix work (per Git Practices → Feature Branching).
- **Landing gate** — what must hold before `/land` merges: review sign-off (`/read-plan`), any
  GPU/high-throughput step's standalone script actually run and its output checked, PHI-vetted.
  Name any sibling branch that must land first.
- **Merge sequence** — *single-branch plan:* one line ("`/land` at end → main, prune branch +
  worktree"). *Multi-branch / phased plan:* the order branches hit `main` and which rebases
  which (foundational/smaller first; big rename/refactor last, unless it's a prerequisite).
- **Cleanup on land** — `/land` Phase 4 prunes the branch (local + remote) + worktree, marks
  the plan `Status: Completed`, prunes the `next.md` / in-flight entries. Name anything extra
  to retire (scratch dirs, temp tables, parallel-branch notes owed to siblings).
```

### After Completing a Plan

- **Land the branch via `/land`** (branch-based work) — merge to `main` and prune the branch + worktree + `next.md` / in-flight entries, following the plan's *Landing & cleanup* section. Don't merge or delete branches ad hoc — `/land` is the mechanism, and its Phase 4 performs the three updates below; for doc-only / direct-on-main work (no branch to land) do them inline.
- **Update all affected documentation** when a plan is implemented. Fix stale paths, CLI examples, import references, and cross-links in `docs/`.
- **Mark plan docs as completed** by adding `**Status: Completed** (date)` at the top.
- **Update the plans README** (`docs/plans/README.md`) feature table with the new status.

### Standalone scripts for GPU / high-throughput work — read results from the mount, not a doc

For the one class of work that still needs a specific box (GPU training, embedding generation,
high-throughput batch), the deliverable is a **standalone runner script** — self-contained env
setup + the run, in one command — copy-pasted onto that box and invoked directly, since no
Claude Code session runs there interactively. The script writes its output to the shared bucket
mount; any Claude-Code session (Mac or VM) reads the results straight off the mount afterward —
no rendered handoff doc, no separate readback step. For eval results specifically (linear-probe
runs, KNN runs, cross-modality comparisons), read from the auto-generated HTML at
`<results-root>/<version>/<modality>/<dataset>/reports/<model>_<dataset>.html` plus the on-disk
per-task / per-example parquets, and write any narrative yourself. Backlog / `next.md` entries
that *reference* such results with a one-line pointer are still fine.

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

### File & Directory Placement

Where a file *lives* is a design decision, not an afterthought. Decide it deliberately at plan time and make it visible in the plan's `## Files to Modify` — don't default to dropping everything at the repo root.

- Place new files in a coherent, discoverable hierarchy; extend the directory structure that already exists rather than accreting a flat dir of unrelated files.
- Adding a second or third file around a new concern is the signal to give it its own directory. Name that directory in the plan and say why in one line.
- This is a plan-time habit, not a retrospective one. `/wrapup` Step 1 is the safety net that catches a dir that drifted into a flat dump — but getting placement right up front is cheaper than moving files later and fixing every inbound reference.

### YAGNI vs Modularity — Raise Genuinely Uncertain Cases

YAGNI (Principle #5) and modularity / re-use pull in opposite directions: YAGNI says don't build seams for hypothetical futures; modularity says factor seams so the next caller doesn't duplicate. Use best judgement on the obvious cases (one-off script → inline it; third caller landing in the same module → extract). **When the call is genuinely uncertain — reasonable engineers would disagree — raise it as an `AskUserQuestion` rather than committing silently.** Two right moments to ask:

- **During exploration, before writing the plan doc** — if the shape of the abstraction hinges on a design call you can't make alone, ask before drafting, so the plan opens on the chosen branch instead of relitigating it.
- **While writing the plan doc** — surface the fork in `## Open Questions` and / or via `AskUserQuestion` so the user decides before the plan locks in a direction.

Don't paper over the tension with a hedge ("I'll extract it if needed later"); name it and resolve it.

---

## Git Practices

### Before Committing

- **Always check and report the current branch.** Before any commit, verify which branch you're on and tell the user. Never assume you're on the expected branch.
- **Re-verify the branch the *instant* before you commit — not just at task start.** In a shared checkout a parallel session can switch HEAD out from under you between when you began and when you commit. Run `git branch --show-current` immediately before `git commit` / `/commit-review` and confirm it's the branch you mean to land on.
- Confirm with the user if the branch seems unexpected for the task.
- **Prefer non-destructive recovery over `git reset --hard` in a shared checkout.** Operations like `git reset --hard`, a broad `git stash`, or `git checkout -- .` act on the *whole* tree — including another session's uncommitted edits — and edits git never staged have no blob to restore, so the loss is permanent. If you commit to the wrong branch, move the work with `git cherry-pick` / `git reset --soft` / a branch-ref move instead. If you truly must reset, snapshot the *full* working tree first (`git stash -u` of everything, or a filesystem copy) — not just the files you happened to notice in an earlier `status`.

### Feature Branching

- **Major changes should be made in a new feature branch**, not directly on main.
- Documentation updates and minor bug fixes can go directly on main.
- **Simple, additive new files** — a new training config, a new one-off script, a new
  fixture — can also go directly on main. The test is additive-and-isolated: the change
  only adds a file (or a self-contained new entry in a registry-style file, e.g. one new
  dataset-config dict key) that nothing else yet references, so it can't break an existing
  path. Reserve feature branches for changes that touch or depend on existing shared
  code/behavior.
- **`research-skills` itself**: a simple fix already discussed and approved in
  conversation (a skill wording tweak, a doc correction, a small hook adjustment) can skip
  the branch + `/land` ceremony entirely and go straight on `main` — this repo is Phil's
  own tooling, iterated on directly across many sessions. Reserve a branch here for a
  larger skill rewrite or anything that still needs review before landing.

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

- **`/review-plan <plan-path>`** — independent design audit of a plan doc (Codex CLI or fresh Claude subagent), then applies agreed feedback. Its always-on lenses include **handoff-readiness** — does the plan POINT AT / STATE DIRECTLY everything a fresh implementing agent needs (file paths, schema contracts, cross-stage surfaces, success criteria, out-of-scope, and the *Verification* section's Expected/Stop criteria). Run after substantial plan-doc work, before implementation.
- **`/review-implementation <plan-path>`** — implementation audit of uncommitted code against the plan. Run after non-trivial implementation completes, before `/commit-review`.
- **`/review-tests <plan-path>`** — test-coverage audit of uncommitted code against the plan. Run after `/review-implementation` when the change introduces new branches / contracts / edge cases worth regression-protection.
- **`/commit-review`** — commit workflow with appropriateness review (catches accidentally-leaked private content) before commit + push. Use this rather than running `git commit` inline.
- **`/phi-vet`** — hard PHI gate for medical-data repos. `/commit-review` escalates to it automatically for repos that touch BigQuery / OMOP / NeuralFrame / DICOM / EHR / WSI / pathology bucket / vista_bench. Do not silently fall back to inline sweeps.

Skip the review skills for trivial changes (single-file fixes, doc tweaks, formatting). Each skill carries its own guidance on what it checks, when to skip, and how findings get applied.

**Spawned subagents may run code on this machine**, gated by the same `phi-vet` discipline as the main session — this is no longer a blanket prohibition. GPU-bound subagent work (training, embedding generation, high-throughput batch) still doesn't belong here; route it to the VM fleet instead.

---

## Context Management

- **Fresh sessions for fresh tasks.** Start new sessions when switching to unrelated work
- **Match rigor to stakes.** Prototypes allow looser constraints; production changes require thorough planning and review

---

## Verification Approaches

Always define how you'll verify changes work — the same discipline regardless of which machine implements it. For a step that needs GPU / high-throughput hardware, verification means giving the standalone runner script real Expected/Stop assertions of its own, since no agent is present to eyeball an ambiguous result there.

Capture expected behavior as **Expected / Stop** success criteria in the plan's *Verification* section (see Plan Document Structure above), so it is reviewed with the plan.

Remember: Give Claude a way to verify its work. This is the single most important factor in output quality.

---

## Skill Composition

Slash commands (skills) are a design layer above bespoke code, and the way they're authored, invoked, and composed is itself a discipline:

- **Invocation discipline.** Expensive skills — multi-agent workflows, large parallel-search passes, anything that spends significant context budget — must never be auto-invoked from trigger cues alone. When a candidate situation surfaces, summarize the fork in one sentence and offer the skill via `AskUserQuestion` alongside lighter-weight alternatives. The user owns the decision to spend that budget. Cheap skills (e.g. `/read-plan`, `/next`) can be invoked on direct user signal without confirmation.

- **Skills can reference other skills.** A skill's markdown file is not a self-contained island. When two skills overlap on a procedure, point at the canonical one (e.g. "see `/commit-review` for the appropriateness review step") rather than duplicating the body. The same modularity discipline that applies to code applies to prose: it keeps drift down and lets each skill stay focused on what it uniquely contributes.

- **Need-to-know context delivery for subagents.** When the main session delegates to a subagent, do not pour the full context of the main session into the subagent prompt. Point the subagent at the relevant sub-skill or sub-doc and give it just enough to know what to read. The main session does not need to hold the subagent's full procedure in context — the subagent does, on demand, while it is running.

- **Markdown-first when building larger workflows.** When asked to build out a multi-step workflow, default to writing a skill (markdown) FIRST and only then writing code that the skill will invoke. The default bias is toward bespoke single-purpose Python scripts that solve the immediate task and then rot — markdown skills capture intention, goals, resources, success criteria, and the "when to invoke / when to skip" gates that one-off code drops on the floor. Code still gets written; it is downstream of the skill that frames it. Many small coding tasks will not benefit from this layering — apply it when the workflow has multiple steps, multiple invocation modes, or will be re-run across sessions.

- **Surfacing new skill opportunities.** When the user repeatedly performs the same multi-step workflow (commit + push, cross-repo status checks, deploy verification, etc.), surface the option to extract it as a slash command in `~/.claude/commands/`. Keep the suggestion lightweight — only when the pattern has clearly appeared 2+ times — and follow the markdown-first principle above when authoring it.
