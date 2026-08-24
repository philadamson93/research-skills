Reference: claude_ops.md

# Implementation Feedback: Retire the planner-Mac / PHI-VM split (Phases 1, 3, 4)

## Verdict

Revise before commit. Phase 1 and Phase 3 are implemented cleanly, and the requested Phase 4 line-level edits are present, but `commands/vm-handoff.md` still has nearby stale planner-Mac wording that says the Mac has "no runtime" / "can't run" authored configs and scripts.

## Plan Coverage

| Phase / bullet | Status | Evidence: path:line | Notes |
|---|---|---|---|
| Phase 1 — Environment Constraints rewrite | Done | claude_ops.md:23-27 | Replaces the blanket execution ban with "Code execution is allowed on this machine" and keeps GPU/high-throughput routing as capacity, not compliance. |
| Phase 1 — Delete "Hard Boundary: Never Open a Remote Shell Into a VM (PHI)" | Done | claude_ops.md:21-31 | The section is gone; `## Environment Constraints` now flows directly into `## Machine-Aware Operating Mode`. |
| Phase 1 — Machine-Aware Operating Mode reframe | Done | claude_ops.md:33-48 | Split is now framed as GPU/high-throughput compute the Mac lacks. Executor coordination bullets remain. |
| Phase 1 — Planner-mode bullet | Done | claude_ops.md:43-45 | The old "Do not run code or query data" line is replaced with "May run light code / query BQ / inspect mounted data directly..." while routing GPU/high-throughput work to the fleet. |
| Phase 1 — Plan Document Structure framing | Done | claude_ops.md:150-153 | The VM handoff need is now "this step needs compute the Mac doesn't have (GPU, high-throughput batch)," not "execution happens on the VM." |
| Phase 1 — VM-status docs framing | Done | claude_ops.md:200-202 | The vm-status section no longer claims eval/results handoffs exist because the Mac cannot reach data; it frames vm-status docs as smoke-test / verification handoffs. |
| Phase 1 — Pre-Commit Review subagent rule | Done | claude_ops.md:335 | Replaces "All spawned subagents must be instructed not to run code" with "Spawned subagents may run code on this machine," gated by `phi-vet`. |
| Phase 1 — Verification Approaches opening | Done | claude_ops.md:346-350 | Replaces "Since code cannot run on this machine" with the compute-capacity framing. |
| Phase 3 — Delete active hook | Done | git diff --name-status; hooks/vm-shell-guard.sh | `git diff --name-status` reports `D hooks/vm-shell-guard.sh`, and the file no longer exists in the worktree. |
| Phase 3 — Remove hook table row | Done | hooks/README.md:7-11 | Table now lists only `phi-vet-gate.sh`; no `vm-shell-guard.sh` row remains. |
| Phase 3 — Remove hook install section | Done | hooks/README.md:15-91, hooks/README.md:93 | The `phi-vet-gate.sh` section now flows directly to Machine gate; the prior `vm-shell-guard.sh — installation` section is removed. |
| Phase 3 — Tighten PHI-free framing | Done | hooks/README.md:95, hooks/README.md:120 | PHI-free is described as a narrow explicit exemption, not the default state of a planner Mac. |
| Phase 3 — Superseded banner | Done | docs/plans/vm-shell-guard-hook.md:5-7 | Banner says `hooks/vm-shell-guard.sh` was deleted by this plan on 2026-08-24. |
| Phase 4 — `commands/vm-handoff.md` principle wording | Partial | commands/vm-handoff.md:10-12 | The specified before/after line was updated, but nearby stale wording remains; see Missing Pieces. |
| Phase 4 — `commands/phi-vet.md` Step 0 wording | Done | commands/phi-vet.md:11-13 | Reframes PHI-free as a narrow allowlist exemption and states a Mac is not PHI-free merely because it is a laptop. |
| Phase 4 — `commands/review-tests.md:112` | Done | commands/review-tests.md:108-113 | "BigQuery, GPU, PHI-mounted paths" is narrowed to "compute unavailable in this checkout (GPU, high-throughput batch)." |
| Phase 4 — `commands/review-tests.md:265` | Done | commands/review-tests.md:259-265 | "infra-blocked gaps (BigQuery, GPU, PHI mounts)" is narrowed to "compute-blocked gaps (GPU, high-throughput batch)." |
| Phase 4 — `commands/land.md:21` | Done | commands/land.md:19-21 | Landing now permits git operations on the planner Mac and limits the no-run warning to tests/linters/python needing GPU or high-throughput compute. |

## Critical Drift

- None found.

## Missing Pieces

- Phase 4 stale `commands/vm-handoff.md` wording | `commands/vm-handoff.md` workflow and template prose | Phase 4's plan says the old wording `"planner Mac authors plans, configs, and scripts but cannot run code (no runtime, GPU, data, or credentials)"` should become capacity-based because "data, or credentials" are reachable from the Mac now. The implementation fixed the opening sentence at `commands/vm-handoff.md:10-12`, but the same file still says `"...implement (author configs/scripts — can't run them on the Mac)..."` at `commands/vm-handoff.md:36`, `"Planner (the Mac, no runtime)"` at `commands/vm-handoff.md:61`, and `"authored on the planner Mac (no runtime)"` at `commands/vm-handoff.md:212`. Those remnants preserve the old blanket no-runtime/no-run posture. | Suggested code change: reframe those three spots around "not GPU/high-throughput-capacity validated here" or "not yet executed on the target executor class," rather than saying the Mac cannot run the code at all.

## Contract Violations

- No active `claude_ops.md` or `hooks/README.md` link to deleted `hooks/vm-shell-guard.sh` remains. `docs/plans/vm-shell-guard-hook.md` still contains historical references to the deleted script after the superseded banner; that is not an active install path, but readers will hit dead file links if they follow old body links without noticing the banner.

## Test Gaps

- N/A. Docs/hooks-only audit; I ran `git diff --check`, which reported no whitespace errors.

## Defensible Deviations

- `docs/plans/vm-shell-guard-hook.md` keeps the original design text and old `hooks/vm-shell-guard.sh` references under a superseded banner at `docs/plans/vm-shell-guard-hook.md:6`. That diverges from a full rewrite, but it appears intentional and reasonable for a historical completed plan. Author should confirm that preserving dead-link historical body text is acceptable.
- `commands/vm-handoff.md:62` still says the Claude-Code CPU executor has "data + credentials." That can remain defensible as a concrete executor capability statement, not the old claim that the Mac categorically lacks data and credentials.

## Suggested Code Edits

- `commands/vm-handoff.md:36`: change `author configs/scripts — can't run them on the Mac` to a capacity/target framing, e.g. `author configs/scripts — GPU/high-throughput runs still need the executor fleet`.
- `commands/vm-handoff.md:61`: change `Planner (the Mac, no runtime)` to something like `Planner (the Mac; no GPU/high-throughput capacity)`.
- `commands/vm-handoff.md:212`: change `authored on the planner Mac (no runtime). Everything below has never executed` to something like `authored on the planner Mac. Everything below has not yet executed on the target executor class`.

## Questions For The Author

- Should `docs/plans/vm-shell-guard-hook.md` keep its historical dead links to `hooks/vm-shell-guard.sh` under the superseded banner, or should those body links be neutralized as plain historical text?

## Audit Trail

- claude_ops.md
- commands/land.md
- commands/phi-vet.md
- commands/review-tests.md
- commands/vm-handoff.md
- docs/plans/README.md
- docs/plans/retire-planner-mac-phi-vm-split.md
- docs/plans/vm-shell-guard-hook.md
- hooks/README.md
- hooks/vm-shell-guard.sh
