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

For repos where the executor / planner split is hostname-dependent (a project VM holds the GPU / high-throughput compute the local Mac lacks), this section overrides **Environment Constraints** above.

1. **At session start, run `hostname`** to determine which mode applies.
2. **The repo declares its machine posture** — typically in `CLAUDE.md` or a dedicated registry like `docs/machines.md`. The registry names known hosts and assigns each one Executor or Planner role, plus PHI posture if relevant.
3. **Executor mode** (a project VM with data, credentials, and a runtime):
   - **Fetch before you survey or act.** The executor is always downstream of the planner's pushes, so your local refs — **`main` included** — lag `origin` by default. Run `git fetch origin` *before* finding a handoff doc / branch / SHA, checking one out, or concluding "not found" — a ref that was never fetched is invisible to a stale tree, so *fetch first*, don't improvise (see *Session Start → Fetch before you survey*). This is where the stale-checkout trap always fires.
   - Run queries, scripts, and exploration as directed by plan docs.
   - Commit results frequently.
   - **The executor may be a *fleet* of capability classes, not one box** — a Claude-Code CPU box (the default / interactive one), a high-throughput CPU box (bulk preprocessing, parallel linear-probe / KNN), and a GPU box (training, embedding generation). Route each step to the class that fits; only the Claude-Code CPU class can run `/vm-handoff` readback itself, so work on the other two runs there but reads back on the Claude-Code CPU box (or the Mac reads results). The class taxonomy + routing live in the canonical spec, `references/verification-and-handoff-design.md` (§4); concrete class→host bindings are repo-local (below).
   - **Classify findings, don't improvise.** A finding that's purely mechanical and leaves the design + success criteria unchanged is an *in-lane correction* (fix it, log it). A finding that contradicts a plan assumption, changes scope, or invalidates the approach is a *plan-level deviation* — STOP, document it, and hand back to the planner; **when uncertain, escalate**. Don't broad-plan or major-rewrite without confirmation. `/vm-handoff` formalizes this routing (its *Deviation workflow*: VM→Mac via a DEVIATION block in the handoff doc, re-plan, supersede with a new doc).
4. **Planner mode** (typically the local Mac):
   - Planning, template authoring, spec writing, doc review.
   - May run light code / query BQ / inspect mounted data directly, gated by the same `phi-vet` discipline as commits; GPU and high-throughput work still routes to the executor fleet.
5. **Unknown hostnames**: ask the user which mode applies rather than hard-refusing or assuming. After confirming, offer to register the hostname in the repo's machine registry so the next session doesn't re-prompt.

Repo-specific bindings (concrete hostnames, package-manager rules, sibling-repo paths, PHI gate choice) live in the repo's `CLAUDE.md` or machine registry — not here. This section defines the *pattern*; each repo declares its *parameters*.

---

## Session Start

**Always** check whether the global skills repo (canonical path: `~/code/research-skills`) is behind `origin/main` before starting work — fetch first so the check sees the true remote state, not a stale local view:

```bash
git -C ~/code/research-skills fetch --quiet 2>/dev/null && \
  git -C ~/code/research-skills log HEAD..origin/main --oneline 2>/dev/null | head
```

If the local clone is behind by **any** commits, tell the user how far behind it is, show the unpulled commit subjects, and ask whether to `git -C ~/code/research-skills pull --ff-only` before starting — don't pull unprompted, but don't skip silently either. Mid-session skill-spec drift (a `/wrapup` or `/review-plan` invocation reading a different version than expected) is harder to reason about than a clean pull at the start, and even a single unpulled commit can change a skill's behavior. Only stay silent when the clone is already up to date (0 commits behind) or the path doesn't exist on this machine.

### Fetch before you survey — your local refs lag the other machine

