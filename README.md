# research-skills

Personal Claude Code skills, shared in case they're useful. These are slash commands and instructions used across a research workflow.

## Contents

- `commands/` — slash commands loaded by Claude Code from `~/.claude/commands/`
  - [`explain-plan.md`](commands/explain-plan.md) — visual companion to `read-plan`: generates a self-contained interactive HTML (Mermaid diagrams with pan/zoom, blast-radius map, step accordion, inline feedback widgets) for plans too dense to review in prose
  - [`review-plan.md`](commands/review-plan.md) — independent design audit of a plan doc by Codex CLI or a fresh Claude Code subagent, then *applies* agreed feedback
  - [`wrapup.md`](commands/wrapup.md) — end-of-session cleanup
  - [`next.md`](commands/next.md) — "where did we leave off?" session-opener
  - [`commit-review.md`](commands/commit-review.md) — commit workflow with an appropriateness review (catches accidentally-leaked private content) before commit + push
  - [`phi-vet.md`](commands/phi-vet.md) — hard pre-commit gate for medical-data repos that scans files for PHI leakage (patient/encounter/study identifiers, sample row data, free-text excerpts, image files); `commit-review` escalates to this when working in an OMOP/NeuralFrame/EHR/DICOM context. Machine-aware (fail-closed): inert on machines in the PHI-FREE allowlist (`hooks/lib/is-phi-free-machine.sh`), active everywhere else
  - [`review-implementation.md`](commands/review-implementation.md) — independent implementation audit of uncommitted code against a plan doc
  - [`review-tests.md`](commands/review-tests.md) — independent test-coverage audit of uncommitted code against a plan doc
  - [`plan-handoff-readiness.md`](commands/plan-handoff-readiness.md) — pre-implementation handoff check: does the plan POINT AT or STATE DIRECTLY everything a fresh agent needs to implement it?
  - [`vm-handoff.md`](commands/vm-handoff.md) — author and close the planner-Mac → executor-VM round-trip: **renders** the `docs/vm-status/<date>-<sha>.md` handoff doc from the plan's *Verification & VM handoff* section (the per-step **Expected** + **Stop** criteria already reviewed with the plan via `review-plan` — derived, not invented), gates them for sign-off (tiered by complexity), then offers `commit-review` to land; on the VM appends the run results back into the *same* doc and offers `phi-vet` → `commit-review`. Auto-detects author vs readback mode by `hostname` per `claude_ops.md` Machine-Aware Operating Mode. Chains with — and reuses, never duplicates — `review-plan`, `plan-handoff-readiness`, `phi-vet`, `commit-review`
  - [`read-plan.md`](commands/read-plan.md) — opens a plan doc in the user's default `.md` app
  - [`open.md`](commands/open.md) — opens *any* file in the user's default app via `open <path>`; resolves the target by obviousness (just-touched file / explicit path → open directly; a description → search then open; ambiguous → confirm). General-purpose sibling of `read-plan`
  - [`debate.md`](commands/debate.md) — structured adversarial debate for major design decisions where reasonable people disagree (cross-repo architecture, build system choices, data contract design); two parallel advocates, codebase-grounded arguments, main-agent moderation, synthesized decision doc
