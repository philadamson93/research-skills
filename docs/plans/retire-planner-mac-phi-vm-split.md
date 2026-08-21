Reference: claude_ops.md

# Retire the planner-Mac / PHI-VM split as the VISTA default

**Status: Draft** (2026-08-21)
**Prior state preserved on `legacy/planner-mac-phi-vm-split-2026-08`** (branched from `main` `30cf092`, before any of this plan's edits) — the full old posture (Hard Boundary section, vm-shell-guard.sh, its install docs) lives there if anyone needs the original rationale later.

## Goal

Phil now has Claude Code for Education through Stanford, which is high-risk-data compliant,
and it covers Claude sessions on his Mac and his project VMs alike (same account on both).
Codex is also now PHI-compliant and logged in on both VMs (basic plan, not Pro). That retires
the premise the current default rests on — that a local/planner Mac session lives *outside*
the PHI boundary and a VM session lives *inside* it. Both machines are now inside it.

This plan retires the resulting defaults in `research-skills` (which govern VISTA and rad-eval
alike — see below) and the VISTA-specific files layered on top:

- **Code execution is allowed on the Mac**, gated by the same phi-vet discipline that already
  governs commits — not blocked outright.
- **The hard "never SSH into a VM" boundary is retired** (confirmed with Phil) — its rationale
  (a Mac session's transcript lives outside the boundary) no longer holds.
- **Git commits stop being the mechanism for moving data-adjacent artifacts between machines.**
  Phil wants to mount the `su-vista-uscentral1` GCS bucket on his Mac directly, so editing/
  inspecting VISTA data no longer requires a round-trip through GitHub just to sync machines he
  already controls. GitHub still needs PHI scrubbing — phi-vet's job doesn't change, only which
  machines it's mechanically active on.
- **What does NOT change**: heavy compute (GPU training, high-throughput batch) still runs on
  the VM fleet, for capacity reasons, not compliance ones. rad-eval's own `require_vertex_phi_env()`
  gate in `dispatcher.py` (Chaudhari Lab's separate BAA arrangement) is untouched — confirmed
  with Phil to leave as-is; only its `docs/machines.md` wording gets a consistency note.

## Background — grounding facts

- **GCP project**: `som-nero-plevriti-deidbdf` (confirmed — "Stanford Oncology de-identified
  BigQuery domain" per `vista-pm/docs/onboarding/glossary.md`).
- **`research-skills` is one GitHub repo cloned twice**, not a shared symlink: once at
  `VISTA/code/research-skills`, once at `RadAWS/code/research-skills`. Both point at
  `github.com:philadamson93/research-skills.git` and are currently identical at `30cf092`
  (confirmed — same HEAD, same untracked scratch files). Editing `claude_ops.md` / `hooks/`
  in one clone governs **both** VISTA and rad-eval once the other clone runs `git pull`, but a
  push here does not silently reach the other clone — that pull is a manual step.
- **One real exception to that sync**: `hooks/lib/phi-free-machines.local` is git-ignored by
  design (keeps real machine names out of the public repo), so it exists independently in each
  physical clone and has to be hand-edited in both places. This plan hits it twice — see Phase 2.
- **Current allowlist state** (checked directly): this Mac (`BDS-H2DLP0QFM4`) is *on* the
  PHI-free allowlist today, with the comment "local planner MacBook (no PHI, no BQ creds)" —
  the exact line this plan makes false.
- **A real pre-existing gap, unrelated to the new posture but worth fixing in the same pass**:
  `~/.claude/settings.json` currently wires only `vm-shell-guard.sh` into `PreToolUse`/`Bash`.
  `phi-vet-gate.sh` was never actually installed as a hook — the PHI commit gate has been
  running on skill discipline alone, not mechanically enforced. That matters more, not less,
  once the Mac drops off the PHI-free allowlist.
- **Confirmed with Phil** (two `AskUserQuestion` rounds, one interrupted and re-asked clean):
  1. Retire the hard SSH-into-VM boundary entirely — not a soft downgrade, not left as-is.
  2. Leave rad-eval's `dispatcher.py` Vertex-only gate untouched; only its `docs/machines.md`
     posture wording gets updated for consistency.

## Approach

### Phase 1 — `claude_ops.md` rewrite (research-skills, shared)

- **Environment Constraints**: the current "no code execution on this machine" default bundles
  two separate reasons — no PHI clearance, and no runtime/GPU. Split them. PHI clearance is
  retired as a reason. Runtime/GPU capacity is not: rewrite so code execution is allowed on any
  machine under Phil's Claude Code for Education account, subject to the same phi-vet discipline
  as commits, while GPU training and high-throughput batch still route to the VM fleet because
  the Mac doesn't have that hardware — a capacity statement, not a compliance one.
- **"Hard Boundary: Never Open a Remote Shell Into a VM (PHI)"**: delete the section outright.
  Its rationale no longer holds now that both machines are inside the same compliance boundary.
  The full text + its reasoning survive on `legacy/planner-mac-phi-vm-split-2026-08` for anyone
  who needs the history.
- **Machine-Aware Operating Mode**: reframe the *reason* a repo declares this split — a VM
  gets Executor role because it holds GPU/throughput compute the Mac lacks, not because it
  holds PHI the Mac can't touch. Executor-mode bullets (fetch-before-survey, fleet classes,
  deviation classification) stay — those are compute/coordination concerns, not PHI ones.
  Planner-mode's "Do not run code or query data — credentials and data paths usually aren't
  here" line is now false for a Mac with the bucket mounted and `gcloud auth
  application-default login` run (already documented, already how BQ access works today per
  `vista-pm/docs/onboarding/bigquery.md`) — rewrite to something like "may run light code /
  query BQ / inspect mounted data directly; GPU and high-throughput work still routes to the
  executor fleet."
- **Plan Document Structure → "Verification & VM handoff"**: same mechanics (Expected/Stop,
  executor classes, phasing), but the framing sentence for *why* a plan needs this section
  shifts from "the Mac can't reach the data" to "this step needs compute the Mac doesn't have."
- **"VM-status docs are for smoke tests only"**: same idea, same one-line framing fix.

### Phase 2 — machine-gate registry (git-ignored — edit in BOTH physical clones)

- Remove the `BDS-H2DLP0QFM4` line from `hooks/lib/phi-free-machines.local` in **both**
  `VISTA/code/research-skills` and `RadAWS/code/research-skills`. Per the existing fail-closed
  design this alone flips `phi-vet-gate.sh` to active and `vm-shell-guard.sh` to inert on this
  Mac — the one mechanism already does the right thing once the registration is corrected.
- Wire `hooks/phi-vet-gate.sh` into `~/.claude/settings.json`'s existing `PreToolUse`/`Bash`
  matcher array, alongside (for now) `vm-shell-guard.sh` — Phase 3 removes the latter.
- This phase is what actually gives the new posture teeth: without it, dropping the Mac from
  the allowlist is inert because nothing calls `phi-vet-gate.sh` yet.

### Phase 3 — retire `vm-shell-guard.sh`

- Delete `hooks/vm-shell-guard.sh` from the active hook set (its logic + full history remain
  on the legacy branch and in git history — no need for a second copy under an `archive/` dir;
  flagged as an Open Question below in case Phil wants it kept visible instead).
- Remove its entry from `~/.claude/settings.json`.
- `hooks/README.md`: drop the vm-shell-guard.sh table row and its whole install section.
  Tighten the phi-vet-gate.sh section's language — it currently frames "planner machines have
  no PHI" as the stable default; rewrite so PHI-free is an explicit, narrow exemption (a
  machine with no data mount and no BQ credentials at all), not something a VISTA/rad-eval Mac
  gets by default anymore.

### Phase 4 — skill wording (research-skills, shared)

- `commands/vm-handoff.md`: "planner Mac authors plans, configs, and scripts but cannot run
  code (no runtime, GPU, data, or credentials)" → drop "data, or credentials" (both reachable
  from the Mac now); keep "no GPU / no throughput capacity" as the real reason a handoff is
  still sometimes needed.
- `commands/phi-vet.md`: Step 0's mechanics don't change (it already just reads the allowlist),
  but its prose ("planner-only machines... have nothing to scan") reads as "Macs are PHI-free
  by default" — tighten so it's clear that's now the exception, not the default.
- `commands/review-tests.md:112,265`: "Gaps that fundamentally require infra unavailable in
  this checkout (BigQuery, GPU, PHI-mounted paths)" — found while grounding this plan. GPU is
  still accurate; BigQuery and PHI-mounted paths are no longer categorically unavailable on the
  Mac once ADC + the bucket mount are in place. Narrow this to GPU-only, or reword to "compute
  unavailable here" so it doesn't quietly relitigate the retired split.
- `commands/review-implementation.md` / `commands/review-tests.md` otherwise only say "this
  work runs on the VM next" without asserting a PHI-based reason — no change needed beyond the
  line above.

### Phase 5 — VISTA-specific files

- `VISTA/code/CLAUDE.md`: the "Operating standards" paragraph names "the no-execution default"
  as one of the things `claude_ops.md` establishes — update that phrase now that execution is
  no longer the shared default framing.
- `VISTA/code/CLAUDE.vm.md`: this is the VM-side counterpart Phil places as `CLAUDE.md` on the
  VM half of the `code/` tree. Its "Counterpart note" ("the same workspace exists on my local
  Mac... planner-only, no code execution") and its "Machine posture: this is the Executor VM
  (execution IS allowed)" heading both assume the old split — rewrite both. **This file has no
  automatic path onto the actual VM** — after editing it here, Phil copies it over by hand (no
  SSH path exists for me to push it, and retiring the SSH boundary doesn't add one for this
  session to use unprompted).
- `vista-pm/README.md:44`: extend the existing "On a VM, mount the bucket with `gcsfuse`" row
  to also cover the Mac — same bucket (`su-vista-uscentral1`), same command shape as the VM's
  (`gcsfuse --implicit-dirs su-vista-uscentral1 <mount-point>`, per the pattern already in
  `vista-eval/src/vistaeval/io/gcs.py`). BigQuery access from the Mac already works today via
  `gcloud auth application-default login` (documented in `docs/onboarding/bigquery.md`) — the
  bucket mount is the only genuinely new piece, since OMOP/clinical text lives in BigQuery, not
  the bucket. Actually running the mount on Phil's Mac is a follow-on step, not part of this
  branch (see Open Questions).
- `crc-extraction-agent/docs/plans/2026-08-10-crc-vertex-egress-docker-profile.md` — flag only.
  Its "Machine posture" section (~lines 301-306) is written against the old split. Out of scope
  to rewrite here (it's an already-approved plan with its own history); note it as a follow-up
  for whoever next picks that plan back up.

## Files to Modify

**research-skills (shared — edit once in `VISTA/code/research-skills`, then `git pull` in
`RadAWS/code/research-skills` to sync)**
- `claude_ops.md` — Phase 1 (Environment Constraints, Hard Boundary removal, Machine-Aware
  Operating Mode reframe, two smaller framing fixes)
- `hooks/vm-shell-guard.sh` — delete (Phase 3)
- `hooks/README.md` — remove vm-shell-guard.sh section, tighten phi-vet-gate.sh prose (Phase 3)
- `commands/vm-handoff.md` — drop "data, or credentials" from the planner-Mac description (Phase 4)
- `commands/phi-vet.md` — tighten Step 0 prose (Phase 4)
- `commands/review-tests.md` — narrow the infra-unavailable list at lines 112 and 265 (Phase 4)
- `docs/plans/README.md` — add this plan's row once landed

**Git-ignored, per physical clone (edit in both)**
- `VISTA/code/research-skills/hooks/lib/phi-free-machines.local` — remove `BDS-H2DLP0QFM4` (Phase 2)
- `RadAWS/code/research-skills/hooks/lib/phi-free-machines.local` — same edit (Phase 2)

**Not in git — machine-local settings**
- `~/.claude/settings.json` — add `phi-vet-gate.sh` to `PreToolUse`/`Bash`, remove
  `vm-shell-guard.sh` once Phase 3 lands (Phase 2 + 3)

**VISTA-specific (separate repos, not research-skills)**
- `VISTA/code/CLAUDE.md` — one-phrase fix (Phase 5)
- `VISTA/code/CLAUDE.vm.md` — rewrite Counterpart note + Machine posture heading (Phase 5);
  manual copy to the actual VM afterward
- `vista-pm/README.md` — add the Mac-side mount row (Phase 5)

**rad-eval-specific (its own clone/repo, not shared research-skills)**
- `RadAWS/code/rad-eval/docs/machines.md` — add a consistency note explaining rad-eval keeps
  its own stricter Vertex-only posture independent of this change (confirmed with Phil — no
  change to `require_vertex_phi_env()` itself)

**Flagged, not edited in this plan**
- `crc-extraction-agent/docs/plans/2026-08-10-crc-vertex-egress-docker-profile.md` — Machine
  posture section is stale; leave for that plan's own owner
- `contrastive-3d-onc/docs/claude_ops.md`, `MerlinOnc/docs/claude_ops.md`,
  `tte-pretraining/docs/claude_ops.md` — pre-existing stale, non-symlinked copies (missing the
  Machine-Aware Operating Mode section and the Hard Boundary section entirely, predating both).
  Unrelated root cause, but this change makes the drift worse either way — recommend
  re-pointing all three at the canonical file via symlink like every other repo. See Open
  Questions for whether that's in-scope for this branch.

## Open Questions

1. **Delete `vm-shell-guard.sh` outright, or archive it under `hooks/archive/`?** Recommend
   outright deletion — the legacy branch and git history already preserve it, and a live
   `archive/` directory invites someone re-wiring it "just in case" later without re-deriving
   whether the reasoning still applies.
2. **Fold the three stale `claude_ops.md` re-symlinks into this branch, or handle as a separate
   cleanup?** They're not caused by this change, but recommend doing it here since it's
   mechanical (delete the stale file, add the same symlink every other repo uses) and this
   branch is already touching machine-posture docs.
3. **`dicom-annotations`' PHI-copy sync workflow** (per memory: Phil hand-syncs a separate PHI
   copy of `explore_ko_pr.ipynb` by copy-pasting changed cells between environments) — this
   workaround exists because of exactly the kind of Mac/PHI separation this plan retires. Worth
   a dedicated look at whether it can be replaced by the same Mac-side mount, but that repo
   wasn't in scope for this pass (it sits outside `VISTA/code/`) — flagging as a likely-real
   follow-on win, not resolving it here.
4. **Does "leave rad-eval's dispatcher gate as-is" also mean `rad_eval_mac_author_only_no_pytest.md`
   (Mac = author only, VM = authoritative pytest gate) stays unchanged?** That memory doesn't
   cite PHI as its reason (more likely environment/GPU parity for the eval suite) — probably
   untouched by this plan regardless, but flagging since it's adjacent and worth a conscious
   answer rather than a silent assumption either way.
5. **Mac-side bucket mount execution** — this plan documents the recipe (Phase 5's
   `vista-pm/README.md` edit) but doesn't run it. Confirm: is actually mounting
   `su-vista-uscentral1` on the Mac a follow-up Phil runs himself, or something to hand back to
   this session as a next step once this plan lands?

## Verification & VM handoff

No GPU/throughput work here — this is a docs + hooks + settings change, verified structurally,
not via a VM handoff.

- **What runs, where** (all on the Mac, Claude-Code CPU class, no VM step):
  - `jq . ~/.claude/settings.json` — must still parse as valid JSON after the hook-wiring edit.
  - `hooks/lib/is-phi-free-machine.sh --explain` — must report `ASSUME_PHI` (not `PHI_FREE`)
    on this Mac after Phase 2's allowlist edit, in **both** physical clones.
  - Re-run the block/allow test matrix from `hooks/README.md`'s (soon-removed) vm-shell-guard
    section is moot post-deletion — instead, confirm the hook file is gone and no
    `settings.json` entry references it.
  - A dry-run test: stage a trivial change in a scratch/throwaway medical-data-flavored repo
    (or a temp dir matching the gate's repo-detection patterns) and confirm `git commit` is now
    mechanically blocked pending `/phi-vet`, proving Phase 2's wiring actually took effect
    (not just "the skill would have caught it").
  - Grep both research-skills clones + the VISTA and rad-eval trees for `vm-shell-guard` and
    `phi-free-machines` after the edit — confirm no other doc references the retired hook
    without pointing at its replacement/history, and that the RadAWS clone's copy actually got
    the `git pull` + local allowlist edit (Phase 2's two-clones gotcha).
- **Expected**: settings.json valid; Mac reports `ASSUME_PHI`; phi-vet-gate.sh mechanically
  blocks the test commit; no dangling references to the deleted hook.
- **Stop**: if `is-phi-free-machine.sh` still reports `PHI_FREE` after the allowlist edit on
  either clone, STOP — the edit didn't take (wrong file, wrong machine-name match) — do not
  proceed to depend on phi-vet being active until this is fixed.

Given the compliance stakes, recommend `/review-plan` on this document before implementing —
this is exactly the kind of "larger skill rewrite" `claude_ops.md`'s own Git Practices section
says should get review before landing.

## Landing & cleanup

- **Branch**: currently `worktree-retire-planner-vm-phi-split` (this session's `EnterWorktree`
  branch) — rename to `feat/retire-planner-mac-phi-vm-split` before landing, matching the
  repo's naming convention.
- **Landing gate**: Phil's explicit read + approval, given the compliance stakes — ideally
  after `/review-plan`. No VM gate needed (nothing here runs on the executor fleet).
  `phi-vet` itself is inert on this Mac until Phase 2 lands, so this branch's own commits still
  go through the *old* posture on the way in — expected, not a bug.
- **Merge sequence**: land to `main` in `VISTA/code/research-skills`, push, then
  `git -C RadAWS/code/research-skills pull --ff-only` to sync the second clone's tracked files.
  The git-ignored `phi-free-machines.local` edit in the RadAWS clone (Phase 2) has to be
  redone by hand there — a pull won't carry it.
- **Cleanup on land**: prune this worktree + branch; add this plan's row to
  `docs/plans/README.md`; mark this doc `Status: Completed`.
