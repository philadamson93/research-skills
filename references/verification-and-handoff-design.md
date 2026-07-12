# Verification & VM-Handoff Design — canonical spec

The single source of truth for **what to verify** and **how many VM handoffs to run** when a
VISTA plan will execute on the VM. Two touchpoints consume this file; neither restates it:

1. **Generative — during plan authoring.** When a VM-handoff-bound plan is being written, use
   this spec to co-design the plan's *Verification & VM handoff* section (including its
   **Handoff phasing** sub-block). Tiered by the complexity classifier below: draft inline for
   a *simple* handoff; spawn a dedicated verification-design subagent for a *complex* one.
2. **Audit — during `/review-plan`.** For a VM-handoff-bound plan, the verification-design
   reviewer pass audits that section against this spec + the repo's `plan-review-checklist.md`.

**Why this exists.** VM handoffs are the only way VISTA work is verified against real data, and
each round-trip is expensive — a `/commit-review` + `/phi-vet` on both the Mac and the VM leg,
plus wall-clock waiting on the VM. So *what* we verify and *how few* round-trips it takes are
worth deliberate design, before the expensive cycles begin. **"Unit tests pass on the local
Mac" is not VM verification** — the plan must name the checks that run against the *real*
runtime (which scripts / queries, against which dataset version, with what inputs, compared to
what).

**Scope discipline.** This spec owns archetype *selection*, the *envelope*, and the *batching*.
It does **not** own repo-specific recipes (exact queries, table names, sample sizes, dataset
versions) — those live in each repo's `.claude/references/plan-review-checklist.md`, which this
spec defers to. It does **not** own the operational mechanics of running a handoff (rendering
the vm-status doc, the tiered sign-off gate, Expected/Stop enforcement, the class-1/2/3
deviation taxonomy, supersede) — those are owned by `/vm-handoff`; point at it, don't restate.

---

## 1. What to verify — the archetype menu

A VM-bound plan's verification should *select from* this menu the archetypes its change
actually warrants, and *propose the ones it's missing*. Not every plan needs every archetype;
the point is that the choice is deliberate. Ground each selected archetype in the repo's
`plan-review-checklist.md` for the concrete recipe.

- **Cheap-gate-first ordering.** Sequence checks cheap → expensive → destructive so a failure
  halts early and cheap: import / `--collect-only` / structural tests → focused test gate →
  full-suite regression → real-data run → any destructive write (materialize / publish) last.
- **Focused → full-suite regression, with delta-anchored counts.** Run the directly-touched
  tests, then the full suite. State the *expected delta*, not just "green": e.g. "642 passed,
  net +1 vs the <sha> baseline — the one new test; nothing else changed." A bare
  pass-count with no baseline can't distinguish a real regression from an expected shift.
- **Migration / re-anchoring consistency diff.** When a change re-materializes an existing
  output, diff the new run against the prior published one — EXCEPT-DISTINCT **both
  directions**, against a **scratch** target (never overwrite published). Report the shape:
  "N gained / M changed-persons / K answer-flips." Pair with a **pre-declared envelope** (see
  §2) so an *expected* re-anchoring resolves inline instead of round-tripping.
- **Before/after refactor parity.** For a behavior-preserving refactor, diff the old vs new
  output at a numeric tolerance. **Pin exact (delta = 0 / EXACT) for equivalence; use a loose
  band for metrics.** Two-checkout diffs (old engine on the base, new on the branch) are the
  strongest form; bank the passing baseline so it isn't re-run.
- **Data-sanity checks.** Row counts; **informative** coverage (exclude padded sentinels like
  `Unknown` / `Not applicable`, not raw non-null); per-person / per-key uniqueness; label
  domain within its allowed set; cardinality / 1:1 relationships that a join relies on.
- **Schema / contract checks.** Column *set and order*; dtypes; JSON / envelope shape with
  explicit **accept AND reject** cases (a well-formed input is accepted; a malformed one
  raises the right error).