VISTA work is **cross-machine**: the planner Mac pushes (plans, handoff docs, `next.md` pointers, branches, SHAs) and the executor VM consumes them — so a receiver's local refs, **`main` included**, are stale by default. Before you survey git to *find* something another session produced (`git log` / `git ls-files` / a branch-or-file lookup), before you check out a named branch or SHA, and before you conclude *"not found"*, run `git fetch origin` **first**. A commit that was never fetched is invisible to a stale tree, so "can't find the branch / doc / SHA" means *fetch first* — never *it was never authored, so improvise a plausible substitute*. This bites hardest **VM-side** (the executor is always downstream of the Mac's pushes — see *Machine-Aware Operating Mode → Executor mode*); it's the operating-standard root of the resume-block `SYNC` line that `/vm-handoff` and `/wrapup` print. It's orthogonal to the shared-checkout check below: that guards against *local* clobbering, this against *stale remote* refs.

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

**For VM-handoff-bound plans** (a Mac/VM-split repo where the work executes on the VM): co-design
the plan's *Verification & VM handoff* section (see Plan Document Structure below) using the
**Verification & VM-Handoff Design canonical spec** — `references/verification-and-handoff-design.md`
in the research-skills repo (resolve its root by following this repo's `docs/claude_ops.md`
symlink). It carries the archetype menu (*what to verify*), the expected-vs-unexpected envelope,
and the batching discipline (*how many handoffs*). Tiered by the spec's complexity classifier:
draft inline for a *simple* handoff; spawn a dedicated verification-design subagent for a *complex*
one (keeps the planning context lean). `/review-plan` later audits this section against the same spec.

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

## Verification & VM handoff
How will we know this works? Because this step needs compute the Mac doesn't have (GPU,
high-throughput batch), state the success criteria *here* so they are reviewed **with the
plan** (via `/review-plan`), not invented later at handoff time:
- **What runs on the VM** — commands / scripts / tests, in order.
- **Target machine** (per step / phase) — which **executor class** runs it: *Claude-Code CPU*
  (default — smoke, structural readback, BQ/OMOP queries, moderate eval), *high-throughput CPU*
  (bulk preprocessing, linear-probe / KNN parallelization, core-saturating batch), or *GPU*
  (model training, embedding generation, GPU-only tests), grounded in the executor-fleet taxonomy
  in the canonical spec (§4). When the run machine has **no Claude Code** (high-throughput CPU /
  GPU), name the **readback** machine too — the Claude-Code CPU executor — since the run and the
  Claude-driven readback split across boxes. **A non-Claude-Code run also needs a *standalone
  runner script*** (env setup — `uv sync` + any env exports — plus the run in one command) as a
  deliverable in *Files to Modify*, and plain operator run-instructions (branch to check out,
  preconditions, the one command, where results land): that box runs a script it can invoke, not a
  Claude-driven vm-status doc (canonical spec §4). Concrete class→host binding stays repo-local.
- **Expected** (per step) — how the executor knows it worked: exit codes, files that must
  exist & be non-empty, metric ranges, skip-logs.
- **Stop** (per step) — the halt-and-report conditions: precondition / failure / decision-gate.
- **Anticipated forks** — where you can predict the executor will hit a fork (a metric near a threshold, an optional path), pre-encode it as a **decision gate** ("if X → A, else B") so the executor resolves it inline instead of round-tripping back for a re-plan. Unanticipated findings that contradict the plan are *deviations* — `/vm-handoff`'s Deviation workflow routes those back here for revision.
- **Handoff phasing** — for a *complex* handoff (cross-repo SHA ripple, more than one phase, decision gates, bank/un-bank of prior results, destructive writes, multi-target bundling, or more than one executor class — which forces a run-vs-readback split), decompose the VM work into phases so the number of expensive round-trips is *designed*, not accidental. Per phase: `Phase N — <name>` · purpose · machine (executor class; readback machine if it differs) · banked-from-prior (steps / SHA not re-run) · gates (class-2 forks resolved inline) · destructive? · stop/deviation routing · next-doc trigger. A *simple* single-phase handoff states its one phase inline. The batching rules (order cheap→expensive→destructive, bundle-by-SHA, bank-and-un-bank, decision-gates-over-round-trips) and the archetype menu / expected-vs-unexpected envelope live in the **Verification & VM-Handoff Design canonical spec** — `references/verification-and-handoff-design.md` in the research-skills repo (resolve its root by following this repo's `docs/claude_ops.md` symlink — or, if you are already inside research-skills, it is the repo root). `/vm-handoff` renders each phase into a runnable vm-status doc.

`/vm-handoff` later renders this section into a runnable `docs/vm-status/<date>-<sha>.md`
handoff doc and tracks the VM's results back into it. It should be **deriving** the
criteria from this section, not authoring fresh ones — if this section is thin, the plan
isn't handoff-ready (see `/review-plan`'s handoff-readiness lens).

