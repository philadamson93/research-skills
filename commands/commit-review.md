---
description: Commit workflow for this project's repos — runs an appropriateness review over uncommitted changes (to catch private conversations / third-party speculation / working-group deliberations that leaked into docs) before committing per project conventions (no AI attribution, single-line thematic) and pushing. TRIGGER when about to run `git commit`, when the user says "commit this" or "land this" or "commit and push," when `/wrapup`'s opt-in commit gate selects a commit (a milestone close — *not* every session end), or any time uncommitted work is being landed. ALWAYS invoke this rather than running `git commit` inline — the inline shortcut is the anti-pattern this skill exists to fix. SKIP only if the user explicitly says "skip the review."
---

Review all uncommitted changes for content that may be more appropriate as private notes than public commits. Surface concerns BEFORE committing — do not self-redact silently.

## Step 1 — Appropriateness review

Scan all uncommitted content (staged, unstaged, and untracked files) with the question: *"Is there anything here the user might want to keep out of a public-facing commit history?"* Use judgment, but pay attention to:

- **Direct quotes of private conversations with identifiable individuals** — even if the person is unnamed, context often narrows identification. Reactions, private assessments, anything received in a meeting setting.
- **Third-party commentary beyond published-work analysis** — speculation about specific researchers, institutions, motivations, career decisions. Critique of a published paper is fine; speculation about the author's reasoning is not.
- **Private working-group deliberations** — internal decisions, working-relationship dynamics, partner-referencing budget or cost discussions.
- **Asides marked conversationally as "shouldn't log" / "neither here nor there"** that may have leaked into structured docs.
- **PHI / credentials / API keys** — low-probability in plan/journal docs, sweep anyway. **In medical-data repos, MUST escalate to `/phi-vet` for the depth-pass — do NOT rely on this inline sweep.** Trigger cues for "medical-data repo": project `CLAUDE.md` or `docs/claude_ops.md` mentions PHI handling; the repo touches BigQuery / OMOP / NeuralFrame / DICOM / EHR / WSI / pathology bucket / vista_bench / clinical-trial cohorts; an existing memory note flags this repo as PHI-risk; the diff touches any file matching `**/labels/**`, `**/cohort*/**`, `**/sql/**`, `**/data/**`, or per-example/per-patient parquets. `/phi-vet` carries the full identifier catalog (person_id formats, DICOM UIDs, accession numbers, slide hashes, sample-row re-identification rules, slide-surrogate redaction policy) and is the canonical pre-commit gate for this class of repo. Falling back to inline sweep when escalation is warranted is a **silent bypass of the PHI gate** — do not do it. If `/phi-vet` is unavailable in this environment, surface that explicitly to the user and pause rather than proceed.

Scientific content is fine to commit without flagging:
- Critique of published papers (standard related-work analysis).
- Future-work ideas, speculation about research directions.
- Decision rationales with attribution conventions the project uses (e.g. `**Human:**` / `**Agent:**`).
- Methodology, cost, and budget discussions internal to the project.
- Collaboration-pattern observations about the working relationship within the project.

Use `git status`, `git diff`, and Grep to cover scope. Read untracked files fully.

## Step 2 — Surface flags, pause

If anything was flagged, list each (file + line + reason + suggested disposition) and wait for user decision. The user picks redact / keep / rewrite.

If nothing was flagged, proceed to commit.

## Step 3 — Commit

Honor whatever commit-style conventions the project specifies. **Read the project docs FIRST**, before drafting and before glancing at `git log`:

1. `docs/claude_ops.md` (vista repos and similar)
2. `CLAUDE.md` at repo root
3. Any commit-style entry in the project's auto-memory directory

If those docs specify a length or style ("concise," "one sentence," "short," "detailed-thematic"), **follow the doc — not the git log**. `git log` shows what individual commits ended up as, which may include drift from the spec. The project docs are authoritative.

Common conventions to expect and respect:

- **No AI attribution trailers.** Never include `Co-Authored-By: Claude` or similar.
- **Default to concise.** A descriptive single sentence (≤ ~150 chars) is the right starting point. Only expand to a longer thematic message if (a) the project doc explicitly favors detailed messages, OR (b) the change genuinely spans multiple themes that need enumeration AND project conventions allow it. Do NOT extrapolate from a few long commits in `git log` — those may have been outliers or pre-spec.
- **One theme per commit.** Split unrelated themes into separate commits. Cascading themes that all support one larger conceptual unit can ride together.
- Use the HEREDOC pattern for the commit message to avoid quoting issues.
- Stage files by name, not `git add -A` or `git add .` (avoids accidentally including credentials or untracked junk).

## Step 4 — Push

Push behavior depends on invocation args — a calling skill or the user can pre-authorize or suppress the push:

- **`args: "no-push"`** — commit succeeded; skip pushing entirely. Report only the commit SHA.
- **`args: "push-authorized"`** — the calling context has already gated the push decision (e.g., `/wrapup`'s "Commit and push" choice, or a user who said "commit and push" upfront). Push to the tracking remote without further prompting, including for `main` / `master`.
- **Standalone / no push hint** (default behavior):
  - Check the current branch.
  - If not `main` / `master`, push to the tracking remote.
  - If `main` / `master`, raise an `AskUserQuestion` before pushing — structured **"Push" / "Hold local"** options, not inline yes/no.
- **Never force-push** unless the user explicitly asks for it.

Report the commit SHA and push result.
