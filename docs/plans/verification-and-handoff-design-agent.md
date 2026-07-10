Reference: docs/claude_ops.md

# Verification & VM-Handoff Design agent

## Goal

VM handoffs are the **only** way VISTA work gets verified against real data, and each
round-trip is expensive (a `/commit-review` + `/phi-vet` on both the Mac and the VM leg,
plus the wall-clock time waiting on the VM). Two things are therefore worth a dedicated design
investment, and neither is well-served today:

1. **What to verify** — not just "tests pass" but data-sanity checks, smoke tests,
   migration/prior-run consistency diffs, cross-task invariants, domain-sanity checks, the
   expected-vs-unexpected envelope, and the silent-failure traps that need an explicit STOP.
2. **How many handoffs** — the batching/sequencing decision that minimizes round-trips:
   what to bundle into one handoff, what to bank as a GREEN baseline and *not* re-run, what
   to pre-encode as a decision gate the executor resolves inline, and where a genuine
   round-trip is unavoidable.

Today this knowledge is (a) partially present as a review *lens* in `review-plan.md` (a
"VM verification" always-on lens + a 4-pillar behavioral-test lens), and (b) deeply encoded
per-repo in `.claude/references/plan-review-checklist.md` (vista_bench / vista-eval /
vista-ct). But nothing is **generative** (it critiques, it doesn't propose), and **nothing
addresses the handoff-count/batching decision at all**.

This plan adds a **Verification & VM-Handoff Design capability** with two touchpoints —
generative during plan authoring, audit during `/review-plan` — backed by one canonical spec
both consume.

## Background — what the corpus shows

Mined from ~90 real `docs/vm-status/*.md` handoff docs across vista_bench, vista-eval,
vista-ct, and rad-eval. Key findings that shape the design:

- **The archetype menu is real and recurring** — cheap-gate-first ordering; focused →
  full-suite regression with *delta-anchored* pass counts; migration EXCEPT-DISTINCT diffs
  against a scratch table (never overwrite published); before/after refactor parity at a
  numeric tolerance (exact for equivalence, band for metrics); informative-coverage
  (exclude padded `Unknown`); per-person uniqueness; label-domain ⊆ {0,1,-1}; cross-task
  logical invariants (death monotonic, PFS⟹alive, superset delta-attribution); relative-
  over-absolute domain sanity (Stage IV mortality > Stage I, never pin percentages);
  metric-sanity floor (0.5-pin = path bug); a **guard that must go RED** (negative/seed
  test proving itself by firing); named **silent-fallback / silent-corruption traps** as
  explicit STOPs; PHI-clean readback; reject substring asserts on rendered output.

- **The expected-vs-unexpected envelope is load-bearing and under-specified.** Poster case:
  clinical-1a STOPped class-3 on a `118-changed / 292-flips` diff that was later *accepted*
  as expected re-anchoring — a pre-stated envelope would have made it a class-2 inline
  resolution and saved the round-trip. Other real costs: a mis-scoped STOP threshold
  (aggregate-drop vs the plan's actual negative-duration-drop criterion) manufactured a
  spurious block; a person-count-vs-study-series unit mix-up in an Expected line manufactured
  a false STOP.

- **The batching discipline is the genuinely new contribution.** From the corpus:
  order steps cheap→expensive→destructive with a STOP before each irreversible action;
  bundle all checks sharing one checkout/SHA into one handoff; pre-encode every foreseeable
  fork as a class-2 decision gate; **bank passed steps by readback SHA and re-hand off only
  the unresolved set — but un-bank any step whose inputs moved** (rad-eval re-ran a banked
  pytest after `origin/main` was folded into the tree); new scope → new doc, same question +
  new evidence → append a readback; decision-first sequencing (author the implementation
  handoff only after a blocking fork resolves; a cheap pre-implementation gate can refute a
  wrong path before it's built); multi-target bundling caution (one target can deviate
  mid-doc while the other ships); firewall OUT results-producing runs (read from HTML) and
  not-yet-built phases; **under-splitting is also a failure** (a "just a validator" change
  pushed with no handoff doc had to retroactively author one).

- **Per-repo checklists already hold the concrete recipes** — repo-specific VM-verification
  recipes and diff/sample guidance. (Formats differ: vista-eval's checklist uses explicit
  `Recipe / Sample-size / Diff-against` headings; vista_bench groups recipes by change-type —
  so the spec must not assume a uniform checklist shape.) The new capability must **defer to
  them, not duplicate** — its job is archetype *selection*, the *envelope*, and the *batching*.

## Approach

One capability, one canonical spec, two touchpoints — complexity-tiered so the orchestrator
decides how much machinery to spin up.

- **Canonical spec** (new `references/verification-and-handoff-design.md`) holds the
  archetype menu, the expected-vs-unexpected envelope, and the handoff-batching discipline,
  written mode-neutrally. Both touchpoints read it; neither restates it (per `claude_ops.md`
  Skill Composition "point at the canonical one").

- **Touchpoint 1 — generative, during plan authoring.** For a VM-handoff-bound plan, the
  planning agent co-designs the plan's *Verification & VM handoff* section — including the
  new **Handoff phasing** sub-section (schema below) — reading the canonical spec + the
  repo's `plan-review-checklist.md`. Tiered per the classifier: a *simple* handoff is drafted
  inline; a *complex* one spawns a dedicated verification-design subagent so the main planning
  context stays lean.

- **Touchpoint 2 — audit, during `/review-plan`.** For a VM-handoff-bound plan, a dedicated
  verification-design reviewer pass runs as an automatic *component* of the review (the outer
  `/review-plan` is still offered, not auto-invoked — but once you're reviewing a VM-bound
  plan, the verification pass is part of what that review *is*; since `/review-plan` is run on
  essentially every non-trivial plan, auto-running the verification component is a *feature*,
  not a loss of control). It uses the reviewer the user already chose for the design review (no
  re-ask), independently audits the Verification & VM handoff section against the canonical spec
  + per-repo checklist, and writes a "Verification & Handoff Design" feedback section applied
  like any other `/review-plan` finding. Tiered per
  the classifier: *simple* → a mandatory distinct section within that reviewer's single pass;
  *complex* → its own focused reviewer invocation + feedback file, authorized by the same
  initial choice.

- **Lens migration — reconcile with existing `/review-plan` content (load-bearing).**
  `review-plan.md` today carries the archetype/behavioral content inline as two always-on
  lenses: *VM verification* (`review-plan.md:79`) and the 4-pillar *Behavioral test design*
  (`review-plan.md:83`). Those **move into the canonical spec**; `review-plan.md` keeps only a
  pointer + the distinct-pass mechanics (when it fires, the feedback-section shape,
  classify/apply). Without this the plan would stand up a second review surface owning the
  same archetypes with subtly different wording — the exact "point at canonical, don't
  duplicate" failure it invokes. **Acceptance rule (checkable):** the command docs
  (`review-plan.md`, `vm-handoff.md`, `plan-handoff-readiness.md`) may contain only
  invocation / ownership / mechanics text plus a link — the archetype menu, the envelope, and
  the batching discipline live *only* in the canonical spec; repo-specific recipes live *only*
  in the per-repo checklist.

- **Complexity classifier (both touchpoints share it).** *Simple* = one handoff, one repo, no
  decision gates, no banked prior-SHA, no destructive write. *Complex* = **any** of {cross-repo
  SHA ripple, >1 handoff phase, class-2 decision gates, bank/un-bank logic,
  destructive/irreversible writes, multi-target bundling}. Simple → inline (generative) / a
  distinct section in the single chosen reviewer's pass (audit). Complex → spawn the
  verification-design subagent (generative) / a separate focused reviewer invocation (audit).

- **`vm-handoff` stays operational.** It renders the *next* concrete handoff doc from the
  (now richer) phasing strategy and records the readback — one execution at a time. When
  results / implementation specifics / a class-3 deviation change the picture, the existing
  deviation → re-plan → supersede loop revises the plan's strategy and re-runs the audit
  pass. The strategy lives in the *plan* precisely so it can be revised cleanly; the handoff
  doc is one dated execution of it.

## Files to Modify

- **NEW `references/verification-and-handoff-design.md`** — the canonical spec. New
  top-level `references/` dir (parallel to `commands/` and `hooks/`; research-skills has none
  today). This is the single home for all mined content; everything else points at it.
- **NEW `docs/plans/verification-and-handoff-design-agent.md`** — this plan doc. New
  `docs/plans/` dir (research-skills has no plans convention yet; `relay/mock-plan.md` is a
  test fixture, not a real plan). Follows `claude_ops.md`'s docs/plans/ standard.
- **`claude_ops.md`** (canonical; symlinked as `docs/claude_ops.md` into every repo — edits
  ripple everywhere) —
  - *Plan Document Structure → Verification & VM handoff*: the current template is a flat
    bullet list (`What runs on the VM` / `Expected` / `Stop` / `Anticipated forks`). Add a
    **fifth bullet, `Handoff phasing`**, after `Anticipated forks`, holding the batching
    strategy as a compact **per-phase schema** (not free prose) so `/plan-handoff-readiness`
    can check its fields: `Phase N — <name>` · purpose · banked-from-prior (which steps / SHA)
    · gates (class-2 forks the executor resolves inline) · destructive? · stop / deviation
    routing · next-doc trigger. Required only for *complex*-tier plans (per the classifier); a
    *simple* single-phase handoff states its one phase inline. Link the canonical spec for the
    batching *rules* rather than restating them.
  - *Planning Workflow*: add that VM-handoff-bound plans co-design that section via the
    generative verification-design step (tiered per the classifier), pointing at the canonical
    spec.
- **`commands/review-plan.md`** — (1) **migrate** the two existing always-on lenses — *VM
  verification* (`:79`) and the 4-pillar *Behavioral test design* (`:83`) — OUT of the prompt
  and INTO the canonical spec, leaving a pointer; (2) add the dedicated verification-design
  reviewer pass (audit mode, auto-run for VM-handoff-bound plans, tiered per the classifier),
  referencing the canonical spec + per-repo checklist; add its feedback-section shape and
  classify/apply handling. Per the acceptance rule, what remains here is mechanics + a link,
  not the menu.
- **`commands/vm-handoff.md`** — one-line cross-ref only: it renders the *next* doc from the
  **Handoff phasing** strategy (now with a first-class home) which the audit pass already
  vetted. Ownership boundary is unchanged — `/vm-handoff` keeps rendering, the tiered sign-off
  gate, Expected/Stop enforcement, the class-1/2/3 deviation taxonomy, and supersede mechanics;
  the canonical spec owns only *plan-time* strategy selection and points at `/vm-handoff` for
  those mechanics rather than restating them.
- **`commands/plan-handoff-readiness.md`** — one-line cross-ref: for complex-tier VM-bound
  plans, check the **Handoff phasing** bullet is present *and its schema fields are filled*,
  not just Expected/Stop.

## Canonical-spec content outline (`references/verification-and-handoff-design.md`)

1. **What to verify — the archetype menu** (select the relevant ones; propose the missing).
2. **The expected-vs-unexpected envelope** (per consequential step: correct-run signature +
   surprising-but-benign vs real-bug; pre-declared diff magnitudes; carried-forward known
   reds; threshold-matches-actual-criterion; units/identifiers correct).
3. **How many handoffs — the batching discipline** (cheap→expensive→destructive ordering;
   bundle-by-SHA; decision-gates over round-trips; bank-and-re-hand-off with the un-bank-on-
   moved-inputs rule; new-scope-new-doc vs same-question-append; decision-first sequencing;
   pre-implementation gates; multi-target caution; firewall-out; under-splitting is a
   failure too) — **plus the per-phase `Handoff phasing` schema** that `claude_ops.md`'s fifth
   bullet renders (fields defined there).
4. **Defer to the per-repo `plan-review-checklist.md`** for concrete recipes; the spec owns
   selection + envelope + batching, not repo-specific recipes.

## Open Questions

Each carries a recommendation resolved from the Codex review; confirm on your `/read-plan` pass.

- **OQ1 — audit-pass reviewer (RESOLVED, confirm).** Reuse the reviewer the user already chose
  for the design review — no re-ask. Simple-tier: a mandatory distinct section within that
  reviewer's single pass. Complex-tier: a separate focused invocation authorized by that same
  initial choice (so auto-run-within-review-plan holds without a second prompt). *Residual
  (RESOLVED 2026-07-08):* the complex-tier second run is **silent** — no notice.
- **OQ2 — generative step: subagent vs inline (RESOLVED via the classifier).** Inline guidance
  for *simple*; spawn the verification-design subagent for *complex*, where the classifier in
  Approach draws the line (cross-repo SHA / >1 phase / class-2 gates / bank-unbank /
  destructive writes / multi-target). Confirm the thresholds match your intent.
- **OQ3 — is `Handoff phasing` required for every VM-bound plan? (RESOLVED 2026-07-08.)**
  *Complex-tier only* — a simple single-phase handoff states its one phase inline rather than
  filling the schema.
- **OQ4 — thin invocable `/design-verification` skill.** Defer, with a concrete revisit
  trigger: add it after either (a) one dogfood where you ask for the generative pass by name,
  or (b) two plans that need complex phasing. Until then it stays claude_ops.md planning
  guidance.

(The former OQ5 — rad-eval has no per-repo checklist — moved to `backlog.md` as a followup-plan
candidate so this plan doesn't carry a stale cross-repo reference.)

## Verification

This is a change to research-skills prose/standards, not runtime code — no VM handoff.
Verification is structural + dogfood:

- **Structural coherence** — the canonical spec is referenced (not duplicated) by
  `claude_ops.md`, `review-plan.md`, `vm-handoff.md`, `plan-handoff-readiness.md`; the
  **Handoff phasing** label is identical everywhere it's cross-referenced.
- **Acceptance-rule readback (catches the lens-duplication failure)** — two-sided check after
  the migration: (a) the migrated *phrases* (`'Behavioral test design'`, `'ABD(OMEN)?'`,
  `'four pillars'`) are **gone** from `commands/review-plan.md`'s body; (b) the migrated
  *concepts* now live in `references/verification-and-handoff-design.md` — `rg` for
  `'substring assert'`, `'relative over absolute'`, `'guard that must go RED'`, `'Stage IV'`
  and confirm they hit the spec. (The vista-ct-specific `'ABD(OMEN)?'` example was intentionally
  dropped, not carried into the generic spec — so grep it only as an *absence* check on
  review-plan.md, not a presence check on the spec.)
- **Symlink ripple** — confirm the `claude_ops.md` edits reach all repos:
  `readlink ../vista_bench/docs/claude_ops.md` returns `../../research-skills/claude_ops.md`
  (same file by construction; a changed target means the symlink broke).
- **Dogfood — audit touchpoint** — run the new `/review-plan` verification pass on a real
  VM-handoff-bound plan (a current vista_bench or vista-eval plan) and confirm it (a) selects
  sensible archetypes, (b) proposes a **Handoff phasing** decomposition, (c) surfaces an
  expected-vs-unexpected envelope, and (d) does **not** merely re-emit the old lens findings
  (its output is one distinct verification/handoff section, not a duplicate of the design
  review) — all without restating the per-repo checklist's recipes.
- **Dogfood — generative touchpoint** — start from a real *thin* VM-bound plan whose
  Verification section is bare, and use the new authoring guidance to draft its **Handoff
  phasing** schema + envelope before review; confirm the guidance is followed without pulling
  the whole canonical spec into the plan doc.
