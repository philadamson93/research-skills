Reference: claude_ops.md

# Retire the planner-Mac / PHI-VM split as the VISTA default

**Status: Draft** (2026-08-21, revised post `/review-plan`)
**Prior state preserved on `legacy/planner-mac-phi-vm-split-2026-08`** (branched from `main` `30cf092`, before any of this plan's edits) — the full old posture (Hard Boundary section, vm-shell-guard.sh, its install docs) lives there if anyone needs the original rationale later.
**Reviewed by**: fresh Claude Code subagent (`docs/plans/reviews/retire-planner-mac-phi-vm-split-feedback-claude.md`), verdict Revise — findings applied below; two genuine design forks it surfaced were re-confirmed with Phil.

## Goal

Phil now has Claude Code for Education through Stanford, which is high-risk-data compliant,
and it covers Claude sessions on his Mac and his project VMs alike (same account on both).
Codex is also now PHI-compliant and logged in on both VMs (basic plan, not Pro). That retires
the premise the current default rests on — that a local/planner Mac session lives *outside*
the PHI boundary and a VM session lives *inside* it. Both machines are now inside it.
(This premise is Phil's own representation — see Background's caveat and Open Questions.)

This plan retires the resulting defaults in `research-skills` (which govern VISTA and rad-eval
alike — see below) and the VISTA/rad-eval-specific files layered on top:

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
  with Phil to leave as-is. rad-eval's *separate* `docs/machines.md` PHI-posture registry
  **does** change (confirmed with Phil after `/review-plan` surfaced it — see Phase 6).
- **Resolved as of this revision**: direct Claude Code use is confirmed fine for
  `som-nero-plevriti-deidbdf` specifically — Phil confirmed it's high-risk, PHI-scrubbed data,
  not PHI, and that classification doesn't extend to any other GCP project. See Background's
  citation and Open Question 7.

## Background — grounding facts

- **GCP project**: `som-nero-plevriti-deidbdf` (confirmed — "Stanford Oncology de-identified
  BigQuery domain" per `vista-pm/docs/onboarding/glossary.md`, independently corroborated by
  rad-eval's `dispatcher.py` hard-coding the same project ID in its own BAA allowlist).
- **Compliance source, cited and resolved.** Phil pointed to Stanford IT's own page,
  <https://uit.stanford.edu/service/claude>: *"Claude Code is approved for low, moderate, and
  high-risk data. PHI use requires routing through the Stanford AI API Gateway."* This draws a
  line between "high-risk" classification and literal PHI — high-risk data is fine via direct
  Claude Code, PHI specifically needs the gateway. Phil confirmed (Open Question 7):
  `som-nero-plevriti-deidbdf` is PHI-scrubbed, not PHI — high-risk, non-PHI, *specifically
  inside the deid project* (not a blanket statement extending to any other GCP project). Direct
  Claude Code use is confirmed fine; no gateway needed for this plan's scope.
- **`RadAWS/code/research-skills` is a symlink to `VISTA/code/research-skills`, not a second
  clone** (`readlink`/`realpath` confirm it — corrects my first draft's "two clones kept in
  sync by git pull"). One physical checkout, one `claude_ops.md`, one `hooks/` directory, one
  `phi-free-machines.local` — every edit below is a single edit, visible to VISTA and rad-eval
  simultaneously, no `git pull` or second-location sync required anywhere.
- **Current allowlist state** (checked directly): this Mac (`BDS-H2DLP0QFM4`) is *on* the
  PHI-free allowlist today, with the comment "local planner MacBook (no PHI, no BQ creds)" —
  the exact line this plan makes false.
- **A real pre-existing gap, unrelated to the new posture but worth fixing in the same pass**:
  `~/.claude/settings.json` currently wires only `vm-shell-guard.sh` into `PreToolUse`/`Bash`.
  `phi-vet-gate.sh` was never actually installed as a hook — the PHI commit gate has been
  running on skill discipline alone, not mechanically enforced. That matters more, not less,
  once the Mac drops off the PHI-free allowlist.
- **rad-eval carries its own general PHI-posture registry**, `docs/machines.md` — separate from
  and broader than `dispatcher.py`'s narrow Vertex-only gate. It marks both `MacBook Pro (4)`
  and `BDS-H2DLP0QFM4` as `PHI present? No`, execution deferred to the VM — the same premise
  this plan retires, independently encoded. Found during `/review-plan`; confirmed with Phil to
  update it too (Phase 6).
- **Practical expectation, per Phil (explain-plan feedback round):** even though this plan
  retires the *compliance* reason execution was Mac-blocked, most of Phil's actual work will
  probably stay VM-side going forward regardless — that's where his `uv` environments already
  live, and code execution broadly is VM-side across his repos per the comments above. The Mac
  gains the *ability* to run light code / read data; it isn't expected to become the primary
  execution environment. This sharpens Phase 1's "capacity, not compliance" framing rather than
  changing it.
- **Confirmed with Phil** (across three rounds of clarification — one `AskUserQuestion` got
  interrupted and was re-asked clean; a later round followed `/review-plan`'s findings):
  1. Retire the hard SSH-into-VM boundary entirely — not a soft downgrade, not left as-is.
  2. Leave rad-eval's `dispatcher.py` Vertex-only gate untouched.
  3. Update rad-eval's `docs/machines.md` PHI-posture table to match VISTA's new posture.
  4. Keep the 3-repo stale-`claude_ops.md`-symlink cleanup bundled in this branch, despite the
     reviewer's YAGNI recommendation to split it into a separate mechanical PR — Phil's call.

## Approach

### Phase 0 — Mac-side bucket mount (test first — moved up per Phil's feedback)

Test this before anything else in this plan — it's the foundational capability the rest of the
plan assumes works. Recipe: `brew install --cask macfuse` (or gcsfuse's macOS install path) +
`gcsfuse --implicit-dirs su-vista-uscentral1 <mount-point>`, same bucket the VMs already mount,
mirroring the existing pattern in `vista-eval/src/vistaeval/io/gcs.py`. BigQuery access from the
Mac already works today via `gcloud auth application-default login` (`vista-pm/docs/onboarding/bigquery.md`)
— the bucket mount is the only new piece, since OMOP/clinical text lives in BigQuery, not the
bucket. The recipe itself is documented in Phase 5's `vista-pm/README.md` edit.

**Cost/practicality note (Phil asked about egress):** reads FROM a GCS bucket TO a client
*outside* Google Cloud (the Mac, over the internet) bill as network egress; writes/uploads
don't. A VM in the same region as the bucket reads for free; a Mac over home/office internet
pays per-GB egress past GCS's small free tier. Practical guidance: fine for light, exploratory
reads (browsing structure, small config/text files) from the Mac; keep bulk data pulls (large
parquets, imaging volumes) on the VM as today — a cost/bandwidth reason layered on top of the
compute-capacity reason already in Phase 1.

**Execution note:** macOS requires a one-time GUI approval for the `macfuse` kernel extension
(System Settings → Privacy & Security) that a headless/background session can't click through —
Phil runs the install step himself; a session can prepare and verify the commands.

**Unblocked (Open Question 7 resolved):** direct Claude Code use against this project's data is
confirmed fine — `som-nero-plevriti-deidbdf` is high-risk, not PHI. Cleared to actually run this
test, not just document it.

**Pre-flight, actually run this pass** (no fuse mount needed for this part):
- `gcloud auth application-default print-access-token` — succeeds; ADC already works on this Mac.
- `gcloud storage ls gs://su-vista-uscentral1/` — succeeds, lists 4 top-level prefixes
  (`chaudhari_lab/`, `plevritis_lab/`, `tmp/`, `vistabench/`).
- **Verified the bucket is actually in the approved project** (worth checking explicitly, not
  assuming): the CLI's *default* gcloud project on this Mac is `som-rit-phi-oncology-dev` — a
  different project, unrelated to this plan — but bucket access doesn't depend on the CLI
  default; resolving the bucket's project number (`261743353465`) via the GCS JSON API confirms
  it's `som-nero-plevriti-deidbdf` exactly, the project Phil approved. **Side note, not a
  blocker**: because the CLI default project is a different one, any future command that omits
  an explicit `--project` flag risks targeting the wrong project by default — worth always
  pinning `--project=som-nero-plevriti-deidbdf` explicitly, consistent with
  `vista-pm/docs/onboarding/bigquery.md`'s existing "project ID is pinned in config, not
  hardcoded per-call" convention.
- **Still Phil's to run**: `gcsfuse`/`macfuse` aren't installed — macOS requires a one-time GUI
  approval for the `macfuse` kernel extension that a headless session can't click through.

### Phase 1 — `claude_ops.md` rewrite (research-skills)

- **Environment Constraints**: the current "no code execution on this machine" default bundles
  two separate reasons — no PHI clearance, and no runtime/GPU. Split them. PHI clearance is
  retired as a reason. Runtime/GPU capacity is not: rewrite so code execution is allowed on any
  machine under Phil's Claude Code for Education account, subject to the same phi-vet discipline
  as commits, while GPU training and high-throughput batch still route to the VM fleet because
  the Mac doesn't have that hardware — a capacity statement, not a compliance one.
- **"Hard Boundary: Never Open a Remote Shell Into a VM (PHI)"**: delete the section outright.
  Its rationale no longer holds now that both machines are inside the same compliance boundary.
  The full text + its reasoning survive on `legacy/planner-mac-phi-vm-split-2026-08`.
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
- **`claude_ops.md:350`** (Pre-Commit Review section): *"All spawned subagents must be
  instructed not to run code. This machine has no runtime environment — no Python, no GPU, no
  data."* — found by `/review-plan`, missed in the first draft. Same reframe: subagents may run
  code now, gated by phi-vet; GPU-bound subagent work still doesn't belong on the Mac.
- **`claude_ops.md:361-363`** (Verification Approaches, opening line): *"Since code cannot run
  on this machine, verification means describing expected behavior for the user to confirm on
  the VM."* — same "capacity, not compliance" reframe as the Plan Document Structure fix above.

### Phase 2 — machine-gate registry (one physical file, ordered steps)

Ordered, not simultaneous — the sequence matters (see Failure Modes below):

1. **Wire `hooks/phi-vet-gate.sh` into `~/.claude/settings.json`'s existing `PreToolUse`/`Bash`
   matcher array first**, alongside (for now) `vm-shell-guard.sh` — Phase 3 removes the latter.
   Confirm `hooks/lib/is-phi-free-machine.sh --explain` still reports `PHI_FREE` right after
   this step (hook installed but inert — proves the wiring itself didn't break anything while
   the Mac is still on the allowlist).
2. **Then** remove the `BDS-H2DLP0QFM4` line from `hooks/lib/phi-free-machines.local` (one
   file, one edit — no second location to sync per the Background correction). Confirm
   `is-phi-free-machine.sh --explain` now reports `ASSUME_PHI`.
3. Per the existing fail-closed design, step 2 alone also flips `vm-shell-guard.sh` to inert on
   this Mac — **the SSH boundary is fully retired in practice here, not at Phase 3.** Phase 3
   is cleanup (deleting dead code + docs) after the boundary is already gone, not the moment it
   goes away.

**Why this order**: reversed, step 2 first would leave the Mac reading `ASSUME_PHI` with zero
mechanical commit gate for a window, since `phi-vet-gate.sh` isn't registered yet.

### Phase 3 — retire `vm-shell-guard.sh`

- Delete `hooks/vm-shell-guard.sh` from the active hook set (its logic + full history remain
  on the legacy branch and in git history — see Open Question #1 on outright deletion vs.
  archiving).
- Remove its entry from `~/.claude/settings.json`.
- `hooks/README.md`: drop the vm-shell-guard.sh table row and its whole install section.
  Tighten the phi-vet-gate.sh section's language — it currently frames "planner machines have
  no PHI" as the stable default; rewrite so PHI-free is an explicit, narrow exemption (a
  machine with no data mount and no BQ credentials at all), not something a VISTA/rad-eval Mac
  gets by default anymore.
- Add a superseded banner to `docs/plans/vm-shell-guard-hook.md` (the hook's own original
  design plan, `Status: Completed`) — found by `/review-plan`: once this phase deletes the
  hook, that doc silently describes dead functionality with no forward pointer. Mirror this
  plan's own top-of-file banner: `> Superseded — hooks/vm-shell-guard.sh deleted by
  retire-planner-mac-phi-vm-split.md (<date>).`

### Phase 4 — skill wording (research-skills)

- `commands/vm-handoff.md`: "planner Mac authors plans, configs, and scripts but cannot run
  code (no runtime, GPU, data, or credentials)" → drop "data, or credentials" (both reachable
  from the Mac now); keep "no GPU / no throughput capacity" as the real reason a handoff is
  still sometimes needed.
- `commands/phi-vet.md`: Step 0's mechanics don't change (it already just reads the allowlist),
  but its prose ("planner-only machines... have nothing to scan") reads as "Macs are PHI-free
  by default" — tighten so it's clear that's now the exception, not the default.
- `commands/review-tests.md:112,265`: "Gaps that fundamentally require infra unavailable in
  this checkout (BigQuery, GPU, PHI-mounted paths)" — GPU is still accurate; BigQuery and
  PHI-mounted paths are no longer categorically unavailable on the Mac once ADC + the bucket
  mount are in place. Narrow this to GPU-only, or reword to "compute unavailable here."
- **`commands/land.md:21`**: *"Do not run repo tests/linters/python as part of landing (per
  `claude_ops.md` → Machine-Aware Operating Mode; the VM is the executor)."* — same class of
  stale framing as `review-tests.md`, found by `/review-plan`, missed in the first draft.
  Reframe alongside the others.
- `commands/review-implementation.md` / `commands/review-tests.md` otherwise only say "this
  work runs on the VM next" without asserting a PHI-based reason — no further change needed.

### Phase 5 — VISTA-specific files

- `VISTA/code/CLAUDE.md`: the "Operating standards" paragraph names "the no-execution default"
  as one of the things `claude_ops.md` establishes — update that phrase.
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
  bucket mount is the only genuinely new piece.
- **Stale `claude_ops.md` copies** (`contrastive-3d-onc`, `MerlinOnc`, `tte-pretraining`) —
  confirmed real files, not symlinks; confirmed missing both the Machine-Aware Operating Mode
  section and the Hard Boundary section entirely (pre-existing drift, unrelated root cause).
  Bundled into this branch per Phil's call, despite the reviewer's recommendation to split it
  out separately: delete each stale file, add the same symlink every other repo uses (e.g.
  `vista-eval/docs/claude_ops.md`) → `ln -s ../../research-skills/claude_ops.md docs/claude_ops.md`.
- `crc-extraction-agent/docs/plans/2026-08-10-crc-vertex-egress-docker-profile.md` — flag only.
  Its "Machine posture" section (~lines 301-306) is written against the old split. Out of scope
  to rewrite here (an already-approved plan with its own history); note as a follow-up for
  whoever next picks that plan back up.

### Phase 6 — rad-eval's own PHI-posture registry (`RadAWS/code/rad-eval`, separate repo)

`docs/machines.md` is a general PHI-posture-per-machine registry ("Skills... and machine-aware
workflows consult this table"), not just the dispatcher's narrower gate — it independently
encodes the same "Mac = no PHI, execution deferred to VM" premise this plan retires. Confirmed
with Phil (after `/review-plan` surfaced it as a Contract Check): update it too. Rewrite the
`PHI present?` / `Notes` columns for both Mac rows (`MacBook Pro (4)`, `BDS-H2DLP0QFM4`) to
reflect Claude Code for Education's coverage — code execution allowed, gated by the same
discipline as VISTA — while `phil-sllm-01` stays the executor for GPU/throughput work.
**Do not touch `require_vertex_phi_env()` in `dispatcher.py`** — the table edit and the
dispatcher's Vertex-only gate are two different mechanisms serving two different purposes
(general machine posture vs. a specific LLM-dispatch BAA control), and only the table changes.

### Phase 7 — VM-side plan/HTML viewing via the bucket mount (new, from explain-plan feedback)

Phil's practical concern once he does most work VM-side: the VM can generate plan docs and
`/explain-plan` HTML companions, but it's typically headless — no browser to `open` them in.
Only the Mac can display a rendered HTML. Proposed mechanism (mirrors this plan's own
git-to-bucket shift): when `/explain-plan` (or `/read-plan`) runs in VM mode, write the
generated file to a bucket-mounted scratch path (e.g.
`gs://su-vista-uscentral1/scratch/explain-plan/<repo>-<plan-stem>.html`) in addition to the
git-tracked repo path, rather than requiring a commit+push+pull round-trip just to view it. The
VM prints the bucket path in its hand-off; Phil pastes a short pointer to his Mac session, which
`open`s the equivalent local path under its own gcsfuse mount. Needs one more decision before
implementing: exact scratch-path convention and whether `/open`/`/read-plan`/`/explain-plan`
gain an explicit VM-mode branch for this, or whether it's simpler to keep the existing
git-commit path for anything meant to be reviewed (a natural checkpoint) and reserve the bucket
relay for pure scratch/WIP viewing. Not resolved in this pass — flagged for a follow-up plan
once Phase 0's mount is actually working.

## Files to Modify

**research-skills (single physical checkout — see Background's symlink correction)**
- `claude_ops.md` — Phase 1 (Environment Constraints, Hard Boundary removal, Machine-Aware
  Operating Mode reframe, two Plan Document Structure framing fixes, lines 350 and 361-363)
- `hooks/vm-shell-guard.sh` — delete (Phase 3)
- `hooks/README.md` — remove vm-shell-guard.sh section, tighten phi-vet-gate.sh prose (Phase 3)
- `hooks/lib/phi-free-machines.local` — remove `BDS-H2DLP0QFM4` (Phase 2, step 2; git-ignored,
  one location only)
- `commands/vm-handoff.md` — drop "data, or credentials" from the planner-Mac description (Phase 4)
- `commands/phi-vet.md` — tighten Step 0 prose (Phase 4)
- `commands/review-tests.md` — narrow the infra-unavailable list at lines 112 and 265 (Phase 4)
- `commands/land.md` — reframe line 21's "VM is the executor" test/lint framing (Phase 4)
- `docs/plans/vm-shell-guard-hook.md` — add a superseded banner pointing at this plan (Phase 3)

**Not in git — machine-local settings**
- `~/.claude/settings.json` — add `phi-vet-gate.sh` to `PreToolUse`/`Bash` (Phase 2, step 1),
  remove `vm-shell-guard.sh` once Phase 3 lands

**VISTA-specific (separate repos, not research-skills)**
- `VISTA/code/CLAUDE.md` — one-phrase fix (Phase 5)
- `VISTA/code/CLAUDE.vm.md` — rewrite Counterpart note + Machine posture heading (Phase 5);
  manual copy to the actual VM afterward. **Not a git repo** — this is an ungated direct file
  edit with no commit/branch/review trail (see Landing & cleanup).
- `vista-pm/README.md` — add the Mac-side mount row (Phase 5). **Own repo, own landing** — a
  normal `/commit-review` + push in `vista-pm`, separate from research-skills' branch.
- `contrastive-3d-onc/docs/claude_ops.md`, `MerlinOnc/docs/claude_ops.md`,
  `tte-pretraining/docs/claude_ops.md` — delete each stale file, replace with the canonical
  symlink (Phase 5). **Three separate repos, each its own commit + landing.**

**rad-eval-specific (its own repo, not shared research-skills)**
- `RadAWS/code/rad-eval/docs/machines.md` — rewrite both Mac rows' `PHI present?`/`Notes`
  columns (Phase 6). **Own repo, own landing** — its own `/commit-review` (rad-eval trips the
  medical-data-repo detection on `CLAUDE.md` keywords, so `/phi-vet` escalates same as any
  medical-data repo).

**Flagged, not edited in this plan**
- `crc-extraction-agent/docs/plans/2026-08-10-crc-vertex-egress-docker-profile.md` — Machine
  posture section is stale; leave for that plan's own owner.

## Open Questions

1. ~~Delete `vm-shell-guard.sh` outright, or archive it under `hooks/archive/`?~~ **Resolved
   (Phil): delete outright.** Matches Phase 3 as written.
2. ~~`dicom-annotations`' PHI-copy sync workflow — replaceable by the Mac-side mount?~~
   **Resolved (Phil): not pursuing — that repo isn't active.**
3. ~~Does `rad_eval_mac_author_only_no_pytest.md` stay unchanged?~~ **Resolved (Phil): yes, it
   stays.** Confirmed independently of PHI — code execution is largely VM-side across Phil's
   repos generally (see Background's new bullet), so this memory's reasoning holds regardless.
4. **Mostly resolved: Mac-side bucket mount execution (Phase 0).** Egress cost answered in
   Phase 0; a live pre-flight (ADC auth + bucket listing, run this session) passed. Still open:
   the actual `gcsfuse`/`macfuse` mount, which needs a one-time GUI kernel-extension approval
   only Phil can click through.
5. ~~Where does the compliance claim come from?~~ **Partially resolved (Phil): cited
   <https://uit.stanford.edu/service/claude>.** This names a real source — good — but reading it
   surfaced a sharper question than the one it answered. See Open Question 7.
6. ~~Is the `RadAWS/code/research-skills` symlink intentional?~~ **Resolved (Phil): yes, it's a
   deliberate convenience, not an accident.** No action needed; Phase 2's single-edit
   simplification stands as written.
7. ~~Does VISTA's data need the Stanford AI API Gateway, or is direct Claude Code use enough?~~
   **RESOLVED (Phil): direct Claude Code is fine.** `som-nero-plevriti-deidbdf` is PHI-scrubbed,
   not PHI — classified high-risk, non-PHI, *specifically inside the deid project* (not a
   blanket statement about any other GCP project Phil touches). This unblocks Phase 0's actual
   execution and confirms Phase 1's Environment Constraints rewrite as designed.
   - **One tension worth naming, not re-litigating**: rad-eval's `dispatcher.py` pins the exact
     same project ID (`PHI_VERTEX_PROJECTS = frozenset({"som-nero-plevriti-deidbdf"})`) and its
     `require_vertex_phi_env()` gate's own comment says the block exists "because the agent's
     prompts carry PHI." Same project, opposite characterization. Plausible reconciliations:
     rad-eval's optimizer-loop agent may pull raw report text or other inputs beyond the
     already-scrubbed fields this plan is describing, or the Vertex-only gate is simply a more
     conservative choice than the data strictly requires. Either way, this plan's "leave
     rad-eval's dispatcher gate as-is" decision (confirmed earlier, unaffected by this OQ's
     resolution) stands regardless — flagging only so a future reader doesn't read the two
     documents side by side and assume one of them is simply wrong.

## Verification & VM handoff

No GPU/throughput work here — this is a docs + hooks + settings change, verified structurally,
not via a VM handoff.

- **What runs, where** (all on the Mac, Claude-Code CPU class, no VM step):
  - `jq . ~/.claude/settings.json` — must still parse as valid JSON after the hook-wiring edit.
  - `hooks/lib/is-phi-free-machine.sh --explain` — must report `PHI_FREE` right after Phase 2
    step 1 (hook wired, allowlist unchanged), then `ASSUME_PHI` right after step 2 (allowlist
    entry removed).
  - Confirm the file is gone and no `settings.json` entry references it, post-Phase-3.
  - A dry-run test: stage a trivial change in a scratch/throwaway medical-data-flavored repo
    (or a temp dir matching the gate's repo-detection patterns) and confirm `git commit` is now
    mechanically blocked pending `/phi-vet`, proving Phase 2's wiring actually took effect.
  - **Post-edit consistency check**: grep the edited `claude_ops.md` for residual "no runtime
    environment" / "code cannot run on this machine" phrasing (the exact wording found at the
    old lines 350 and 361-363) to confirm Phase 1's expanded scope was actually applied
    everywhere, not just the four originally-named sections.
  - **Symlink sanity check** (replaces the old "confirm both clones synced" check, moot per the
    Background correction): `readlink /Users/philadamson/Documents/Stanford/RSL/Chaudhari_Lab/RadAWS/code/research-skills`
    resolves to the VISTA path — confirms there's genuinely one location, not two to keep in sync.
  - Grep the VISTA and rad-eval trees for `vm-shell-guard` and `phi-free-machines` after the
    edit — confirm no other doc references the retired hook without pointing at its
    replacement/history.
- **Expected**: settings.json valid; Mac reports `PHI_FREE`→`ASSUME_PHI` in that order across
  Phase 2's two steps; phi-vet-gate.sh mechanically blocks the test commit; no dangling
  references to the deleted hook; symlink resolves correctly.
- **Stop**: if `is-phi-free-machine.sh` still reports `PHI_FREE` after Phase 2 step 2, STOP —
  the allowlist edit didn't take (wrong file, wrong machine-name match) — do not proceed to
  depend on phi-vet being active until this is fixed.

This plan has been through one `/review-plan` pass (fresh Claude Code subagent, Revise →
findings applied above) and two rounds of `/explain-plan` HTML feedback. **Approved by Phil,
2026-08-24** (recorded in `docs/plans/README.md`'s Reviewed column, since this repo has no
per-doc Reviewed field) — cleared to implement.

## Landing & cleanup

This plan spans four independent landing ceremonies — a fresh implementer needs to know which
class each edit belongs to, not just "Files to Modify":

- **research-skills** (branch + PR): currently `feat/retire-planner-mac-phi-vm-split` (pushed).
  Landing gate: Phil's explicit read + approval, given the compliance stakes — ideally after
  `/read-plan`. No VM gate needed (nothing here runs on the executor fleet). `phi-vet` itself
  is inert on this Mac until Phase 2 lands, so this branch's own commits still go through the
  *old* posture on the way in — expected, not a bug. Merge: land to `main`, push. (No second
  clone to sync — the symlink means rad-eval sees it the moment it lands, per Background.)
- **`VISTA/code/CLAUDE.md` + `CLAUDE.vm.md`** (ungated direct edits): **not a git repo** — no
  commit, branch, or review trail exists for these by construction. Edit directly; the only
  "landing" is Phil copying `CLAUDE.vm.md`'s content onto the actual VM's `CLAUDE.md` by hand.
- **`vista-pm`** (its own repo, `main`): the `README.md` mount-row edit gets its own ordinary
  `/commit-review` + push, independent of the research-skills branch's merge timing.
- **Stale-symlink repos** (`contrastive-3d-onc`, `MerlinOnc`, `tte-pretraining`): each gets its
  own commit + push in its own repo, same as `vista-pm`.
- **`rad-eval`** (its own repo, `RadAWS/code/rad-eval`): the `docs/machines.md` edit gets its
  own `/commit-review` (escalates to `/phi-vet` — this repo trips the medical-data detection),
  independent of the research-skills branch.
- **`~/.claude/settings.json`**: not version-controlled at all — the hook-wiring edit takes
  effect immediately on save, no landing step.

**Cleanup on land** (research-skills branch specifically): prune this worktree + branch; mark
this plan doc `Status: Completed`; update its row in `docs/plans/README.md` (bootstrapped
2026-08-24) to match.
