Reference: docs/claude_ops.md (canonical: ~/code/research-skills/claude_ops.md)

**Status: Completed** (2026-08-26). Landed to `main` @955a0c7 via `/land` (ff-only); branch
`feat/dangerous-ops-and-compact-hooks` pruned. All four hooks + shared lib + committed test
suite are on `main`; suite green (46/46). Codex verdict was *Blocked* on real false-negatives
(heredoc-tail truncation, global `--help` exemption, contiguous-only gcloud matching) — all
fixed and regression-tested. `~/.claude/settings.json` wiring is machine-local (live on this
VM; replicate on the Mac counterpart). See
`docs/plans/reviews/guardrail-hooks-ask-before-danger-feedback.md`.

# Guardrail hooks: ask-before-delete (/mnt), ask-before-provision, and post-compact rule re-injection

## Context

A recent session **ignored `claude_ops.md` after an auto-compact** and did a batch of
unapproved work: no plan approval, started a VM, and created a 1.5TB disk — all without
asking. Root cause is structural, not a one-off:

1. **`claude_ops` is advisory, not enforced.** Its rules (plan-before-code,
   ask-before-destructive) live *in context*. Auto-compact is exactly the event that can
   drop them — the Claude Code docs do **not** guarantee `CLAUDE.md`/project instructions
   are re-injected after a compact (confirmed via docs research). A post-compact session
   can lose the rules, then act freely because this VM runs in `auto` permission mode
   (`CLAUDE_CODE_ENABLE_AUTO_MODE=1` + `defaultMode:"auto"`), which auto-approves most
   actions.
2. **The few genuinely irreversible/expensive actions should not depend on the model
   having read anything.** They should be gated by hooks that fire regardless of context
   state.

**Intended outcome:** convert the two worst failure classes from advisory text into
*enforced human-approval prompts*, and re-anchor the core rules into any fresh
post-compact context. Specifically:
- **Ask before deleting `/mnt` data** (the shared bucket mount — irreplaceable).
- **Ask before expensive/irreversible cloud provisioning** (VM create/start, disk
  create/resize, terraform).
- **Re-inject `claude_ops` non-negotiables after an auto-compact.**

This mirrors the existing enforcement pattern already on this machine:
`research-skills/hooks/phi-vet-gate.sh` (a `PreToolUse`→Bash hook that inspects the
command string and returns a decision on stdout). We reuse that pattern, don't reinvent it.

**Grounded facts (verified this session):**
- Claude Code **2.1.246** installed; bundle contains `hookSpecificOutput` +
  `permissionDecision` → the modern hook decision protocol incl. `"ask"` is supported.
- Working hook config shape on this machine (authoritative — phi-vet uses it):
  `{"matcher":"Bash","hooks":[{"type":"command","command":"<abs-path>"}]}` under
  `hooks.PreToolUse`. (An `{on/if/exec}` shape surfaced in docs research but does NOT
  match the shape that actually works here — ignore it.)
- Hook stdin JSON: `{"tool_name","tool_input":{"command"},"cwd","permission_mode",...}`.
- Decision protocol (exit 0 + stdout JSON):
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask|deny|allow","permissionDecisionReason":"..."}}`.
  `"ask"` forces a human Y/N prompt — this is what we want (human decides in the moment),
  not `phi-vet`'s legacy `{"decision":"block"}` (which tells Claude to go do something).

## Goal

Three new shell hooks under `research-skills/hooks/`, wired into `~/.claude/settings.json`,
plus README docs. Two are `PreToolUse`→Bash "ask" gates; one is a `SessionStart` context
re-injection. Design decisions (confirmed with user):
- **Deletion gate: `/mnt` only.** Ask only when a destructive verb co-occurs with a `/mnt`
  path. Recursive `rm` elsewhere (code dirs, worktrees, scratch) does **not** prompt — keeps
  routine cleanup quiet.
- **Deletion surface: broadened** (user decision, post-review 2026-08-26): beyond
  rm/unlink/shred/truncate/dd/rsync--delete/find-delete, the gate also covers `rmdir`, `mv`
  (incl. moving data OUT of /mnt), and truncating redirects (`> /mnt/…`). Accepts a
  conservative nag on `mv` INTO /mnt.
