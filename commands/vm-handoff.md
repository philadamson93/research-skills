---
name: vm-handoff
description: Author and close the planner-Mac → executor-VM handoff round-trip. TRIGGER on explicit /vm-handoff, or proactively (offer via AskUserQuestion) after planner-Mac work that has never executed and needs first-time validation on real VM data. SKIP when the run is results-producing (linear-probe / KNN / cross-modality sweeps — read from the auto-generated HTML, not smoke-gated) or trivial. Auto-detects author (Mac) vs readback (VM) mode by `hostname` per claude_ops.md Machine-Aware Operating Mode. In author mode it DERIVES the runnable docs/vm-status/<date>-<sha>.md doc from the plan's "Verification & VM handoff" criteria (renders them, never invents) and gives you a tiered sign-off gate before landing; in readback mode it appends the VM's run results into the SAME doc, closing the loop. Reuses /review-plan, /plan-handoff-readiness, /phi-vet, and /commit-review rather than duplicating them.
---

# vm-handoff

## The principle

VISTA work is split across two machines: the **planner Mac** authors plans, configs, and
scripts but **cannot run code** (no runtime, GPU, data, or credentials); the **executor
VM** holds the runtime + data mounts + credentials and runs everything. Every non-trivial
change therefore crosses a machine boundary at least once, and the thing that crosses it is
a *handoff doc*: the planner's statement of what to run, how to tell it worked, and when to
stop and hand back.

The success criteria of that handoff are **not invented here** — they live in the plan. A
VISTA plan's *Verification & VM handoff* section (per `claude_ops.md` Plan Document
Structure) already states what runs on the VM and the per-step **Expected** / **Stop**
criteria, and `/review-plan` already audited them. This skill's author mode **renders** that
already-reviewed section into a concrete, copy-paste-runnable `docs/vm-status/<date>-<sha>.md`
instance; its readback mode records the VM's results back into the same doc. The durable
*spec* is the plan; the vm-status doc is one dated *execution* of it.

This skill does not decide *who* is planner vs executor — that's `claude_ops.md`'s
Machine-Aware Operating Mode. It consumes that posture and does the handoff.

## Where this sits in the workflow chain

```
PLANNER MAC
  plan mode → docs/plans/X.md  (incl. "Verification & VM handoff": Expected/Stop)
  /review-plan X            ── audits the design AND the success criteria
  /plan-handoff-readiness X ── is the criteria section present & implementable?
  …implement (author configs/scripts — can't run them on the Mac)…
  /review-implementation X · /review-tests X   ── structural audits vs the plan, then route VM-bound work here
  /vm-handoff  ───────────▶ RENDER the plan's criteria into docs/vm-status/<date>-<sha>.md
       │                    (implementation is still UNCOMMITTED at this point)
       └ tiered success-criteria gate (your sign-off) ──┐
       └ offers → /commit-review (bundles doc + impl) → /phi-vet → push  ────┘
EXECUTOR VM
  pull, run the steps
  /vm-handoff (readback)   ── results appended into the SAME doc
       └ offers → /phi-vet → /commit-review → push
BACK ON MAC
  pull → clean = done · a Stop fired = re-enter plan mode (revise the plan, loop)
```

**Reuse, never duplicate.** Upstream criteria-review is `/review-plan` on the plan; landing
each leg is `/commit-review → /phi-vet`; an independent *re-audit of the criteria* is
`/review-plan` on the **plan** (where they live and where its design-shaped lenses fit), not
on the rendered vm-status doc. The only things this skill uniquely adds are the
**render-from-plan** step, the **tiered sign-off gate**, and the **loop-back** when a Stop fires.

## Mode dispatch — `hostname` decides

Run `hostname` first and resolve the machine's role from the repo's machine posture (its
`CLAUDE.md` / machine registry, per `claude_ops.md` Machine-Aware Operating Mode):

