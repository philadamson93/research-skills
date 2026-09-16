# Plans

Tracks every plan doc in `docs/plans/` — status, review sign-off, and a one-line description.
Bootstrapped 2026-08-24 (`/wrapup`); before this, plan status lived only in each doc's own
`Status:` header (still the source of truth for implementation status — this table adds the
cross-doc `Reviewed` column that header convention didn't carry).

**Reviewed** column values: `Yes` (user reviewed the current content, via `/read-plan` or an
approved SHA-in-sync `/explain-plan` HTML), `No` (never reviewed), `Stale` (was `Yes`, plan
substantively edited since).

| Plan | Status | Reviewed | Description |
|---|---|---|---|
| [`retire-planner-mac-phi-vm-split.md`](retire-planner-mac-phi-vm-split.md) | Completed | Yes | Retire the planner-Mac/PHI-VM split now that Claude Code for Education covers both machines; landed `main` `bc4ea6e` (ff) 2026-08-24. tte-pretraining's symlink skipped (premise didn't hold); Phase 0's bucket mount landed via `rclone nfsmount` (gcsfuse turned out Linux-only). |
| [`executor-mac-parity-remove-deviation-handback.md`](executor-mac-parity-remove-deviation-handback.md) | Completed | No | Retire the Mac/VM authority split entirely (full parity) and the `vm-handoff` doc mechanism it required; standalone scripts + shared bucket mount replace it for GPU/high-throughput work. Landed `main` `1743127` (ff) 2026-08-24; directed live in conversation rather than via `/read-plan`/`/explain-plan`. |
| [`verification-and-handoff-design-agent.md`](verification-and-handoff-design-agent.md) | Completed — superseded | Yes | Verification & VM-Handoff Design capability; its vm-status-doc mechanism and canonical spec (`references/verification-and-handoff-design.md`) retired by `executor-mac-parity-remove-deviation-handback.md`; history preserved on `legacy/vm-handoff-doc-system-2026-08`. |
| [`vm-shell-guard-hook.md`](vm-shell-guard-hook.md) | Completed — superseded | Yes | PreToolUse hook enforcing the (now-retired) "no remote shell into a VM" boundary. Landed `7768dbe`; hook deleted and superseded banner added by `retire-planner-mac-phi-vm-split.md` Phase 3, landed `main` `bc4ea6e`. |
| [`guardrail-hooks-ask-before-danger.md`](guardrail-hooks-ask-before-danger.md) | Completed | No | Four PreToolUse guardrail hooks (dangerous shell ops, mount deletes, provisioning, pre-compact wrapup nudge) plus shared lib and committed test suite; landed `main` `955a0c7` via `/land` (ff-only), suite green 46/46. Codex's *Blocked* verdict on three real false-negatives all fixed and regression-tested. `~/.claude/settings.json` wiring is machine-local — live on this VM, replicate on the Mac. |
| [`planning-layer-and-mount-migration.md`](planning-layer-and-mount-migration.md) | **Completed 2026-09-16 — all seven stages landed (Stage 5 @788882e, Stage 6 @6e1afc2)** | Yes (`/explain-plan`, 2026-09-14, SHA `fc335cc1603e`) | Seven-stage program (0-6): Stage 0 fixes the mount-delete hook (realpath-scoped, lands first); Stage 1 adds standing rules incl. a close-out block that *writes* to the board/ledger; Stage 2 a one-page brief per program (why + stage + dated decisions); Stage 3 one status board per repo on the mount, retiring the 706-line `next.md` forked across 127 checkouts; Stage 4 **copy-only** — copy existing plans to the mount for context, author new ones there, no delete/untrack/symlink; Stage 5 teaches the skills the new layer; Stage 6 an always-on **manager** that holds the big-picture map (which of the ~8 running things fits where), advances ready work, reminds a drifting agent, and routes questions to Phil via a board-state queue — deciding nothing a task raised for him. Research-grounded (5-pass review + local tests). Brief + research findings: `<mount>/chaudhari_lab/phil/planning/programs/`. |