- **Infra gate: always ask** on create/start/resize/apply (no size threshold — these are
  rare; a prompt each is fine).
- **Infra surface: current verb set kept** (user decision, post-review 2026-08-26): only
  Compute-Engine instances/disks, buckets, terraform (the incident class). Other cost-creating
  gcloud resources (GKE, Cloud SQL, MIGs) are NOT gated — YAGNI; add later if needed. The
  *normal-form parsing* of these verbs was fixed (global flags, `beta`/`alpha` tracks,
  `gsutil -m`, `terraform -chdir`).

## Approach

### Hook 1 — `hooks/mnt-delete-gate.sh` (PreToolUse → Bash)
- Parse `tool_input.command`; allow (silent, exit 0) anything that isn't Bash or doesn't
  match a deletion verb touching `/mnt`.
- **Trip condition:** a deletion/destruction verb **whose target includes a `/mnt` path**:
  - `rm` (any form) with a `/mnt/...` argument
  - `gsutil rm`, `gcloud storage rm` on a path/URL — gate only if `/mnt` appears (local
    mount deletes; bucket-URL deletes are a separate concern, out of scope here — note it)
  - `find <under /mnt> ... -delete` / `... -exec rm`
  - `truncate`, `dd of=/mnt/...`, `shred` on `/mnt`
  - `rsync --delete` with a `/mnt` destination
  - `mv /mnt/... <elsewhere>` (moving data OUT of /mnt) and `> /mnt/<existing>` overwrite —
    include if cheap to detect; otherwise list as a known gap.
- **Decision:** emit `permissionDecision:"ask"` with a reason naming the matched command and
  the `/mnt` path, e.g. *"This command deletes data under /mnt (the shared bucket mount).
  Confirm you want to proceed."*
- Detection is on the **literal command string** (env vars/`eval`/`$()`/subshells are not
  expanded). Document this limit (see Known limits). Match `/mnt` as a token to avoid
  matching substrings like `/mntx`.

### Hook 2 — `hooks/provision-gate.sh` (PreToolUse → Bash)
- Trip on expensive/irreversible provisioning verbs (command-position match, like phi-vet's
  git-commit matcher, to avoid matching inside strings):
  - `gcloud compute instances create`, `gcloud compute instances start`
  - `gcloud compute disks create`, `gcloud compute disks resize`
  - `gcloud compute instances create ... --create-disk` (disk via instance create)
  - `terraform apply`, `terraform destroy`
  - `gsutil mb` (make bucket)
- **Decision:** `permissionDecision:"ask"` with a reason naming the resource and (if
  present) parsed `--size`/`--machine-type` so the human sees the cost surface in the prompt.

> Hooks 1 & 2 are **two scripts** (single responsibility, independently testable/toggleable),
> both wired to the same `PreToolUse`→Bash matcher array alongside `phi-vet-gate.sh`. Matching
> hooks may run **in parallel** (the harness resolves them by precedence `deny`>`ask`>`allow`,
> not textual order), and each is silent on non-matches, so order is immaterial. Shared
> command-scanning logic (heredoc-body stripping + the fail-closed `ask` emitter) lives in
> `hooks/lib/shell-scan.sh`, sourced by both — a single tested scanner rather than duplicated
> parsing (Codex agreed this is the right modular call).

**Implemented parsing details (post-review):** detection is **whole-string co-occurrence** on
the heredoc-**body**-stripped command (bodies are data, e.g. a `codex exec` prompt, and must
not trip the gate; but a command *after* a heredoc terminator is preserved and still gated).
Both gates are **fail-closed**: missing `jq` or an unparseable event ⇒ `ask`, never silent
allow. This is NOT a shell parser — see Known limits.

### Hook 3 — `hooks/post-compact-reinject.sh` (SessionStart)
- Fire on `SessionStart` with trigger reason **`compact`** only (startup already loads
  `CLAUDE.md`; re-injecting on every start is redundant). Parse the reason from stdin;
  exit 0 silently for non-compact reasons.
