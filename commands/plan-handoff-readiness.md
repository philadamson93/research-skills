---
name: plan-handoff-readiness
description: A plan doc is a fresh-agent handoff. The current session has accumulated context the plan needs to either POINT AT (name the docs / files / memories the fresh agent should read first) or STATE DIRECTLY (when the context is load-bearing and brittle to indirection). After writing or substantially editing an implementation plan doc — anything in docs/plans/, plans/, design/, rfcs/, or files named PLAN.md / DESIGN.md / RFC.md / IMPLEMENTATION.md / PROPOSAL.md — run this check to surface gaps where the fresh agent would arrive context-starved. Pauses for user sign-off if gaps found. TRIGGER right after a Write or Edit tool call that produces a multi-step implementation plan, BEFORE invoking commit-review or moving on to the next conversation thread. Extensible per-project — see the bottom section.
---

# plan-handoff-readiness

## The principle

A plan doc is written at the end of a conversation that has accumulated a lot of context. The fresh agent in some future session who picks up the plan to implement it has none of that context. They have:

- The plan doc itself
- The current state of the codebase
- Their own toolkit (`grep`, `read`, etc.)
- Whatever the plan tells them to read first

If the plan implicitly assumes the fresh agent already knows something the current conversation worked out, the implementation will start by re-deriving it (slower, error-prone) or skip it (silently wrong). Both outcomes are bad.

The job of `plan-handoff-readiness` is to surface these implicit assumptions and decide, per gap, between two fixes:

1. **POINT AT** the source of the context — "read `<file>` first," "see memory `<name>`," "see `docs/journal/<entry>` for decision rationale," "see `<sister-feature-plan>` for the related design."
2. **STATE DIRECTLY** in the plan — when the context is load-bearing for implementation AND brittle to indirection (the source may move, get archived, or rot; the line numbers may shift; the memory may decay).

The default is **POINT AT.** Stating directly is reserved for cases where indirection genuinely fails the fresh agent.

## Implementation-forward, not retrospective

A finalized plan is **implementation-forward**. It tells the implementer what to build. Decisions made along the way (why option (b) was picked over (c), what alternatives were considered, what was deferred) are **retrospective** — they belong in commit messages, conversation logs, PR descriptions, or a project-level decisions tracker, **not in the plan doc that ships to the implementer.**

When auditing a plan, focus on what the IMPLEMENTER needs to act:

- Does the plan name file paths, line numbers, schemas, success criteria, cross-stage propagation, out-of-scope items?
- Does it describe what to build, not why each design choice was preferred?

Do NOT audit for:

- **Decision rationale** ("why did they pick (b) over (c)?") — if the spec says "the column is modality-conditional," the implementer has what they need to act. The reasoning belongs in the commit / conversation, not the plan.
- **Decisions log presence** — a plan doc is not a decisions tracker. If the project keeps a decisions log, point at it; don't expect the plan to embed one.
- **"Open Questions" section completeness** — if a plan still has open questions, it's not finalized; the right action is "go finalize the questions," not "audit handoff readiness."

**Surface as a gap (REMOVE-IT signal): an "Open Questions" or "Decisions" section retained AFTER all questions are resolved.** The decisions are baked into the spec; the retained section is duplicative scaffolding from the design phase that ages poorly (Q-citations in the spec become dangling references when someone later renumbers or trims the section). Once finalized, fold:

- **Resolved decisions** → into the implementation spec itself (the rule is what the implementer needs; not the rationale).
- **Backlog / out-of-scope items** → a brief "Out of scope" section so the implementer knows what to skip.
- **Items still gated on data** → into the relevant Slice's verification section as decision-criteria sub-bullets ("if VM data shows X, file follow-up Y") — these are forward-looking work, not open questions.
- **Strip Q-citations from the spec** ("per Q14 resolution", "(Q21)") — they only made sense while the Open Questions section existed; once it's gone, they're noise.

## When to run

- **Right after writing or substantially editing a plan doc.** Before invoking commit-review. Before moving on to the next thread of the conversation.
- **At the end of a planning conversation that produced a plan doc**, even if no commit is imminent — flag gaps so the user can decide whether to enrich now or defer.
- **When updating an existing plan doc with new sections** — verify the new sections meet the same standard.

## What counts as a plan doc

