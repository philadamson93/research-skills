---
name: open
description: Use when the user asks to open a file in their default app — "open this", "open that file", "open it for me", "open <path>", "open the <description> file", or `/open [path-or-description]`. Runs macOS `open <path>` so the file launches in whatever app the user has configured for that type. Three modes by obviousness — (1) OBVIOUS: a specific file is unambiguous from the immediate context (the file just created/edited/named in the preceding turns, or an explicit path arg) → open it directly, no prompt; (2) DESCRIBED: the user gives a short description instead of a path ("open the survival query", "the v1.3 sql") → search the repo/context for the best match, open it if confident; (3) AMBIGUOUS: multiple plausible targets or no clear match → confirm via AskUserQuestion (or ask free-form if zero candidates). Generalizes `read-plan` (which is plan-doc-specific) to any file type. SKIP when the user wants Claude to read/summarize/analyze a file's contents — that's a Read, not an open.
---

# open

Open a file in the user's default app via macOS `open <path>`. The app is whatever the user has configured for that file type (`.md` → Marked/Obsidian/VS Code, `.sql` → their SQL editor, `.pdf` → Preview, etc.). `open` routes by extension; the skill doesn't care which app handles it.

This generalizes [`read-plan`](read-plan.md) — that skill is scoped to plan docs; this one opens *any* file. When the target is specifically a plan doc the user wants to review-and-comment, prefer `read-plan` (it has the review-loop handoff). For everything else, this is the skill.

## Decide the mode by how obvious the target is

**Default toward acting, not asking.** The user invoked an *open* skill — they want a file on screen, not a quiz. Only prompt when genuinely ambiguous.

### Mode 1 — OBVIOUS → open directly, no prompt

Open without asking when exactly one file is the clear referent. Any of:

- **Explicit path arg** — `/open <path>` or "open `path/to/file`". Use it verbatim.
- **Just-touched file** — Claude created, wrote, edited, or named exactly one file in the immediately-preceding turns and the user says "open this" / "open it" / "open that". Open that file.
- **Sole candidate** — only one file matches what the user said and there's no competing interpretation.

Example: Claude just wrote `sql/ad_hoc/foo.sql` and the user says "open this file." That's obvious — open `sql/ad_hoc/foo.sql`.

### Mode 2 — DESCRIBED → search, then open if confident

The user gives a *description* rather than a path ("open the survival query", "the v1.3 sql", "that pathology priority file"). Resolve it:

- Search by filename and content: `Grep` / `Glob` over the repo, biased toward files mentioned in recent turns. A `git log -10 --name-only` or `ls` of the likely dir helps.
- If exactly one strong match → open it, and name what you opened so the user can catch a wrong guess (`Opened sql/ad_hoc/pathology_priority_ct_mortality_1yr.sql`).
- If several plausibly match → drop to Mode 3.

### Mode 3 — AMBIGUOUS → confirm

Two or more plausible targets, or a description that doesn't resolve cleanly:

- **2–4 candidates** → `AskUserQuestion` (single-select; `multiSelect: true` only if opening several together is plausible). Lead with the most-recently-referenced candidate; annotate each with a one-line *why it's a candidate* hint ("named in your last message", "last edited 2 turns ago").
- **Zero candidates** → ask free-form for a path. Don't guess wildly.

## Open

```bash
open <path>
```

Multiple files in one call: `open path1 path2 ...`.

Verify the path exists before opening (quick `ls`/`Glob`) when it came from a search or the user typed it — silently failing on a typo wastes the user's attention. A path Claude itself just created doesn't need re-checking.

## After opening

One line naming what you opened, then stop. Don't summarize the file's contents — opening is handing the file to the user, not narrating it. If the user wanted a summary they'd have asked Claude to read it.

## Permission prompts

If `Bash(open:*)` isn't allowlisted, every invocation prompts. After the first time, mention once that they can allowlist it via `/update-config` to make this skill silent. Don't re-mention on later runs.

## What NOT to do

- **Don't ask when it's obvious.** A just-created file + "open this" needs no confirmation.
- **Don't open and then summarize.** That conflates `open` (hand it over) with `Read` (Claude analyzes).
- **Don't open a plan doc the user wants to review-and-comment** — route to [`read-plan`](read-plan.md), which carries the inline-comment iteration loop.
- **Don't fabricate a path.** If a description doesn't resolve, search; if search finds nothing, ask.
