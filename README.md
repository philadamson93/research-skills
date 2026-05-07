# research-skills

Personal Claude Code skills, shared in case they're useful. These are slash commands and instructions I use across my own research workflow.

## Contents

- `commands/` — slash commands loaded by Claude Code from `~/.claude/commands/`
  - `commit-review.md` — commit workflow with an appropriateness review (catches accidentally-leaked private content) before commit + push
  - `review-plan.md` — independent design audit of a plan doc by Codex CLI or a fresh Claude Code subagent, then *applies* agreed feedback
  - `review-implementation.md` — independent implementation audit of uncommitted code against a plan doc
  - `review-tests.md` — independent test-coverage audit of uncommitted code against a plan doc
  - `plan-handoff-readiness.md` — pre-implementation handoff check: does the plan POINT AT or STATE DIRECTLY everything a fresh agent needs to implement it?
  - `read-plan.md` — opens a plan doc in the user's default `.md` app
  - `next.md` — "where did we leave off?" session-opener
  - `wrapup.md` — end-of-session cleanup
- `CLAUDE.md` — my global Claude Code instructions (interaction style, environment notes)

## How to use

This repo is a snapshot of my `~/.claude/`. To use one of these commands:

1. Clone: `git clone https://github.com/philadamson93/research-skills.git`
2. Copy a command to `~/.claude/commands/` (or symlink the whole dir).
3. Optionally copy `CLAUDE.md` to `~/.claude/CLAUDE.md`.

The skills assume Claude Code as the harness. Some reference companion tools (`codex` CLI, `gh`); install as needed.

## Notes

- `review-plan.md` looks for a repo-local checklist at `.claude/references/plan-review-checklist.md` — if present, it's loaded into the reviewer prompt to ground the audit in repo-specific contracts. Each project should author its own.
- Skills evolve; feedback / PRs welcome.