- Files in `docs/plans/`, `plans/`, `design/`, `rfcs/`, `proposals/`, or similar directories.
- Files named `PLAN.md`, `DESIGN.md`, `RFC.md`, `IMPLEMENTATION.md`, `PROPOSAL.md` at any directory depth.
- Markdown files whose primary content is a multi-step implementation plan (sections like "Files to edit," "Smoke test plan," "Open questions") even if the path doesn't match.

## Skip conditions

- The plan doc is itself a meta-doc — a "decisions log," "open questions," or "session journal" that intentionally does not pin implementation details.
- The user has explicitly said to skip ("just commit the rough draft," "skip the readiness check").
- The doc edit is a typo or pure prose-cleanup with no new content.
- The plan is an archived / superseded historical doc capturing frozen state.

## What a fresh agent typically needs

These are the categories of context the current session usually has accumulated, that the fresh agent will not have. For each, ask: does the plan POINT AT or STATE the context, or is it implicit?

### 1. Where the change touches the codebase

The fresh agent needs to know:

- **Specific files and line ranges** the change touches, not "the handler module" or "the orchestrator."
- **Where new files live** — directory convention plus closest sister file to model from.
- **Existing related code** to mirror, extend, or coordinate with — so the implementer doesn't reinvent a pattern that already exists nearby.

For projects whose ship surface is partly Markdown (slash-command prompts, dispatch templates, project-owned skills, prompts-as-config), the same principle applies — name the prompt or skill files, not just "the orchestrator."

### 2. Schema and interface contracts

If the change touches a contract (database schema, JSON envelope, API endpoint signature, RPC payload, prompt slot list, config file format), the fresh agent needs:

- **The schema-of-record file** — where the contract is defined.
- **The specific fields, enums, types** being added or changed.
- **Versioning impact** — is the change additive (no version bump), backward-compatible (minor bump), or breaking (major bump or migration)?
- **Cross-stage propagation** — when a contract changes, fields usually need to be added in multiple places (validator, serializer, dispatch payload, consumer slot list, downstream renderer). Name them.

### 3. Why the plan exists in the form it does

Many plans are written after a substantive design discussion. The decisions encode trade-offs whose rationale is not obvious from the code or the plan's prescription. The fresh agent needs:

- **Decisions vs. open questions** — distinguished cleanly. Don't make the implementer guess what's settled.
- **Rationale** for each non-obvious decision — at minimum a one-line "why this and not the alternative." Without rationale, the implementer can't reason about edge cases that fall outside the decided scope.
- **A pointer to the journal entry / decision log / RFC** that captures the discussion in fuller detail, if one exists. The plan need not duplicate it; the pointer is enough.

### 4. How to know the implementation worked

The fresh agent needs:

- **A canonical run / fixture / test** to validate against — not "make sure it works."
- **What the expected output looks like** — agreement with a baseline, a specific status code, a regression-free diff.
- **What should NOT change** — behaviors that must remain stable. As load-bearing as the new behavior.

### 5. What the plan deliberately doesn't cover

The fresh agent needs:

- **An explicit out-of-scope statement.** Without it, every adjacent concern reads as "should I do this too?" and scope creep is the default.
- The OOS section gives the implementer permission to defer items that look adjacent but aren't part of v1.

### 6. Coordination with other in-flight work

If the project has parallel work that touches the same surfaces, the fresh agent needs:

- **Which other branches / plans / tickets share surface area** with this one.
- **Sequencing recommendations** — "land A first, rebase B onto post-A `main`," or "A and B can land independently; final merge resolves the union."
- **Memory of any active design conversation** that hasn't yet produced a separate plan doc — at minimum a pointer to the relevant journal entry.

## Surface gaps and pause

For each gap found, list:

- **File and section** the gap is in
- **What's missing** — the specific question the doc fails to answer for a fresh agent
- **POINT AT or STATE DIRECTLY** — proposed fix shape, with a one-line concrete suggestion (the doc text or the pointer to add)

Pause for user sign-off. The user picks: (a) add the proposed fixes now, (b) commit as-is and queue the fixes, (c) the gap is intentional (e.g., a deliberately-deferred open question).

## Common gap patterns

These are universal across projects; project-specific patterns extend (see bottom).

### "Add a new X" (no file pointer)

"Add a new authentication middleware" without naming where the file lives or what existing middleware to model from. **Fix:** POINT AT the file path and the closest sister file.

### "New schema field Y" (no schema file)

