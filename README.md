# research-skills

Personal Claude Code skills, shared in case they're useful. These are slash commands and instructions I use across my own research workflow.

## Contents

- `commands/` — slash commands loaded by Claude Code from `~/.claude/commands/`
  - `explain-plan.md` — visual companion to `read-plan`: generates a self-contained interactive HTML (Mermaid diagrams with pan/zoom, blast-radius map, step accordion, inline feedback widgets) for plans too dense to review in prose
  - `debate.md` — structured adversarial debate for major design decisions where reasonable people disagree (cross-repo architecture, build system choices, data contract design); two parallel advocates, codebase-grounded arguments, main-agent moderation, synthesized decision doc
  - `review-plan.md` — independent design audit of a plan doc by Codex CLI or a fresh Claude Code subagent, then *applies* agreed feedback
  - `wrapup.md` — end-of-session cleanup
  - `next.md` — "where did we leave off?" session-opener
  - `commit-review.md` — commit workflow with an appropriateness review (catches accidentally-leaked private content) before commit + push
  - `phi-vet.md` — hard pre-commit gate for medical-data repos that scans files for PHI leakage (patient/encounter/study identifiers, sample row data, free-text excerpts, image files); `commit-review` escalates to this when working in an OMOP/NeuralFrame/EHR/DICOM context
  - `review-implementation.md` — independent implementation audit of uncommitted code against a plan doc
  - `review-tests.md` — independent test-coverage audit of uncommitted code against a plan doc
  - `plan-handoff-readiness.md` — pre-implementation handoff check: does the plan POINT AT or STATE DIRECTLY everything a fresh agent needs to implement it?
  - `read-plan.md` — opens a plan doc in the user's default `.md` app
- `CLAUDE.md` — my global Claude Code instructions (interaction style, environment notes)

## How to use

This repo is a snapshot of my `~/.claude/`. To use one of these commands:

1. Clone: `git clone git@github.com:philadamson93/research-skills.git`
2. Copy a command to `~/.claude/commands/` (or symlink the whole dir).
3. Optionally copy `CLAUDE.md` to `~/.claude/CLAUDE.md`.

The skills assume Claude Code as the harness. Some reference companion tools (`codex` CLI, `gh`); install as needed.

### One-shot setup on a fresh VM (or local Mac)

To wire this repo up as the source of truth for `~/.claude/commands/` and `~/.claude/CLAUDE.md` so future updates flow both ways, run once after cloning:

```bash
git clone git@github.com:philadamson93/research-skills.git ~/code/research-skills
ln -s ~/code/research-skills/commands ~/.claude/commands
ln -s ~/code/research-skills/CLAUDE.md ~/.claude/CLAUDE.md
```

After this, `git -C ~/code/research-skills pull` (or push, after `commit-review`) updates the live commands. Symlinks survive Claude Code restarts; no rebuild needed.

**Session-start sync habit:** at the start of any work session on a machine that has this repo cloned, do `git -C ~/code/research-skills pull --ff-only` to pick up cross-machine updates. Worth bookkeeping in a per-machine memory note (e.g., `feedback_research_skills_sync.md`) so future sessions remember.

## Notes

- `review-plan.md` looks for a repo-local checklist at `.claude/references/plan-review-checklist.md` — if present, it's loaded into the reviewer prompt to ground the audit in repo-specific contracts. Each project should author its own.
- Skills evolve; feedback / PRs welcome.