- **Edge / boundary cases.** Plausibly-beyond-happy-path inputs raise the *right error type*
  with a regex-matched message; boundary values (zero, exact-window-day, empty collection) get
  exact-boundary tests rather than being assumed.
- **Cross-task / cross-label logical invariants** (logically necessary given the data
  semantics, not data-dependent): subset / monotonicity / implication — e.g. death is
  monotonic so shorter-horizon survival is a subset of longer; progression implies alive; a
  relaxed cohort is a strict superset of the strict one with **delta-attribution = 0
  unexplained** rows.
- **Domain-knowledge sanity — relative over absolute.** Prefer relative orderings, ratios, and
  self-consistency (Stage IV mortality > Stage I; shorter-horizon positive-rate ≥
  longer-horizon; plausible-age band; treatment-date after diagnosis-date). **Never pin
  absolute percentages** — they lock in the current cohort's distribution and break on
  legitimate drift. When unsure an invariant holds, raise it to the user rather than assert it.
- **Metric-sanity floor.** A metric pinned at 0.5 (or NaN, or a perfect 1.0 on real data) is a
  path / extraction / fixture bug, not a result — make it an explicit STOP. Confidence
  intervals must not invert.
- **A guard that must go RED.** For a new fail-closed guard (a seed gate, a policy check, a
  negative test), the verification includes *proving the guard fires* — if it does **not** go
  red when it should, the wiring is broken → STOP. A guard you never saw fail is a guard you
  can't trust.
- **Named silent-fallback / silent-corruption traps → explicit STOPs.** Enumerate the specific
  ways this change could pass while being wrong, and make each a STOP: a stale-vocab / fake
  scorer silently substituted; an empty-regex that matches everything (zero-cohort footgun); a
  finite-but-reversed volume that passes `isfinite` while corrupting orientation; a silent
  zero-row merge; an unconditional normalization applied twice; a match-report category count
  that jumps without failing the run.
- **PHI-isolation as a first-class check.** Negative controls that *must be denied* (a 403 / a
  permission-denied); and a **PHI-clean readback contract** — counts, metrics, pass/fail, and
  scrubbed tracebacks only; never sample rows, identifiers, dates, accession / DICOM UIDs, or
  report text. (Enforcement of the readback is `/phi-vet` + `/vm-handoff`'s readback rule; this
  spec just insists the plan *selects* the control.)
- **Reject substring asserts on rendered output.** An `assert 'X' in rendered_sql / json /
  html` tests what's trivially true in the source and passes coincidentally when the substring
  lives in an unrelated field. Diagnostic question: *"what behavior does this prove?"* — if the
  only honest answer is "it rendered without crashing," rewrite as a render-smoke plus the
  actual behavioral check (EXCEPT-DISTINCT / row-count parity / typed-field assert / upstream
  contract assert on the registry the render depends on).

---

## 2. The expected-vs-unexpected envelope

The single highest-leverage discipline for cutting round-trips. For each **consequential**
step, the plan states not only what a correct run looks like, but what a *surprising-but-benign*
result looks like versus a *real bug* — so the executor resolves benign surprises inline (a
class-2 decision gate) instead of escalating (a class-3 round-trip).

- **Pre-declare the expected diff magnitude / shape.** If a change is expected to move existing
  outputs (a re-anchoring, a coverage expansion), state the expected magnitude and which
  movements are benign vs which signal a bug — and encode it as a decision gate. *Real cost of
  not doing this:* a migration STOPped as a class-3 deviation on a "118 changed / 292 flips"
  diff that was later accepted as expected re-anchoring — a pre-stated envelope would have made
  it an inline class-2 resolution and saved the round-trip.
- **Pre-list known / carried-forward reds.** Enumerate the tests / warnings that are *already*
  red before this change (with their source), so the executor doesn't chase them: "these 4 are
  carried forward from <sha>, tracked in backlog; anything else red → STOP." Same for
  environment-gated skips (GPU-only tests on a CPU box) and benign forward-drift (a newer
  generator emits an extra optional field — note and continue).