## Landing & cleanup
How this work reaches `main` and how its branch is retired — planned here so the merge and
the branch-deletion are *designed*, not improvised at the end. `/land` executes this: it
should be **following** this section, not inventing the sequence.
- **Branch** — the feature branch this lands on (`feat/…`), or "direct on main" for doc-only /
  minor-fix work (per Git Practices → Feature Branching).
- **Landing gate** — what must hold before `/land` merges: review sign-off (`/read-plan`),
  VM gate green, PHI-vetted. Name any sibling branch that must land first.
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

### VM-status docs are for smoke tests only — not for eval results

`docs/vm-status/<date>-<sha>.md` reports are for **smoke-test / verification handoffs** between sessions: aggregator runs needing structural readback, full test sweeps with expected reds to characterize, end-to-end pipeline validation. Use **`/vm-handoff`** to author and close these — it auto-detects planner vs executor by `hostname` (per Machine-Aware Operating Mode above), **renders** the runnable doc from the plan's *Verification & VM handoff* section (the Expected/Stop criteria already reviewed with the plan via `/review-plan` — it derives them, it doesn't invent them), and on the VM appends the run results back into the *same* doc so the round-trip is self-contained. Once a workstream has moved past smoke tests into producing eval results (linear-probe runs, KNN runs, cross-modality comparisons), don't propose vm-status docs — the user reads results directly from the auto-generated HTML at `<results-root>/<version>/<modality>/<dataset>/reports/<model>_<dataset>.html` plus the on-disk per-task / per-example parquets, and writes any narrative themselves. Backlog / next.md entries that *reference* such results with a one-line pointer are still fine.

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

- **`/review-plan <plan-path>`** — independent design audit of a plan doc (Codex CLI or fresh Claude subagent), then applies agreed feedback. Its always-on lenses include **handoff-readiness** — does the plan POINT AT / STATE DIRECTLY everything a fresh implementing agent needs (file paths, schema contracts, cross-stage surfaces, success criteria, out-of-scope, and for VM work the *Verification & VM handoff* Expected/Stop criteria). Run after substantial plan-doc work, before implementation.
- **`/review-implementation <plan-path>`** — implementation audit of uncommitted code against the plan. Run after non-trivial implementation completes, before `/commit-review`. Only when the repo uses a planner/executor (Mac/VM) split **and** the plan requires a VM handoff does it route to `/vm-handoff` first (so the handoff doc lands in the same commit-review); otherwise it goes straight to `/commit-review`.
- **`/review-tests <plan-path>`** — test-coverage audit of uncommitted code against the plan. Run after `/review-implementation` when the change introduces new branches / contracts / edge cases worth regression-protection. Same conditional `/vm-handoff`-before-`/commit-review` routing as `/review-implementation`.
- **`/commit-review`** — commit workflow with appropriateness review (catches accidentally-leaked private content) before commit + push. Use this rather than running `git commit` inline.
- **`/phi-vet`** — hard PHI gate for medical-data repos. `/commit-review` escalates to it automatically for repos that touch BigQuery / OMOP / NeuralFrame / DICOM / EHR / WSI / pathology bucket / vista_bench. Do not silently fall back to inline sweeps.
- **`/vm-handoff`** — planner-Mac → executor-VM round-trip. On the Mac, renders the plan's *Verification & VM handoff* criteria into a runnable `docs/vm-status/<date>-<sha>.md`, gates the criteria for your sign-off (tiered by complexity), then offers `/commit-review` to land. Runs **before** the commit-review phase, not after: authored against the still-uncommitted implementation, so its `/commit-review` bundles the handoff doc **and** the code it documents into one PHI-vet + push instead of a second cycle. On the VM, appends the run results into the same doc and offers `/phi-vet` → `/commit-review`. Auto-detects mode by `hostname`.