- On compact, emit a short **re-anchor** to stdout (SessionStart hook stdout is injected
  into context; if the version requires `hookSpecificOutput.additionalContext`, use that —
  verify in Step 0). Content is a *compact pointer*, not a duplication of `claude_ops`
  (modularity):
  > You may be resuming after an auto-compact — earlier context (incl. `claude_ops.md`)
  > may have been dropped. Re-anchor on these NON-NEGOTIABLES before acting, and re-read
  > `~/code/research-skills/claude_ops.md` if unsure:
  > 1. **Plan before code** — enter plan mode and get explicit approval before implementing.
  >    Do **not** start new implementation off a compacted context without re-confirming
  >    the plan.
  > 2. **Ask before destructive/expensive actions** — /mnt deletion, VM/disk provisioning
  >    (hooks enforce the worst cases; treat it as a rule regardless).
  > 3. **PHI discipline** — never echo PHI; commits gated by `/phi-vet`.
  > 4. **Executor lane** — don't broad-plan or major-rewrite without user confirmation.

### Hook 3b (optional, smaller) — `hooks/precompact-wrapup-nudge.sh` (PreCompact, trigger `auto`)
- Emit a `systemMessage`/stderr note: *"Auto-compact imminent — avoid starting new work;
  consider `/wrapup`."* **Does not block** (blocking a full context risks an overflow wall).
- Best-effort: the exact PreCompact output field that surfaces to the user needs Step-0
  verification. If it can't cleanly surface a message, drop it — Hook 3 is the load-bearing
  piece.

### Machine-gating
Unlike `phi-vet-gate.sh` (PHI-machine-gated), these gates are about destructive/expensive
ops, not PHI — **active on every machine**, no allowlist. Simpler. The scripts live in
`research-skills` (versioned, shared); the wiring lives in each machine's
`~/.claude/settings.json` (machine-local, not committed), same split as phi-vet.

## Files to Modify

New scripts (new concern → they sit alongside the existing hook in `research-skills/hooks/`):
- `research-skills/hooks/mnt-delete-gate.sh` — /mnt deletion ask-gate
- `research-skills/hooks/provision-gate.sh` — infra provisioning ask-gate
- `research-skills/hooks/post-compact-reinject.sh` — SessionStart(compact) rule re-inject
- `research-skills/hooks/precompact-wrapup-nudge.sh` — PreCompact(auto) nudge (optional)
- `research-skills/hooks/lib/shell-scan.sh` — shared `strip_heredoc_bodies` + `emit_ask`
  (sourced by both gates; single tested scanner)
- `research-skills/hooks/tests/gate_tests.sh` — table-driven regression suite (all four hooks;
  false-negative/positive + fail-closed + lifecycle cases); part of the landing gate
- `research-skills/hooks/README.md` — add a table row + install section per new hook
  (mirror the existing `phi-vet-gate.sh` section: wire-up JSON, sanity check, offline tests)

Machine wiring (NOT committed — machine-local settings, replicate on the Mac):
- `~/.claude/settings.json` — add the two Bash gates to the existing
  `hooks.PreToolUse[].matcher=="Bash"` array (next to phi-vet), add a `hooks.SessionStart`
  entry for the re-inject, and (if kept) a `hooks.PreCompact` entry for the nudge. Use
  absolute paths (`~` is not expanded in hook command paths).

## Decisions (resolved — formerly Open Questions)
- **Bucket-URL deletes** (`gsutil rm gs://...` not via the /mnt mount): **out of scope** —
  the ask was about /mnt; documented as a known limit.
- **PreCompact nudge** (Hook 3b): **kept, best-effort.** Fixed to read the documented
  `.trigger` field. It's non-load-bearing (post-compact-reinject is the real mechanism); drop
  it if a future version doesn't surface `systemMessage`.
- **/mnt destructive surface / infra breadth**: resolved under Goal → Design decisions above.

## Verification

**Canonical suite:** `bash hooks/tests/gate_tests.sh` (table-driven, 46 cases). Run as a
file — never paste payloads on a command line, or the live gates trip. **Landing gate = this
suite green.** Outcomes below record what was confirmed.

