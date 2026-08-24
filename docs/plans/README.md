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
| [`executor-mac-parity-remove-deviation-handback.md`](executor-mac-parity-remove-deviation-handback.md) | Draft | Yes | Retire the Mac/VM authority split entirely (full parity) and the `vm-handoff` doc mechanism it required; standalone scripts + shared bucket mount replace it for GPU/high-throughput work. |
| [`verification-and-handoff-design-agent.md`](verification-and-handoff-design-agent.md) | Completed — superseded | Yes | Verification & VM-Handoff Design capability; its vm-status-doc mechanism and canonical spec (`references/verification-and-handoff-design.md`) retired by `executor-mac-parity-remove-deviation-handback.md`; history preserved on `legacy/vm-handoff-doc-system-2026-08`. |
| [`vm-shell-guard-hook.md`](vm-shell-guard-hook.md) | Completed — superseded | Yes | PreToolUse hook enforcing the (now-retired) "no remote shell into a VM" boundary. Landed `7768dbe`; hook deleted and superseded banner added by `retire-planner-mac-phi-vm-split.md` Phase 3, landed `main` `bc4ea6e`. |
