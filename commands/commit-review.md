---
description: Commit workflow for this project's repos — runs an appropriateness review over uncommitted changes (to catch private conversations / third-party speculation / working-group deliberations that leaked into docs) before committing per project conventions (no AI attribution, single-line thematic) and pushing. TRIGGER when about to run `git commit`, when the user says "commit this" or "land this" or "commit and push," at end-of-session wrap-up, or any time uncommitted work is being landed. ALWAYS invoke this rather than running `git commit` inline — the inline shortcut is the anti-pattern this skill exists to fix. SKIP only if the user explicitly says "skip the review."
---

Review all uncommitted changes for content that may be more appropriate as private notes than public commits. Surface concerns BEFORE committing — do not self-redact silently.

## Step 1 — Appropriateness review

Scan all uncommitted content (staged, unstaged, and untracked files) with the question: *"Is there anything here the user might want to keep out of a public-facing commit history?"* Use judgment, but pay attention to:

- **Direct quotes of private conversations with identifiable individuals** — even if the person is unnamed, context often narrows identification. Reactions, private assessments, anything received in a meeting setting.
- **Third-party commentary beyond published-work analysis** — speculation about specific researchers, institutions, motivations, career decisions. Critique of a published paper is fine; speculation about the author's reasoning is not.
- **Private working-group deliberations** — internal decisions, working-relationship dynamics, partner-referencing budget or cost discussions.
- **Asides marked conversationally as "shouldn't log" / "neither here nor there"** that may have leaked into structured docs.
- **PHI / credentials / API keys** — low-probability in plan/journal docs, sweep anyway. **In medical-data repos** (cues: project CLAUDE.md mentions PHI handling; the repo touches BigQuery / OMOP / NeuralFrame / DICOM / EHR; an existing memory note flags this repo as PHI-risk), ESCALATE to `/phi-vet` for the depth-pass instead of relying on this inline sweep — `phi-vet` carries the full identifier catalog (person_id formats, DICOM UIDs, accession numbers, sample-row re-identification rules) and is the canonical pre-commit gate for this class of repo. Do not silently fall back to inline sweep when escalation is warranted.

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

Honor whatever commit-style conventions the project specifies — typically in the project's `CLAUDE.md`, a memory file, or `docs/claude_ops.md`. Common conventions to expect and respect:

- **No AI attribution trailers.** Never include `Co-Authored-By: Claude` or similar.
- **Single line, substantive, thematic.** Many projects favor a single-line-but-detailed commit summary over either terse one-liners or multi-paragraph bodies. Match the historical style visible in `git log`.
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