- **Match the STOP threshold to the plan's *actual* criterion.** A threshold scoped to the
  wrong quantity manufactures a spurious block. *Real cost:* an aggregate-drop STOP fired on
  the aggregate when the plan's real criterion was negative-duration-drop — the executor had
  to partition the drops itself to avoid a false block. State the threshold on the exact
  quantity the criterion is about.
- **Get the Expected units / identifiers right.** A person-count vs study-series-count mix-up in
  an Expected line manufactured a false STOP. Name the unit and the key precisely.
- **Every consequential step carries both an Expected and a STOP.** Expected = what a correct
  run looks like (substantive: exit codes, files that exist and are non-empty, metric ranges,
  skip-logs). STOP = the named conditions to halt and report instead of pushing forward
  (precondition / failure / decision-gate). `STOP: none — <reason>` is legitimate only
  for pure-setup steps; a consequential step lacking a STOP is the bug this discipline prevents.

---

## 3. How many handoffs — the batching discipline

The number of handoffs is a design decision, not an accident. Minimize expensive round-trips:

- **Order steps cheap → expensive → destructive**, with a STOP before each irreversible action
  (materialize to a scratch / temp target before publishing), so a failure costs the least.
- **Bundle all checks that share one checkout / SHA into one handoff.** One handoff per
  code-change increment. Split out only: checks that need *new data* not yet available, checks
  that need a *different executor class* (a machine boundary is a phase boundary — see §4), or
  checks *gated on a decision* that hasn't resolved.
- **Pre-encode every foreseeable fork as a class-2 decision gate** the executor resolves inline
  ("if X → A, else B; record which"). More gates = fewer round-trips. Reserve round-trips
  (class-3) for genuine plan-premise violations.
- **Bank passed steps by readback SHA; re-hand off only the unresolved set — but un-bank any
  step whose inputs moved.** A superseding handoff carries a "Banked — do not re-run" block
  naming the banked steps + the SHA each was proven at, and re-runs only what's open. *But* if a
  banked step's inputs changed (a merge folded `origin/main` in, a dependency was updated),
  un-bank and re-run it.
- **new scope → new doc; same question + new evidence → append a readback.** A blocked or
  fix-cycle result appends into the *same* doc; a genuinely new stage gets a new doc that links
  the prior as a superseded / prior handoff.
- **Decision-first sequencing.** Don't author the implementation handoff behind an unresolved
  design fork — author the fork-resolving handoff first. And when a design rests on a
  *contested / unverified* assumption, a cheap **pre-implementation gate** can refute a wrong
  path before it's built (worth minting even though it adds a handoff).
- **Multi-target bundling caution.** Two independent targets in one handoff means one can
  deviate mid-doc while the other ships — weigh whether independent targets deserve independent
  handoffs.
- **Firewall OUT of smoke handoffs:** results-producing runs (linear-probe / KNN / sweeps — read
  from the auto-generated HTML, not pasted into a handoff doc) and not-yet-built phases (state
  an explicit scope guard: "phase X is out of scope; it gets its own handoff after Y lands").
- **Under-splitting is also a failure.** A "just a validator / just close one step" change that
  was pushed with no handoff doc still needed one — it had never been gated and had to
  retroactively author a gate. A change that touches runtime behavior warrants a handoff even
  when it feels too small to bother.

---

## 4. Which machine — the executor-fleet taxonomy

The "executor VM" is not one box — it's a small fleet of **capability classes**, and *which*
class a check runs on is a verification-design decision the plan should state, not a runtime
accident. A machine boundary is a **phase boundary** (§3): route each check to the class that
fits its workload, and when a check's run-machine differs from where its readback happens, split
the phase so the boundary is explicit.

Three classes (routed by capability, not by hostname):

