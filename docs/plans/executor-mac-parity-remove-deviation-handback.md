Reference: claude_ops.md

# Executor/Mac parity — retire the vm-handoff doc mechanism entirely

**Status: Completed** (2026-08-24) — landed to `main` `1743127` (ff), branch + worktree pruned.
Directed live in conversation (`Reviewed: No` in `docs/plans/README.md` reflects that no
separate `/read-plan`/`/explain-plan` pass happened) rather than as a normally-authored plan.

## Goal

`retire-planner-mac-phi-vm-split.md` (landed `main` `bc4ea6e`, same day) reframed *why* a VM
gets Executor role — GPU/high-throughput capacity the Mac lacks, not PHI/compliance — but
deliberately left the Executor/Planner **authority** split untouched: "Executor-mode bullets
(fetch-before-survey, fleet classes, deviation classification) stay — those are
compute/coordination concerns, not PHI ones." This plan retires that split entirely.

Both the Mac and Phil's Claude-Code VMs (`phil-sllm-01`) now run under the same Claude
subscription with identical capability — the asymmetry that justified a "planner authors,
executor defers to the planner for anything beyond the plan" split is gone. Per Phil
(2026-08-24): **the split between writing and QAing code is gone entirely** for any
Claude-Code-capable machine. Concretely, that collapses the entire `docs/vm-status/<date>-<sha>.md`
render/readback mechanism (`/vm-handoff`, its Deviation workflow, the tiered sign-off gate, and
the canonical spec that designs how many of these round-trips a plan needs) — there's no more
asymmetry left for that machinery to bridge.

**What survives, and why:** the *only* real split left is **hardware presence** — GPU training,
embedding generation, and high-throughput batch need specific hardware, and a box running that
kind of job usually has **no Claude Code running on it at all** (a bare compute box driven by a
script, not interactively). That's not an authority fact, it's a "no agent is present to decide
anything" fact — true between two VMs just as much as between the Mac and a VM. For that case:
a **standalone runner script** (already an existing `claude_ops.md` concept — env setup + the
run, one command) gets copy-pasted onto the box, and it writes its output to the **shared bucket
mount** (`su-vista-uscentral1`, now working on the Mac — see the Mac-side mount work landed
earlier today) instead of into a rendered doc. Any Claude-Code session reads the results
straight off the mount. No render step, no doc, no sign-off ceremony.

**What does NOT change:** rad-eval's `dispatcher.py` `require_vertex_phi_env()` gate (untouched
by the prior plan and untouched by this one — a separate BAA/PHI mechanism); destructive-action
confirmation, PHI gates, and "ask when architecturally significant" (Communication Standards) —
none of those were specific to the Mac/VM split; they apply identically to every session,
before and after.

## Approach

### Phase 1 — `claude_ops.md`

- **Machine-Aware Operating Mode**: rewritten. No more Executor/Planner role split for
  Claude-Code-capable machines — full parity (plan, implement, verify, commit, revise inline on
  a wrong assumption). The only split named is hardware presence, with the standalone-script +
  mount pattern as its mechanism.
- **"Fetch before you survey"**: reframed symmetrically — any machine's session can be the one
  whose pushes another session is stale relative to; dropped the "planner Mac pushes, executor
  VM consumes" asymmetric framing.
- **Planning Workflow → "For VM-handoff-bound plans"**: removed (pointed at the now-deleted
  canonical spec); replaced with a one-line pointer to name a standalone script + its Expected/
  Stop criteria in the plan's Verification section, same as any other deliverable.
- **Plan Document Structure template**: `## Verification & VM handoff` → `## Verification`,
  substantially shortened — dropped executor-class/readback-machine fields, the Handoff-phasing
  sub-block, and the pointer to the deleted canonical spec; kept Expected/Stop/Anticipated-forks
  (still real verification discipline) plus a short standalone-script clause for the
  hardware-presence case. `## Landing & cleanup` template's "VM gate green" → "any GPU/
  high-throughput step's standalone script actually run and checked."
- **"VM-status docs are for smoke tests only"** section: replaced with "Standalone scripts for
  GPU / high-throughput work — read results from the mount, not a doc."
- **Pre-Commit Review section**: dropped the `/vm-handoff` bullet entirely; stripped the
  `/vm-handoff`-routing clauses from the `/review-implementation` and `/review-tests` bullets.
- **Verification Approaches** section: dropped the `/vm-handoff` pointer, reframed around the
  standalone-script Expected/Stop discipline.

### Phase 2 — `VISTA/code/CLAUDE.md` + `CLAUDE.vm.md` (direct edits, not a git repo)

- `CLAUDE.md`: "machine-aware executor/planner pattern" → "GPU/high-throughput capacity routing
  (any Claude-Code machine otherwise has full parity)".
- `CLAUDE.vm.md`: same phrase fix, plus the "Stay in Executor lane" bullet rewritten to "Full
  parity with the Mac" — drops "don't broad-plan or major-rewrite without user confirmation...
  planning happens on the Mac." Same caveat as the prior plan: no automatic path onto the actual
  VM — Phil copies the file over by hand.

### Phase 3 — Retire `commands/vm-handoff.md` and `references/verification-and-handoff-design.md`