- `hooks/` — Claude Code lifecycle hooks (separate from skills: hooks are shell scripts the harness fires automatically at events like `PreToolUse` / `SessionStart`, not invoked-by-intent skills)
  - [`phi-vet-gate.sh`](hooks/phi-vet-gate.sh) — `PreToolUse` hook that hard-gates `git commit` in medical-data repos until [`phi-vet`](commands/phi-vet.md) has signed off on the current staged tree (forces both PHI scan and explicit per-doc read-acknowledgement). Self-gates by machine (inert on PHI-free machines, so it's safe to install everywhere). See [`hooks/README.md`](hooks/README.md) for install.
  - [`lib/is-phi-free-machine.sh`](hooks/lib/is-phi-free-machine.sh) — shared fail-closed machine check (PHI-FREE allowlist) consulted by *both* the hook above and the [`phi-vet`](commands/phi-vet.md) skill, so they never disagree about where PHI tooling is active.
- [`CLAUDE.md`](CLAUDE.md) — global Claude Code instructions (interaction style, environment notes)
- [`claude_ops.md`](claude_ops.md) — operating standards shared across research repos: planning workflow, code quality, git practices, pre-commit review pointers, skill composition discipline. Designed to be **symlinked into each repo as `docs/claude_ops.md`** so all repos reference the same source-of-truth (see [Setup → Once per repo](#once-per-repo) below).

## Setup

These skills assume Claude Code as the harness. Some reference companion tools (`codex` CLI, `gh`); install as needed.

Setup is two parts: **once per machine** to make the slash commands available, then **once per repo** to give that repo the operating standards. The mechanics behind each step are in [How it works](#how-it-works) below.

### Once per machine

Make the slash commands available globally:

```bash
git clone git@github.com:philadamson93/research-skills.git ~/code/research-skills
ln -s /path/to/research-skills/commands ~/.claude/commands
```

Updating is just `git -C ~/code/research-skills pull` — symlinks survive Claude Code restarts, no rebuild. Hooks are **not** installed by these symlinks; they need a `~/.claude/settings.json` entry per [hook](hooks/README.md).

### Once per repo

Give a repo the operating standards. Two steps — symlink the canonical file in, then import it from the repo's own `CLAUDE.md` so it loads into every session run from that repo:

```bash
cd <repo>
ln -sf /path/to/research-skills/claude_ops.md docs/claude_ops.md   # adjust to reach your research-skills clone
```

Then add to the repo's `CLAUDE.md` (create one at the repo root if it has none):

```markdown
## Operating standards

@docs/claude_ops.md
```

Commit both so collaborators and fresh checkouts pick them up (they only need `research-skills` cloned alongside):

```bash
git add docs/claude_ops.md CLAUDE.md && git commit -m "docs: wire in claude_ops.md operating standards"
```

## How it works

- **The symlink makes the file present; the `@`-import makes it load.** Claude Code auto-loads `CLAUDE.md` files (walking from the cwd up to root) plus `~/.claude/CLAUDE.md` — but never an arbitrary file under `docs/`. So the symlink alone governs nothing; the `@docs/claude_ops.md` line is what pulls the standards into the session (`@path` inlines that file's contents, and the read follows the symlink to the canonical source). The symlink earns its keep two ways: it gives `@docs/claude_ops.md` a stable target regardless of where `research-skills` is cloned, and it makes the `Reference: docs/claude_ops.md` breadcrumb at the top of plan docs resolve to a real file.

- **The relative symlink target** `../../research-skills/...` assumes `<repo>` and `research-skills` are siblings (both under `~/code/` or similar), since the link sits at `<repo>/docs/`. Adjust the depth if `docs/` lives elsewhere or the repo is checked out somewhere unusual.

- **Shortcut if you launch Claude from a parent folder.** If you run Claude from a workspace folder that sits *above* several repos, one `@research-skills/claude_ops.md` import in *that folder's* `CLAUDE.md` is inherited by every repo beneath it (CLAUDE.md loads the entire tree from cwd to root), so no per-repo wiring is needed. Convenient at scale, but it assumes the parent-folder launch pattern — the per-repo steps above are the portable default for working inside a single repo.

- **Session-start sync:** `git -C ~/code/research-skills pull --ff-only` at the start of a session picks up cross-machine updates. `claude_ops.md` documents this as a Session Start step (it suggests a pull when the local clone is 3+ commits behind `origin/main`).

## Notes

- [`review-plan.md`](commands/review-plan.md) looks for a repo-local checklist at `.claude/references/plan-review-checklist.md` — if present, it's loaded into the reviewer prompt to ground the audit in repo-specific contracts. Each project should author its own.
- Skills evolve; feedback / PRs welcome.
