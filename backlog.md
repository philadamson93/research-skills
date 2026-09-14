# research-skills — backlog

Known issues and deferred work for the skill repo itself. Per the same pointer-style discipline `/wrapup` enforces on project repos: short entries, link out to substance.

## Runtime cache vs canonical drift

**Resolved on this Mac (`BDS-H2DLP0QFM4`), verified 2026-08-24**: `ls -la ~/.claude/` confirms `commands -> /Users/philadamson/Documents/Stanford/VISTA/code/research-skills/commands` is a proper symlink (Resolution A from the original filing). Also verified on the VM (`phil-sllm-01`) 2026-09-11: `~/.claude/commands -> /home/philadamson/code/research-skills/commands`, a proper symlink, so skill edits in this repo are live immediately and `/wrapup` Step 7's runtime-to-canonical copy is a no-op on both machines. If it recurs elsewhere, the options below still apply.

The intended setup is a symlink: `~/.claude/commands → research-skills/commands` (per README "One-shot setup on a fresh VM"). Originally filed 2026-05-12 after finding `~/.claude/commands/` was instead a *separate git repo* with its own history, drifted from canonical.

**If it recurs**: (A) convert to a symlink per the README setup, reconciling drift first; (B) keep two repos but automate sync (a pre-session hook rsyncing canonical → runtime); (C) document the manual `cp`-and-commit ritual in `wrapup` Step 7 (already does — "sync direction matters" + the `cp` recipe).

## rad-eval has no per-repo plan-review-checklist

Three repos have a `.claude/references/plan-review-checklist.md` (vista_bench, vista-eval,
vista-ct); rad-eval does not. Until one is seeded, the three things `/review-plan` always checks (sibling-repo
contracts, building something you don't need yet, and whether a fresh session could build the
plan) run without repo-grounded specifics for rad-eval reviews. Worth a small followup plan to author a rad-eval checklist grounded in its
extraction / seed-gate / equivalence verification patterns.

Filed 2026-07-08 while scoping the (now-retired) verification-and-handoff-design agent (moved
out of that plan's open questions so the plan doesn't carry a stale cross-repo reference).

## VM-side plan/HTML viewing has no bridge to the Mac's browser

Once execution moves VM-side more (per the PHI-posture retirement, see below), `/explain-plan`
and `/read-plan` output authored on the VM has no way to reach a browser — the VM is typically
headless. Proposed direction (Phase 7 of
[`retire-planner-mac-phi-vm-split.md`](retire-planner-mac-phi-vm-split.md#phase-7)): write
generated HTML to a bucket-mounted scratch path instead of requiring a commit+push+pull
round-trip. Needs its own follow-up plan once that plan's Phase 0 (Mac-side bucket mount) is
actually working — not scoped yet.

Filed 2026-08-24, surfaced via `/explain-plan` feedback on the PHI-posture retirement plan.

## Two repos hold real copies of claude_ops.md instead of symlinks

39 of the 41 `<repo>/docs/claude_ops.md` paths are symlinks to this repo's canonical file, so the
2026-09-11 plain-English rewrite reached them for free. Two are **real copies** and are stale at
older revisions: `contrastive-3d-onc/docs/claude_ops.md` (248 lines) and
`paper-trail/docs/claude_ops.md` (181 lines) — both predate even the pre-rewrite canonical.
Decide per repo: convert to a symlink like the other 39, or leave it if the divergence is
deliberate. Each is a separate medical-data repo, so replacing the file there costs one commit
and its own PHI review.

Filed 2026-09-11 during the plain-English rewrite. **paper-trail's repair is now scheduled as
Stage 1(e) of [`docs/plans/planning-layer-and-mount-migration.md`](docs/plans/planning-layer-and-mount-migration.md)** (APPROVED 2026-09-14); contrastive-3d-onc still open here.

## ~/code/CLAUDE.md still uses the retired shorthand

The workspace-root `CLAUDE.md` (156 lines, loaded into every session under `~/code/`) still says
"Machine posture", "VM / Executor", "Stay in Executor lane", and "planner-only" — the vocabulary
`claude_ops.md` dropped on 2026-09-11. It also repeats guidance the rewritten standard now states
plainly. A parallel copy lives on the Mac at `~/Documents/Stanford/VISTA/code/CLAUDE.md` and is
kept deliberately in step, so both need the same pass. Neither is in a git repo, so there is no
branch or review gate — but it is cross-machine, so do both in one sitting.

Filed 2026-09-11 during the plain-English rewrite.

## phi-vet gate hook matches command text, not the tree being committed

Two related defects in `hooks/phi-vet-gate.sh`, both hit on 2026-09-11:

1. **It judges the wrong tree.** As a PreToolUse hook it inspects the index *before* the command
   it gates has run, so a shell invocation that stages files and then commits them in one step is
   judged against whatever was staged beforehand. The denial message read "Staged: 0 file(s)"
   while blocking. Worse, the inverse also happened: a 350-line doc rewrite committed cleanly
   with no human doc read at all, because the pre-command index happened to match an
   already-signed-off tree. Staging in a separate command first gives the gate the real tree and
   it then behaves correctly.
2. **It fires on prose.** The gate blocked a `python3` heredoc that performed no git operation
   whatsoever — its only offence was containing a staging-then-committing command *as quoted text*
   inside documentation describing this very bug. Any command whose text merely mentions
   committing is caught, which makes it impossible to author docs about git workflows through
   Bash.

Fix direction: gate on the post-command tree (or refuse to judge a compound command that stages
its own files), and match on the command's actual git invocation rather than a substring of its
text.

Filed 2026-09-11, hit while committing the plain-English rewrite.

## Mac hardware serial is committed, against this repo's own policy

`.gitignore` states that real machine names "often embed a hardware serial" and must stay
machine-local, never committed — `hooks/lib/phi-free-machines.local` exists precisely for that.
But `BDS-H2DLP0QFM4` is committed in `backlog.md` and in several `docs/plans/` files
(`retire-planner-mac-phi-vm-split.md` in four places, plus its rendered `.html`). It is already
on the remote, so no single commit can undo the exposure; scrubbing it means a history rewrite,
or a decision that it does not matter. Worth deciding which, especially if
`philadamson93/research-skills` is a public remote.

Surfaced 2026-09-11 by `/commit-review`'s appropriateness scan (pre-existing, not introduced by
that commit).

## (Future entries — add as encountered)