- **Claude-Code CPU** — a standard-CPU executor with Claude Code installed plus the repo's data
  mounts + credentials. The **default** executor and the interactive one: smoke tests, structural
  readback, BigQuery / OMOP queries, moderate aggregator and eval runs. It is the **only** class
  that can run `/vm-handoff`'s readback itself (the readback append is Claude-driven), so every
  handoff whose results are read back by Claude lands here.
- **High-throughput CPU** — a many-core executor **without** Claude Code, provisioned for
  embarrassingly-parallel CPU throughput: large-scale preprocessing (sharded download / convert /
  manifest), linear-probe / KNN parallelization across many tasks, batch jobs that saturate cores.
  The *run* is launched here (by a human or a script); the `/vm-handoff` readback is **not** — it
  happens on the Claude-Code CPU box (or the Mac reads the results / logs), because this class has
  no Claude Code.
- **GPU** — an accelerator executor for model **training**, **embedding generation**, and
  GPU-only tests. Same Claude-Code-absent posture as high-throughput CPU: the compute runs here,
  the readback happens on the Claude-Code CPU box (or the Mac reads results).

**Run-machine ≠ readback-machine.** For the two non-Claude-Code classes, the box that runs the
compute is not the box that runs the readback. State both in the plan and render both in the
handoff — *"run Step N on the GPU / high-throughput-CPU box; read results back on the Claude-Code
CPU executor"* — and treat the machine switch as its own phase so the split is designed, not
assumed.

**The runnable artifact differs by class — a doc for Claude-Code, a script for the rest.** The
`docs/vm-status/<date>-<sha>.md` handoff doc is a **Claude-driven** artifact: it presumes a
Claude-Code executor that *reads* the steps, *runs* them, *interprets* each Expected/Stop, and
*appends* the readback. A high-throughput-CPU or GPU box has no Claude Code, so it cannot be told
*"pull the branch and run the vm-status doc"* — there is no agent there to interpret it. (This is
the concrete failure this section exists to prevent.) For any step whose **run** lands on a
non-Claude-Code class, the plan therefore carries two operator-usable deliverables in place of
Claude-interpreted steps:

- **A standalone runner script** — committed to the repo (listed in the plan's *Files to Modify*,
  authored on the Mac during implementation like any other script — the Mac can write scripts it
  cannot run) that does env setup (`uv sync` with the right extras, any required env exports such
  as `HF_HUB_DISABLE_XET` / `HF_TOKEN`) **and** the run end-to-end, so the box needs **one command
  and no Claude**. Committed runner scripts are already the established practice (e.g. a
  `run_<x>_vm.sh` / `run_<x>_gpu.sh` per repo); this makes them the *required* artifact for a
  non-Claude-Code run, not an optional convenience.
- **Plain operator run-instructions** — which branch to check out, any precondition to land first,
  the single command to invoke (`bash scripts/run_<x>.sh`), and where results land (the HTML /
  parquets / logs) for readback. `/vm-handoff` renders these as an operator run-block that *points
  at* the script, rather than the per-step Expected/Stop it renders for a Claude-Code box.

**Self-provision regenerable inputs — don't inherit a prior run's scratch.** *One command
and no Claude* also covers the step's **inputs**, not just its env. When a step consumes a
producer artifact from an earlier phase (a localization CSV, a manifest, a cached embedding),
decide its provenance deliberately: a **durable** artifact (committed, or on a persistent
mount) is referenced by path; an **ephemeral** one — a smoke run's `/tmp` scratch, often
correctly short-lived because it carries PHI-adjacent content — will not survive across runs
or across the machine boundary, so the consuming runner regenerates it on demand rather than
assume it is still there. Shape it as: input path provided → use it; unset / absent →
self-provision a minimal N-row copy (kept ephemeral when PHI-adjacent); the underlying mount /
producer genuinely missing → fail-fast with the exact command to produce it. *Real cost of
not doing this:* a GPU runner that hard-required the path a small verification smoke had left
in `/tmp` failed at its precondition when the next operator ran it a day later on a swept
`/tmp` — a self-provisioning fallback would have kept it the intended one command.