**Step 0 — capability probe.** ✅ CONFIRMED: 2.1.246 honors `permissionDecision:"ask"` from a
PreToolUse hook (the `/mnt` gate fired a live Y/N prompt during development — indeed it
even caught a false-positive on a `codex exec` command, which drove the heredoc-body fix).
SessionStart plain **stdout** is the injection channel (no `additionalContext` needed).

**Step 1 — offline suite.** ✅ 46/46. Covers: real-destructive/provision → ask (incl. the new
rmdir/mv/redirect verbs and the Codex-found bypasses: heredoc-then-command, here-string,
`gcloud beta`/`--project`, `gsutil -m`, `terraform -chdir`, help-decoy `echo --help && …`);
benign → silent; accepted conservative nags; fail-closed on malformed JSON; lifecycle hooks
(`source:compact` re-anchor, `trigger:auto` nudge). **Stop condition (any ask-case false-silent
= blocker) was hit and cleared** — the field-delimiter-vs-regex-`|` bug that silenced all
gsutil/terraform cases was found by the suite and fixed (parallel arrays).

**Step 2 — live end-to-end.** ✅ Partially confirmed via the live `codex exec` false-positive
(gate fired) + the `rm -f /mnt/__nonexistent_gate_probe__` doc probe. Full re-confirm on a
fresh session after settings reload is a cheap manual check.

**Step 3 — post-compact injection.** ✅ CONFIRMED (was deferred): the re-anchor text appeared
in *this* resumed context after a real compact — visible via the `SessionStart:compact hook
success` block carrying the 4 NON-NEGOTIABLES. So the load-bearing mechanism is proven live,
not just offline.

## Landing & cleanup
- **Branch:** `feat/dangerous-ops-and-compact-hooks` in `research-skills`. Although
  `claude_ops` allows simple approved skill tweaks straight on main, three new
  *safety-critical* hooks warrant a branch + review.
- **Landing gate:** `/review-plan` sign-off (done — Codex, revisions applied); `gate_tests.sh`
  green (46/46); README updated. **PHI gate:** although `research-skills` is non-medical, its
  `docs/` now contains files mentioning "PHI" (this plan, the review), so `phi-vet-gate.sh`'s
  keyword heuristic may treat a commit here as gated on this VM. **Follow the actual
  `/commit-review` → `/phi-vet` result rather than asserting exemption** — if the gate fires,
  run `/phi-vet` (content is Phil's own tooling, no patient data, so the human read is quick).
- **Merge sequence:** single branch → `/land` to `main`, prune branch + worktree.
- **Cleanup on land:** mark this plan `Status: Completed`; the `~/.claude/settings.json`
  wiring is machine-local (already live on the VM; leave a note to replicate on the Mac
  counterpart per the parallel-CLAUDE.md convention).
- **Commits (thematic):** (1) the four hook scripts + shared lib; (2) the test suite;
  (3) README docs **+ this approved plan doc + the Codex review** (claude_ops requires the
  approved plan to be committed). Settings.json wiring is NOT committed.

## Known limits (stated honestly in README — see hooks/README.md "Known limits")
Detection is **whole-string co-occurrence** on the heredoc-body-stripped command, NOT a shell
parse. Grouped honestly:
- **Inherent (need a real parser/runtime; true backstop = OS/IAM least-privilege on the
  mount):** indirection is invisible (`eval`/`$()`/backticks/vars/`xargs`/symlinks — e.g.
  `rm -rf "$MNT_TARGET"` won't fire); `.cwd` is not consulted (relative `rm` from a `/mnt` cwd
  won't fire).
- **Deliberate scope:** `/mnt`-only deletion; provision verb set limited to the incident class;
  bucket-URL (`gsutil rm gs://…`) deletes out of scope.
- **Accepted conservative nags (safe-direction):** cross-subcommand/quoted/commented mentions
  and `mv` INTO /mnt may prompt — without a parser we can't distinguish mention from execution,
  so we ask when unsure.
- **Bypass mode:** `--dangerously-skip-permissions`/`bypassPermissions` may skip scoped hooks;
  a future `disableBypassPermissionsMode` setting would close it.

The earlier plan wrongly claimed "compound commands are matched per-subcommand" — corrected:
there is no subcommand splitting (Codex finding).