Both files **deleted outright** (534 + 301 lines). Full history preserved on
`legacy/vm-handoff-doc-system-2026-08` (branched from `main` before deletion, pushed), mirroring
how the prior plan preserved `vm-shell-guard.sh`. `docs/plans/verification-and-handoff-design-agent.md`
(the plan that built this capability) gets a superseded banner pointing here.

### Phase 4 — `commands/review-plan.md`

- Description frontmatter: dropped "verification/handoff-design (VM-bound plans)" from the
  always-on-lenses list.
- Removed **Phase 2c** entirely ("Verification & handoff-design pass (VM-handoff-bound plans
  only)") — the whole tiered-complexity-classifier sub-review built around the canonical spec.
- Removed the **"Verification & handoff design"** always-on lens from the Codex/Claude reviewer
  prompt (required-read #4, the lens itself) and from the output template ("Verification &
  Handoff Design" section).
- **Implementability & handoff-readiness** lens: reworded the success-criterion clause to point
  at the plan's (now-renamed) *Verification* section generically, not "the VM-bound lens above."
- **Verification Gaps** output-template bullet: reworded from "VM-side verification recipes" to
  "verification recipes for any step run against real data or on GPU/high-throughput hardware."

### Phase 5 — `commands/review-implementation.md` and `commands/review-tests.md`

Both: removed the "Exception — route through `/vm-handoff` first" block entirely (both the
conditional-routing prose and the `/vm-handoff`-specific offer text); both now hand off straight
to `/commit-review` unconditionally. Both description frontmatters: dropped the
"only when the repo uses a planner-Mac/executor-VM split... route to /vm-handoff" clause.

### Phase 6 — `commands/land.md`

- Machine-posture paragraph: "fine on the planner Mac" → "fine on any machine"; "an unrun VM
  gate" → "an unrun GPU/high-throughput step."
- "Green-gate freshness" bullet: "the branch's VM gate" → "the branch's tests/verification"
  (the freshness concept is general CI hygiene, not VM-specific).
- "VM gate outstanding?" bullet → "GPU / high-throughput step outstanding?" — checks for an
  un-run standalone script instead of an un-read-back vm-status doc.

### Phase 7 — Sweep for residual references

Repo-wide grep for `vm-handoff`, `verification-and-handoff-design`, `vm-status`, stale
`planner`/`executor` framing across `commands/*.md`, `README.md`, `backlog.md`,
`commands/wrapup.md`'s resume-block template (dropped its `docs/vm-status/*.md` example field
and the "same locator format as `/vm-handoff`" cross-reference). Left untouched: historical
mentions under existing superseded banners (`docs/plans/vm-shell-guard-hook.md`), and
`personal/`-tree-is-Mac-only mentions in `wrapup.md`/`land.md`/`phi-vet.md` (a filesystem fact
about a git-ignored directory, not an authority split).

## Files to Modify

**research-skills**
- `claude_ops.md` — Phase 1
- `commands/vm-handoff.md` — deleted (Phase 3)
- `references/verification-and-handoff-design.md` — deleted (Phase 3)
- `docs/plans/verification-and-handoff-design-agent.md` — superseded banner (Phase 3)
- `commands/review-plan.md` — Phase 4
- `commands/review-implementation.md` — Phase 5
- `commands/review-tests.md` — Phase 5
- `commands/land.md` — Phase 6
- `README.md`, `backlog.md`, `commands/wrapup.md` — Phase 7

**VISTA-specific (not research-skills)**
- `VISTA/code/CLAUDE.md`, `VISTA/code/CLAUDE.vm.md` — Phase 2 (not git repos; `CLAUDE.vm.md`
  needs hand-copying to the actual VM, same as the prior plan)

## Open Questions

All resolved during drafting (see conversation): class-3 renamed by removing the class taxonomy
entirely rather than relabeling it (the whole Deviation workflow section is gone, not just
reworded); no "supersede with a fresh doc" practice survives since there's no doc type left to
supersede; `/review-implementation` / `/review-tests`'s prior "Defensible Deviations" language
is untouched (confirmed unrelated — that's a Codex-review-time classification of already-written
code vs. the plan, not this VM/Mac execution-time mechanism).

## Verification

Docs-only change, verified structurally:
- Repo-wide grep for `vm-handoff`, `verification-and-handoff-design`, `vm-status` returns no
  hits outside historical/superseded content and this plan's own description of what changed.
- Repo-wide grep for `planner`/`executor` returns no hits describing an authority split for
  Claude-Code-capable machines (hardware-capacity mentions and Mac-only-filesystem-fact mentions
  are fine and expected).
- `commands/vm-handoff.md` and `references/verification-and-handoff-design.md` are gone from
  `main`'s working tree but resolvable via `legacy/vm-handoff-doc-system-2026-08`.
- Read the full rewritten `claude_ops.md` Machine-Aware Operating Mode + Plan Document Structure
  sections end-to-end and confirm they read as one coherent policy, not patched fragments.

## Landing & cleanup

- **Branch**: `feat/executor-mac-parity-remove-deviation-handback` (this worktree).
- **Landing gate**: Phil's explicit read + approval (same class of stakes as the prior PHI-
  posture plan — this is core operating discipline inherited by every VISTA repo). No VM gate.
- **Merge sequence**: single-branch — land at the end, prune branch + worktree.
- **Cleanup on land**: mark this plan `Status: Completed`; add its row to `docs/plans/README.md`;
  remind to hand-copy `CLAUDE.vm.md`'s new content onto the actual VM.