"The schema needs a new `request_id` field" without saying where the schema is defined or whether the change is additive vs. breaking. **Fix:** POINT AT the schema-of-record file. STATE DIRECTLY the field type, any enum values, and the versioning decision (additive / minor / major).

### "New endpoint /Z" (no convention)

"Add `/users/preferences` endpoint" without saying where endpoints are defined, the router-registration step, or which existing endpoint is the closest template. **Fix:** POINT AT the routing file, handler file, and closest sister.

### "Pre-step does X" (no pre-step exists)

Plan refers to "the input-validation pre-step" or "the orchestrator's parsing module" — components that don't exist as separate code units. The work is done inline in a larger function or by an agent driven by a prompt. **Fix:** STATE DIRECTLY the actual code structure — name the function or prompt where the work currently lives.

### "When the feature is done" (no success criterion)

Plan describes the feature without saying how the implementer knows it works. **Fix:** STATE DIRECTLY a canonical run, expected output, and regression-check baseline. POINT AT the test fixture if one exists.

For VISTA plans whose work executes on the VM (the executor is a kind of fresh agent too), the success criterion takes a specific shape: a **Verification & VM handoff** section stating *what runs on the VM* plus per-step **Expected** (how the executor knows it worked) and **Stop** (halt-and-report conditions) — per `claude_ops.md`'s Plan Document Structure. A plan missing this section isn't VM-handoff-ready: `/vm-handoff` would have to invent the criteria instead of deriving them. **Fix:** STATE DIRECTLY the Expected/Stop criteria in the plan so they're reviewed with it (via `/review-plan`), not improvised at handoff time.

### Cross-stage plumbing missed

Plan correctly identifies that one stage changes (e.g., "the request handler now accepts a new field") but omits upstream / downstream stages that need lockstep updates:

- **Validators** — invariants in input-validation may reject the new shape without an explicit rule.
- **Renderers / serializers** — UI / response-shape logic may mis-render new shapes.
- **Dispatch payloads / RPC envelopes** — fields the next stage needs must be added to the carrier shape.
- **Subagent or sub-process prompt slots** — `{{slot}}` placeholders or env-var contracts must be added before the consumer can read the new field.

Most common gap pattern in real reviews. When a plan touches the central pipeline (request handler, orchestrator, dispatcher, build runner), check all four cross-stage surfaces.

### "Decided yesterday" (rationale missing)

Plan states a non-obvious decision ("we use approach X, not Y") without saying why. The fresh agent can't reason about edge cases. **Fix:** STATE DIRECTLY a one-line "why this and not Y" — even a brief one. POINT AT the journal entry / RFC / discussion thread for the longer reasoning if one exists.

## Non-goals

- **Don't rewrite the plan doc.** Propose specific additions and let the user approve. The user wrote the plan; this skill is a checker, not an editor.
- **Don't apply this to status / index / brief docs** (`NEXT.md`, `README.md`, `TODO.md`) where the convention is brevity-with-pointers, not implementability.
- **Don't apply to milestone / archived / read-only docs** capturing frozen historical state.
- **Don't gate on stylistic concerns** (tone, prose density, ordering) unless they directly affect implementability. Doc-style is a separate concern.
- **Don't expand scope.** If a plan is intentionally narrow, the readiness check verifies the narrow scope is implementable, not that the scope is right.
- **Default to POINT AT, not STATE DIRECTLY.** Plan docs that copy-paste context from other docs go stale fast. Pointing is more robust than restating, except when the source is fragile.

## Project-specific extensions

This skill is the universal base. Individual projects accumulate their own gap patterns — file-path conventions, common cross-stage surfaces, recurring "Pre-step does X" misframings against that project's actual code structure.

If the current project has its own `.claude/skills/plan-handoff-readiness.md` (or earlier names: `.claude/skills/plan-check.md`, `.claude/skills/plan-doc-readiness-check.md`), read it as an extension of this global skill — not a replacement. The project skill should:

- Reference this global skill rather than duplicate the universal checks above.
- Add project-specific names: actual file paths, schema files, the project's particular orchestrator-or-pipeline shape.
- List project-specific common gap patterns observed in past reviews of that project's plans.

If you find yourself running this skill in a project that doesn't have a `.claude/skills/plan-handoff-readiness.md`, the global skill alone is sufficient. The extension is a refinement, not a prerequisite.
