# research-skills — backlog

Known issues and deferred work for the skill repo itself. Per the same pointer-style discipline `/wrapup` enforces on project repos: short entries, link out to substance.

## Runtime cache vs canonical drift

**Resolved on this Mac (`BDS-H2DLP0QFM4`), verified 2026-08-24**: `ls -la ~/.claude/` confirms `commands -> /Users/philadamson/Documents/Stanford/VISTA/code/research-skills/commands` is a proper symlink (Resolution A from the original filing). Not re-checked on Phil's other machines (VMs) — if this recurs elsewhere, the options below still apply.

The intended setup is a symlink: `~/.claude/commands → research-skills/commands` (per README "One-shot setup on a fresh VM"). Originally filed 2026-05-12 after finding `~/.claude/commands/` was instead a *separate git repo* with its own history, drifted from canonical.

**If it recurs**: (A) convert to a symlink per the README setup, reconciling drift first; (B) keep two repos but automate sync (a pre-session hook rsyncing canonical → runtime); (C) document the manual `cp`-and-commit ritual in `wrapup` Step 7 (already does — "sync direction matters" + the `cp` recipe).

## rad-eval has no per-repo plan-review-checklist

Three repos have a `.claude/references/plan-review-checklist.md` (vista_bench, vista-eval,
vista-ct); rad-eval does not. Until one is seeded, the generic archetype menu (and, once it
lands, the canonical `references/verification-and-handoff-design.md` spec) carries more weight
for rad-eval plan reviews than for the others. Worth a small followup plan to author a
rad-eval checklist grounded in its extraction / seed-gate / equivalence verification patterns.

Filed 2026-07-08 while scoping the verification-and-handoff-design agent (moved out of that
plan's open questions so the plan doesn't carry a stale cross-repo reference).

## VM-side plan/HTML viewing has no bridge to the Mac's browser

Once execution moves VM-side more (per the PHI-posture retirement, see below), `/explain-plan`
and `/read-plan` output authored on the VM has no way to reach a browser — the VM is typically
headless. Proposed direction (Phase 7 of
[`retire-planner-mac-phi-vm-split.md`](retire-planner-mac-phi-vm-split.md#phase-7)): write
generated HTML to a bucket-mounted scratch path instead of requiring a commit+push+pull
round-trip. Needs its own follow-up plan once that plan's Phase 0 (Mac-side bucket mount) is
actually working — not scoped yet.

Filed 2026-08-24, surfaced via `/explain-plan` feedback on the PHI-posture retirement plan.

## (Future entries — add as encountered)