**Default shape — phase the Claude judgment ahead of the throughput run.** The judgment-heavy,
correctness-critical gates (a modality-aware join that could silently zero-merge, a before/after
parity check, the metric-sanity floor) run as a *small* Claude-driven smoke on the Claude-Code CPU
box first; a clean smoke is the STOP-gate that releases the standalone full-throughput run on the
high-throughput-CPU / GPU box — only the *smoke* is gated here; the run's own results firewall out
to HTML per §3 (read on the Claude-Code CPU box, or the Mac reads the HTML), never pasted into a
handoff doc. This catches the correctness bug cheaply, before the expensive run. The
**fully-standalone self-gating** variant — every gate baked into the script as an exit-non-zero
assertion, no Claude anywhere — is the fallback for when there is no cheap Claude-verifiable smoke;
state in the plan which shape applies and why.

**Concrete class → host binding is repo-local.** This spec names *capability classes*, not
machines; the actual hostnames (and which repo's data each mounts) live in the repo's machine
posture — its `CLAUDE.md` / machine registry, per `claude_ops.md` Machine-Aware Operating Mode —
keeping specific host identifiers out of this shared spec.

---

## 5. The Handoff phasing schema

The batching decision above is recorded in the plan's *Verification & VM handoff* section as
a **Handoff phasing** sub-block (the final item after `Anticipated forks`, per `claude_ops.md`'s
Plan Document Structure). It is a compact **per-phase schema**, not free prose, so
`/review-plan`'s handoff-readiness lens can check its fields. Required for **complex-tier** plans (per the
classifier); a **simple** single-phase handoff states its one phase inline.

```
Phase N — <name>
  · purpose               what this phase proves
  · machine               which executor class runs it (Claude-Code CPU / high-throughput CPU /
                          GPU); name the readback machine too when it differs (§4); for a
                          non-Claude-Code run, name the committed runner script + operator run-block
  · banked-from-prior     which prior steps / SHA carry forward and are NOT re-run
  · gates                 the class-2 forks the executor resolves inline (if X -> A, else B)
  · destructive?          any irreversible write in this phase (STOP before it)
  · stop / deviation      the class-3 conditions that halt and hand back
  · next-doc trigger      what result opens the next phase / handoff
```

`/vm-handoff` *renders* the next phase into a runnable `docs/vm-status/<date>-<sha>.md` doc; it
does not invent the phasing — it reads it from here.

## Complexity classifier (both touchpoints share it)

- **Simple** = one handoff, one repo, no decision gates, no banked prior-SHA, no destructive
  write. → Generative: draft inline. Audit: a mandatory distinct section within the single
  chosen reviewer's pass. The single phase is stated inline; no separate schema required.
- **Complex** = **any** of { cross-repo SHA ripple; more than one handoff phase; class-2
  decision gates; bank / un-bank logic; destructive or irreversible writes; multi-target
  bundling; more than one executor class (§4), which forces a run-vs-readback split }. →
  Generative: spawn a dedicated verification-design subagent (keeps the main
  planning context lean). Audit: a separate focused reviewer invocation, authorized by the
  reviewer choice already made for the design review (runs **silent** — no second prompt).

---

## 6. Defer to the per-repo checklist

Each repo's `.claude/references/plan-review-checklist.md` holds the concrete, repo-specific
recipes this spec deliberately does not: exact queries / scripts, table and dataset-version
names, sample sizes, sibling-repo contracts, modularity precedents, and the repo's own
cross-task invariants and domain-sanity checks. Formats differ across repos (some use explicit
`Recipe / Sample-size / Diff-against` headings; others group by change-type) — do not assume a
uniform shape. This spec provides the *menu, envelope, and batching*; the checklist provides
the *recipe*. A repo with no checklist (e.g. rad-eval, as of this writing) leans harder on this
spec's generic menu until one is seeded.
