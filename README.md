# research-skills

Personal Claude Code skills, shared in case they're useful. These are slash commands and instructions used across a research workflow.

## Contents

- `commands/` — slash commands loaded by Claude Code from `~/.claude/commands/`
  - [`explain-plan.md`](commands/explain-plan.md) — visual companion to `read-plan`: generates a self-contained interactive HTML (Mermaid diagrams with pan/zoom, blast-radius map, step accordion, inline feedback widgets) for plans too dense to review in prose
  - [`review-plan.md`](commands/review-plan.md) — independent design audit of a plan doc by Codex CLI or a fresh Claude Code subagent, then *applies* agreed feedback
  - [`wrapup.md`](commands/wrapup.md) — end-of-session cleanup
  - [`next.md`](commands/next.md) — "where did we leave off?" session-opener
  - [`commit-review.md`](commands/commit-review.md) — commit workflow with an appropriateness review (catches accidentally-leaked private content) before commit + push
  - [`phi-vet.md`](commands/phi-vet.md) — hard pre-commit gate for medical-data repos that scans files for PHI leakage (patient/encounter/study identifiers, sample row data, free-text excerpts, image files); `commit-review` escalates to this when working in an OMOP/NeuralFrame/EHR/DICOM context
  - [`review-implementation.md`](commands/review-implementation.md) — independent implementation audit of uncommitted code against a plan doc
  - [`review-tests.md`](commands/review-tests.md) — independent test-coverage audit of uncommitted code against a plan doc
  - [`plan-handoff-readiness.md`](commands/plan-handoff-readiness.md) — pre-implementation handoff check: does the plan POINT AT or STATE DIRECTLY everything a fresh agent needs to implement it?
  - [`read-plan.md`](commands/read-plan.md) — opens a plan doc in the user's default `.md` app
  - [`debate.md`](commands/debate.md) — structured adversarial debate for major design decisions where reasonable people disagree (cross-repo architecture, build system choices, data contract design); two parallel advocates, codebase-grounded arguments, main-agent moderation, synthesized decision doc
- `hooks/` — Claude Code lifecycle hooks (separate from skills: hooks are shell scripts the harness fires automatically at events like `PreToolUse` / `SessionStart`, not invoked-by-intent skills)
  - [`phi-vet-gate.sh`](hooks/phi-vet-gate.sh) — `PreToolUse` hook that hard-gates `git commit` in medical-data repos until [`phi-vet`](commands/phi-vet.md) has signed off on the current staged tree (forces both PHI scan and explicit per-doc read-acknowledgement). See [`hooks/README.md`](hooks/README.md) for install.
- [`CLAUDE.md`](CLAUDE.md) — global Claude Code instructions (interaction style, environment notes)
- [`claude_ops.md`](claude_ops.md) — operating standards shared across research repos: planning workflow, code quality, git practices, pre-commit review pointers, skill composition discipline. Designed to be **symlinked into each repo as `docs/claude_ops.md`** so all repos reference the same source-of-truth (see per-repo setup below).

## How to use

This repo is a snapshot of `~/.claude/` plus the canonical `claude_ops.md`. To use:

1. Clone: `git clone git@github.com:philadamson93/research-skills.git ~/code/research-skills`
2. Wire up the global commands + CLAUDE.md (one-shot setup, below).
3. For each research repo that should consume the operating standards, add a per-repo `docs/claude_ops.md` symlink (per-repo setup, below).

The skills assume Claude Code as the harness. Some reference companion tools (`codex` CLI, `gh`); install as needed.

### One-shot setup on a fresh VM (or local Mac)

Wire this repo up as the source-of-truth for `~/.claude/commands/` and `~/.claude/CLAUDE.md` so future updates flow both ways:

```bash
git clone git@github.com:philadamson93/research-skills.git ~/code/research-skills
ln -s ~/code/research-skills/commands ~/.claude/commands
ln -s ~/code/research-skills/CLAUDE.md ~/.claude/CLAUDE.md
```

After this, `git -C ~/code/research-skills pull` (or push, after `commit-review`) updates the live commands. Symlinks survive Claude Code restarts; no rebuild needed.

**Hooks are not auto-installed by the symlink above** — they require an entry in `~/.claude/settings.json` per [hook](hooks/README.md). Each hook has its own install section since hooks vary in payload contract and matcher pattern.

**Session-start sync habit:** at the start of any work session, do `git -C ~/code/research-skills pull --ff-only` to pick up cross-machine updates. `claude_ops.md` documents this as a Session Start step (it suggests a pull when the local clone is 3+ commits behind `origin/main`).

### Per-repo setup: `claude_ops.md` symlink

For each research repo that should consume the canonical operating standards (so all repos reference the same `claude_ops.md` and a single edit propagates everywhere):

```bash
cd <repo>
ln -sf ../../research-skills/claude_ops.md docs/claude_ops.md
git add docs/claude_ops.md && git commit -m "docs: symlink claude_ops.md to research-skills canonical source"
```

The relative `../../research-skills/...` target assumes both repos are siblings under `~/code/` (or `~/Documents/.../code/`). Adjust the relative path if `docs/` lives at a different depth or the repo is checked out somewhere else. The symlink is checked into the repo so collaborators / fresh checkouts pick it up automatically — they only need `research-skills` cloned alongside.

## Notes

- [`review-plan.md`](commands/review-plan.md) looks for a repo-local checklist at `.claude/references/plan-review-checklist.md` — if present, it's loaded into the reviewer prompt to ground the audit in repo-specific contracts. Each project should author its own.
- Skills evolve; feedback / PRs welcome.