- **Planner (the Mac, no runtime)** → **Author mode** (render the handoff doc).
- **Executor (the VM with data + credentials)** → **Readback mode** (append results).
- **Unknown hostname** → do not guess. Ask which role applies, and offer to record it
  wherever the repo declares its posture (its `CLAUDE.md`, or a `docs/machines.md` if it
  uses one — `claude_ops.md` is deliberately non-prescriptive about which) so the next
  session doesn't re-prompt.

State the detected mode in one line before acting (`On phil-mbp → planner → author mode`)
so a mis-detection is visible and correctable.

---

## Author mode (planner Mac)

### Phase A1 — Confirm this handoff is warranted

`/vm-handoff` is for work that **has never executed** and needs first-time validation on
real data. **Skip** (say so and stop) when:

- The run is **results-producing** — linear-probe / KNN / cross-modality sweeps. Per
  `claude_ops.md`, those are read directly from the auto-generated HTML
  (`<results-root>/<version>/<modality>/<dataset>/reports/<model>_<dataset>.html`) and the
  on-disk parquets; a one-line pointer in `next.md` to the launch command is enough.
- The change is **trivial** (doc tweak, single-file fix, formatting).

When proactive (not an explicit `/vm-handoff`), offer the skill via `AskUserQuestion`
rather than authoring unprompted.

### Phase A2 — Locate the plan and its criteria (the source of truth)

Find the canonical `docs/plans/<...>.md` this work implements and read its **Verification &
VM handoff** section — that is what you render. Two checks:

