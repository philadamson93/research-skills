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
| [`retire-planner-mac-phi-vm-split.md`](retire-planner-mac-phi-vm-split.md) | Completed | Yes | Retire the planner-Mac/PHI-VM split now that Claude Code for Education covers both machines; landed `main` `bc4ea6e` (ff) 2026-08-24. tte-pretraining's symlink skipped (premise didn't hold); Phase 0's gcsfuse mount still owed. |
| [`verification-and-handoff-design-agent.md`](verification-and-handoff-design-agent.md) | Completed | Yes | Verification & VM-Handoff Design capability — canonical spec now at `references/verification-and-handoff-design.md`, landed `fcf2e83`. |
| [`vm-shell-guard-hook.md`](vm-shell-guard-hook.md) | Completed — superseded | Yes | PreToolUse hook enforcing the (now-retired) "no remote shell into a VM" boundary. Landed `7768dbe`; hook deleted and superseded banner added by `retire-planner-mac-phi-vm-split.md` Phase 3, landed `main` `bc4ea6e`. |