Skip the review skills for trivial changes (single-file fixes, doc tweaks, formatting). Each skill carries its own guidance on what it checks, when to skip, and how findings get applied.

**Spawned subagents may run code on this machine**, gated by the same `phi-vet` discipline as the main session — this is no longer a blanket prohibition. GPU-bound subagent work (training, embedding generation, high-throughput batch) still doesn't belong here; route it to the VM fleet instead.

---

## Context Management

- **Fresh sessions for fresh tasks.** Start new sessions when switching to unrelated work
- **Match rigor to stakes.** Prototypes allow looser constraints; production changes require thorough planning and review

---

## Verification Approaches

Always define how you'll verify changes work. For steps that need compute this machine doesn't have (GPU, high-throughput batch), verification means describing expected behavior for the user to confirm on the VM.

Capture that expected behavior as **Expected / Stop** success criteria in the plan's *Verification & VM handoff* section (see Plan Document Structure above), so it is reviewed with the plan. `/vm-handoff` operationalizes those criteria into a runnable `docs/vm-status/<date>-<sha>.md` handoff doc and records the VM's results back into the same doc — see that skill for the planner→executor round-trip.

Remember: Give Claude a way to verify its work. This is the single most important factor in output quality.

---

## Skill Composition

Slash commands (skills) are a design layer above bespoke code, and the way they're authored, invoked, and composed is itself a discipline:

- **Invocation discipline.** Expensive skills — multi-agent workflows, large parallel-search passes, anything that spends significant context budget — must never be auto-invoked from trigger cues alone. When a candidate situation surfaces, summarize the fork in one sentence and offer the skill via `AskUserQuestion` alongside lighter-weight alternatives. The user owns the decision to spend that budget. Cheap skills (e.g. `/read-plan`, `/next`) can be invoked on direct user signal without confirmation.

- **Skills can reference other skills.** A skill's markdown file is not a self-contained island. When two skills overlap on a procedure, point at the canonical one (e.g. "see `/commit-review` for the appropriateness review step") rather than duplicating the body. The same modularity discipline that applies to code applies to prose: it keeps drift down and lets each skill stay focused on what it uniquely contributes.

- **Need-to-know context delivery for subagents.** When the main session delegates to a subagent, do not pour the full context of the main session into the subagent prompt. Point the subagent at the relevant sub-skill or sub-doc and give it just enough to know what to read. The main session does not need to hold the subagent's full procedure in context — the subagent does, on demand, while it is running.

- **Markdown-first when building larger workflows.** When asked to build out a multi-step workflow, default to writing a skill (markdown) FIRST and only then writing code that the skill will invoke. The default bias is toward bespoke single-purpose Python scripts that solve the immediate task and then rot — markdown skills capture intention, goals, resources, success criteria, and the "when to invoke / when to skip" gates that one-off code drops on the floor. Code still gets written; it is downstream of the skill that frames it. Many small coding tasks will not benefit from this layering — apply it when the workflow has multiple steps, multiple invocation modes, or will be re-run across sessions.

- **Surfacing new skill opportunities.** When the user repeatedly performs the same multi-step workflow (commit + push, cross-repo status checks, deploy verification, etc.), surface the option to extract it as a slash command in `~/.claude/commands/`. Keep the suggestion lightweight — only when the pattern has clearly appeared 2+ times — and follow the markdown-first principle above when authoring it.