- **Criteria present?** If the plan has no Verification & VM handoff section (or it's a bare
  "run it and see"), the plan isn't handoff-ready. **Do not invent criteria here.** Point
  back: run `/plan-handoff-readiness` on the plan and add the Expected/Stop section there
  (so `/review-plan` can audit it), *then* return to `/vm-handoff`. Inventing un-reviewed
  success criteria at handoff time is the exact failure this chain prevents.
  - **Ad-hoc exception:** for a genuine one-off with no plan (e.g. *"does this script even
    import on the VM"*), you may author a minimal handoff without one — but **state the
    Expected/Stop criteria inline and flag them as ad-hoc (not plan-derived, not
    `/review-plan`-audited)** so the un-reviewed status is explicit on the page. If the smoke
    grows past a one-off, promote it to a plan and re-derive.
- **Plan reviewed?** If a `docs/plans/reviews/<plan-stem>-feedback.md` exists unprocessed,
  surface it once (like `/read-plan` does) before rendering.

Then auto-capture the header facts by reading git / shell (metadata, not running project
code — allowed on the Mac):

- **Date** — `date +%F`. **Branch** — `git branch --show-current`.
- **Commit-state honesty** — the most-dropped field. If the work under test is **already
  committed**, capture `git rev-parse --short HEAD` and name the doc `<date>-<sha>.md`. If
  it's **uncommitted on the Mac**, say so: *"authored this session, never executed — commit
  + push before pulling on the VM; SHA set at commit time"* and name it
  `<date>-<descriptor>.md`. Never write a SHA that doesn't exist yet as if the VM can check
  it out. **Descriptor-named docs are permanent** — don't rename them to a SHA after the
  commit (real practice keeps the descriptor name); the prior-handoff link and the `next.md`
  pointer use the descriptor name too. Reserve `<date>-<sha>.md` for work that is *already*
  committed when you author the handoff.
- **Prior-handoff link(s)** — the most recent `docs/vm-status/*.md` this continues, so the
  lineage of what-ran-when is walkable from this doc alone.

### Phase A3 — Render the doc (one doc per session)

Author **one** doc per handoff session at `docs/vm-status/<date>-<sha>.md`, translating the
plan's Verification & VM handoff section into copy-paste-runnable steps. It is
self-contained: the executor never *has* to read the plan to run it (it links the plan for
depth, but states what to run inline). Skeleton:

```markdown
Reference: docs/claude_ops.md

# VM <verb> — <one-line scope>, <version>

**Status: Handoff to VM** (<date>)
**Branch:** `<branch>` (<pinned SHA, or "commit+push first, SHA set at commit time">)
**Machine posture:** authored on the planner Mac (no runtime). Everything below has **never executed** — run it on `<vm-host>` (executor, holds <data it needs>).
**Plans:** [`<plan-stem>.md`](../plans/<plan-stem>.md#verification--vm-handoff) <— criteria source of truth
**Prior handoffs:** [`<date>-<sha>.md`](./<date>-<sha>.md) (omit if first)

## Why this doc
<What changed, what has never run on real data, and what a clean result unblocks — 1 paragraph.>

## Step 0 — get the artifacts onto the VM
```bash
cd <repo>
git checkout <branch> && git pull
uv sync --extra dev
```
**Expected:** clean checkout at the intended SHA; lockfile resolves.
**STOP:** none — pure setup.

## Step 1 — <name>   (rendered from the plan's Expected/Stop for this step)
```bash
<exact, copy-paste-ready command(s) with full paths / flags / env>
```
**Expected:** <exit 0; `<path>` exists & non-empty; metric in sane range; skip-log correct>
**STOP:** <the named halt-and-report conditions. `STOP: none — <reason>` only for steps with no project-specific halt.>

## Step N — ...

## Step <final> — launch the full run (optional; only after smoke is clean)
```bash
<the real run command — e.g. the sweep script>
```
**Expected:** launches; results land at `<results-root>/.../reports/*.html` + parquets.
**STOP:** none — this step *points at* the launch; its results are read from the HTML, **not** pasted into this doc (per `claude_ops.md`). Omit entirely if there is no "real run" beyond the smoke.

## Report back
<What the VM appends on readback: per-step pass/fail, tracebacks, decision-gate outcomes,
counts. What to read from HTML instead of pasting. NO PHI.>

## VM run results
_(left empty by the planner; the executor fills this in readback mode)_
```

Every runnable step carries **both** an Expected block and a Stop line (escape hatch:
`STOP: none — <reason>`). See "Expected vs Stop" below; these should be *traceable to* the
plan's criteria, not freshly authored.

**Multi-repo handoff:** keep it **one doc**, but give Step 0 a checkout block per repo (pin
each repo's branch / SHA explicitly) — cross-repo SHA ripple is exactly why the lineage
belongs in a single place.

### Phase A3.5 — Tiered success-criteria gate (your sign-off)

Before landing, surface the criteria for your input — sized to the handoff's complexity:

- **Simple handoff** (a few steps, no decision gates, single repo) → **lightweight
  sign-off**: present the Expected/Stop criteria compactly via `AskUserQuestion`
  (Approve / Revise / Independent review). Cheap eyeball, you stay the gate.
- **Complex handoff** (decision gates, cross-repo SHA ripple, many steps) → in the same
  `AskUserQuestion`, **offer (recommended) to re-audit the criteria at their source: `/review-plan`
  on the plan**, where the criteria live and its design-shaped lenses fit. (Pointing
  `/review-plan` at the rendered vm-status doc works mechanically but yields design-flavored
  findings, not "are these steps runnable / are the Stops complete" — so audit the plan, and
  let this gate confirm the render is faithful and copy-pasteable.)

Revise → edit and re-surface. Approve → Phase A4.

### Phase A4 — Wire the pointer, then offer to land

- Add a **one-line pointer** in the repo's tracking doc (`docs/next.md`, else `next.md`,
  else `NEXT.md` — same precedence as `/next`; create `docs/next.md` if none exists):
  `- VM smoke pending: [docs/vm-status/<date>-<sha>.md](...) — <one-line what>`. Pointer in
  the tracking doc; substance in the handoff doc (pointer-style discipline, like `/wrapup`).
- Then **offer the next step** via `AskUserQuestion`: run `/commit-review` now, or stop
  here. This is the **single** commit-review for the whole change: because the handoff doc
  was authored while the implementation is *still uncommitted* (`/review-implementation` ·
  `/review-tests` route VM-bound work to `/vm-handoff` **before** the commit-review phase),
  `/commit-review` lands the doc **and** the code it documents (the configs/scripts/tests) in
  **one** PHI-vet + push — not a second cycle after the code already landed. That bundling is
  the reason `/vm-handoff` runs before `/commit-review`, not after. Don't auto-fire it —
  offer it (per `claude_ops.md` Skill Composition). (`/commit-review` escalates to `/phi-vet`
  in medical-data repos — though on the planner Mac `/phi-vet` is inert per its machine gate,
  so the real PHI scan is the VM readback leg, Phase R2.)

---

## Readback mode (executor VM)

The VM ran what the doc said. Close the loop **in the same doc** — one doc per session,
author-then-readback. Do not start a new file or route results to a sibling.

### Phase R1 — Fill `## VM run results`

Under the doc's `## VM run results` heading (create it if the doc predates this skill and
lacks one), append a stamped section:

```markdown
## VM run results — `<hostname>`, <date>, ran at `<sha>`
- **Step 0:** ✅ checked out `<sha>`, sync clean.
- **Step 1:** ✅ / ❌ <outcome vs the Expected block; if ❌, the traceback or failing eyeball>
- **Step N:** ...
- **Decision gates (class 2):** <which branch the data selected, with the number that decided it>
- **In-lane corrections (class 1):** <any mechanical fixes made inline, so the planner sees them on pull>
- **⚠️ DEVIATION (class 3):** <expected vs found · why it blocks · escalating to planner> — only if one fired
- **Net:** <smoke clean → cleared to launch the full run · BLOCKED on deviation → back to planner>
```

Record each result **against its Expected block** (so go/no-go reads at a glance), and
**honor every Stop**: if a Stop fired, halt and report it here — do **not** improvise past
it, pick a fallback, or "fix" a planning-level problem. That is the Executor-lane rule from
`claude_ops.md`; the Stop conditions are its concrete teeth. When a Stop reveals the plan
*itself* is wrong, that's a **class-3 deviation** — see *Deviation workflow* below for how
it routes back to the Mac (the blocked doc is never edited to fix the plan).

### Phase R2 — PHI gate the readback (medical-data repos)

The VM touches real medical data; the readback is the likeliest leak point. Before
committing the results, run **`/phi-vet`** (or honor its gate hook): **no** patient
identifiers, sample rows, accession/DICOM UIDs, clinical dates, or report text — only
counts, metrics, pass/fail, and tracebacks scrubbed of data. Read large results from the
HTML / parquets; never paste them in.

### Phase R3 — Offer to land, then update the pointer

**Offer** (via `AskUserQuestion`) to run `/commit-review` (which escalates to `/phi-vet` in
medical-data repos) to push the results section. On landing, update the `next.md` pointer's
status (`VM smoke pending` → `VM smoke PASS <sha>` / `BLOCKED — see doc`). The planner pulls
and reads the round-trip from one file.

---

## Deviation workflow — when a finding contradicts the plan

Execution surfaces things planning didn't foresee. Every finding — VM-side during a run, or
Mac-side after a handoff shipped — is classified by one question, *does it change the design
or the Expected/Stop criteria?*, and routed accordingly:

| Class | What it is | Who handles it | Round-trip |
|---|---|---|---|
| **1 — in-lane correction** | Mechanical / local; design + criteria unchanged (wrong path, missing env var, fixture regen) | Executor fixes inline, records it under **In-lane corrections** in the readback | No |
| **2 — decision-gate** | A fork the plan *anticipated*; the Stop says "if X → A else B" | Executor picks the branch, records the deciding number | No (pre-authorized) |
| **3 — plan-level deviation** | Contradicts a plan assumption, changes scope, or invalidates the approach | Executor STOPs, documents the finding, hands back | Yes |

**Bright line (1 vs 3):** if the finding changes what *Expected/Stop* means, it's class 3.
The executor **self-classifies and fixes only obvious class-1 mechanical issues**; **when
uncertain, escalate** (`claude_ops.md` forbids the executor major-rewriting without
confirmation). If the session is live, surface the finding to the user rather than deciding
silently. The more forks the plan pre-encodes as class-2 decision gates, the fewer class-3
round-trips — anticipating likely deviations is a plan-authoring discipline, not a handoff one.

### VM → Mac (class 3 surfaced during a run)

1. **VM:** STOP. Write a `⚠️ DEVIATION (class 3)` block in `## VM run results` — *expected vs
   found, why it blocks* — flip the `next.md` pointer to **BLOCKED**, push. Do **not** fix
   the plan; the finding travels back in the readback (that is its home — no separate
   findings log).
2. **Mac:** pull, read the finding, **re-enter plan mode** with it as the input
   (`claude_ops.md` Core Principle #2 — re-enter plan mode when direction changes).
3. **Mac:** revise the plan's approach + *Verification & VM handoff* criteria; `/review-plan`
   audits the delta; `/plan-handoff-readiness` re-checks the criteria section.
4. **Mac:** `/vm-handoff` renders a **new** vm-status doc that **supersedes** the blocked one
   (see below), linking it as a prior handoff.
5. **VM:** runs the new doc.

### Mac → VM (planner invalidates a shipped handoff)

- **VM not yet started** → supersede: render a new vm-status doc, mark the old one
  superseded, flip the `next.md` pointer. **The live handoff is always the newest
  non-superseded `docs/vm-status/*.md`** — the VM confirms that before launching.
- **VM mid-run** → the planner flags direction-changed; the executor halts at the next safe
  step (treat as a Stop), reports where it got to in the readback, and the supersede flow
  takes over. Cross-machine signalling is async via git — the `next.md` pointer status and
  the superseded header are the source of truth, not a live channel.

### Superseding, not editing

A blocked or invalidated doc is **never edited to carry the revised plan** — it is the
historical record of a run that hit a wall. The revision is a *new* doc:

- New doc header: `**Prior handoffs:** [<blocked-doc>](...) — superseded; see its DEVIATION block`.
- Blocked doc gets a top banner: `> **Superseded by [<new-doc>](...)** (<date>) — <one-line why>`.

One doc per run, lineage walkable both directions. This is why findings live in the readback
(step 1 above): the supersede chain *is* the record of what reality taught the plan.

## Expected vs Stop — the discipline this skill enforces

Every runnable step carries **both**, traceable to the plan's criteria; the skill does not
finalize a step that lacks either (escape hatch: explicit `STOP: none — <reason>`, which
turns a forgotten Stop into a conscious decision):

- **Expected** = *what a correct run looks like* — the executor's self-check for "go." Render
  it as the `**Expected:**` block (older hand-written docs label it `**Eyeball:**` — same
  concept; standardize new docs on `Expected` so the readback's "record against the Expected
  block" matches the page). Always substantive: exit codes, files that must exist & be
  non-empty, metric ranges, skip-logs. Without it, the executor can't tell a clean pass from
  a silent corruption.

- **Stop** = *the named conditions under which the executor halts and reports instead of
  pushing forward.* Three flavors:
  - **Precondition stop** — "if an embedding is missing → generate it or drop that config
    *before* the sweep."
  - **Failure stop** — "AUROC pinned at 0.5 → path/extraction bug, STOP"; "if the fail-fast
    guard test does *not* go red, the wiring is broken, STOP."
  - **Decision gate** — "if metric X < threshold → Design A, else Design B": a fork the
    executor *can* resolve inline (record which and why), versus one it must escalate.

  Without a Stop, the executor improvises past a real problem — exactly the failure
  `claude_ops.md` warns against ("don't assume fallbacks are preferred — they can mask
  upstream errors"). `STOP: none — pure setup` is legitimate for setup steps; a
  *consequential* step (a smoke run, a gate) lacking a Stop is the bug this skill prevents.

## What this skill deliberately does NOT do

- **Decide planner vs executor roles** — that's `claude_ops.md` Machine-Aware mode.
- **Author or audit the design** — the success criteria live in the plan's *Verification &
  VM handoff* section and are reviewed by `/review-plan`; this skill renders them. If the
  plan lacks the section, fix the plan (`/plan-handoff-readiness`), don't invent here.
- **Carry eval results** — results-producing runs go to HTML/parquets per `claude_ops.md`;
  the handoff doc is smoke / verification only. It *may* point at the launch command for the
  real run once smoke is clean (real docs do — the optional final step in the skeleton), but
  the results themselves are read from the HTML, never pasted in.
