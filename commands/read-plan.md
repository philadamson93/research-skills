---
name: read-plan
description: Use when the user signals they're ready to read/review a plan doc themselves — phrases like "I'll review", "ready to read it", "let me look", "open it for me", "I'll take a look", or affirmative agreement ("yes", "ok") right after Claude has offered/named a plan doc for review. Also invoked explicitly via `/read-plan [path]`. Runs `open <path>` so the plan launches in the user's default `.md` app (Marked, Typora, Obsidian, VS Code, etc.). Identifies the path from recent conversation context (most-recently-referenced plan doc) or asks via AskUserQuestion if ambiguous. SKIP when the user is asking Claude to read, summarize, or audit the plan — this skill is for handing the plan over to the user to read themselves, not for Claude-side analysis. SKIP if no plan doc has been referenced recently and the user hasn't supplied a path.
---

# read-plan

Hand off plan docs to the user's app for human review. macOS `open <path>` routes `.md` to whatever default app the user has configured.

The skill exists because Claude reading the plan ≠ the user reading the plan. When the user wants to review themselves, the right action is to get out of the way.

## Phase 0 — Codex review prerequisite (typically already happened)

For critical plans, the typical flow is `/review-plan` → `/read-plan`. By the time `/read-plan` fires, a Codex critique at `docs/plans/reviews/<plan-stem>-feedback.md` may already have been processed (findings adjudicated, plan revised). If the user invokes `/read-plan` on a plan that has unprocessed feedback (a feedback file exists but Phase 4–6 of `/review-plan` was never run), surface that once before opening: *"Heads up — there's an unprocessed Codex critique at `<path>`. Process it first via `/review-plan`, or open the plan as-is?"*. Don't block; let the user choose.

For non-critical plans where Codex review was deliberately skipped, this phase is a no-op.

## Phase 1 — Identify the path

**Default is to prompt.** Open without asking only when the target is *obvious*. When in doubt, ask.

### Obvious — open without prompting

Both conditions must hold:

- **Explicit arg** — the user invoked `/read-plan <path>` with a path. Use it verbatim.
- **OR direct response to a single named plan** — Claude named exactly one plan doc in the *immediately preceding* turn AND the user's current message is a direct affirmative ("yes", "ok", "open it", "let me read", "I'll review") with no other plan named or implied. The pairing has to be unambiguous — if Claude offered a choice between plans, or named multiple, this is no longer obvious.

In all other cases, prompt.

### Not obvious — prompt via AskUserQuestion

Scan recent turns (and `git log -10 --name-only -- '*plans/*'` if needed) for plan-doc candidates:

- Anything under `docs/plans/`, `plans/`, `design/`, `rfcs/`, `proposals/`
- Files named `PLAN.md`, `DESIGN.md`, `RFC.md`, `IMPLEMENTATION.md`, `PROPOSAL.md` at any depth
- Markdown files Claude has explicitly framed as a plan/spec/RFC in recent turns

Then raise an `AskUserQuestion` (max 4 options + auto "Other"):

- Lead with the most recently mentioned candidate.
- Annotate each with a one-line *why it's a candidate* hint (e.g., "in-flight on current branch", "last touched 2 commits ago", "named in your last message").
- Use `multiSelect: true` if 2+ plans were paired in the discussion (e.g., a refactor + its downstream feature plan) — opening both at once is common in that case.
- If zero candidates surface, drop the multi-choice and ask free-form for a path.

Verify the chosen path exists (quick `ls` or `Read` check) before opening. Silently failing on a typo wastes the user's attention.

## Phase 2 — Open

```bash
open <path>
```

For multiple paths, open in one call: `open path1 path2 ...`.

## Phase 3 — Hand off

One line, then stop:

> Opened `<path>` — leave inline comments, save, and ping me when you're done.

That's it. Do **not**:

- Summarize the plan.
- Pre-list "things to watch for" or "open questions."
- Volunteer to run `/review-plan` or other next-step skills.
- Continue working on adjacent tasks.

The user explicitly asked to take the wheel. Wait for them.

## Phase 4 — Pick up inline comments and iterate

The user's review loop is:

1. They edit the plan doc directly in their app, leaving inline comments — typically HTML comments `<!-- ... -->`, blockquotes, `TODO:` / `Q:` / `FIXME:` markers, or fresh prose edits inserted into sections.
2. They save and ping you ("done", "comments in", "ready", "take a look", "ok back to you", etc.).
3. You re-read the plan doc to surface what changed.
4. You address each comment — incorporate the change, push back with rationale, or ask a clarifying question.
5. The user iterates again, or moves on.

**When the user pings:**

- Re-read the full plan doc with `Read`. Don't rely on memory of the previous version — diff what's there now against what was there before.
- If the repo has the plan committed, `git diff <path>` is the cleanest way to surface changes; otherwise visually scan for new comment markers (`<!--`, `Q:`, `TODO:`, `FIXME:`, blockquotes that weren't there) and inserted prose.
- For each comment/change, respond in order. Quote the comment briefly so the user can track which one you're addressing, then give your response (proposed edit, pushback, or clarifying question).
- If a comment requests an edit you agree with, propose the concrete diff and ask for confirmation before writing — don't auto-edit the plan during the review loop.
- If the user has already directly edited the plan (not just commented), treat the edit as authoritative; don't undo it. Acknowledge and adjust downstream sections that need to stay consistent.

Iteration continues until the user is satisfied. There is no fixed number of rounds.

## Phase 5 — Completion: only on "done"

The plan is marked complete **only when the user explicitly says "done"** (or an unambiguous synonym: "all done", "we're done", "plan is final", "ship it"). Do not infer completion from:

- "ok" / "looks good" / "fine" / "sounds right" — these are mid-loop acknowledgments, not completion signals.
- The user moving on to a different topic.
- A long silence.

When the user does say "done":

- Confirm the plan is in its final state (no unaddressed comments, no open questions left dangling).
- If anything is still unresolved, surface it once before treating the plan as complete: "Before I close this out — comment in section X about Y is still open. Resolve or defer?"
- **Mark the plan as Reviewed.** If the project has a plan-tracking index (`docs/plans/README.md` or equivalent with a `Reviewed` column), update this plan's row to `Reviewed: Yes`. Confirm inline: "Marked `<plan>` as Reviewed: Yes in `docs/plans/README.md`." A plan reaches `Yes` only through human review — this path, or an approved, SHA-in-sync `/explain-plan` HTML (the peer visual path, which records approval the same way); `/wrapup` will never auto-promote on its own. If no such index exists, skip silently (don't bootstrap one mid-review-loop; that's `/wrapup`'s job).
- Then offer the natural next steps in one line: commit the plan via `/commit-review`, run `/review-plan` (its handoff-readiness lens checks fresh-agent implementability), or start implementation.

## Permission prompts

If `Bash(open:*)` isn't allowlisted, every invocation will prompt. After the first time, mention once that they can allowlist it via `/update-config` to make this skill silent. Don't re-mention on subsequent runs.

## What NOT to do

- **Don't auto-fire on a bare "yes"/"ok"/"sure"** unless Claude *just* named a plan doc in the immediately-preceding turn — otherwise the trigger is too broad.
- **Don't fire when the user asks Claude to review the plan** ("can you check this plan?", "audit it", "any gaps?"). That's `/review-plan` territory.
- **Don't open non-plan files.** For arbitrary `open` calls, the user can invoke Bash directly.
- **Don't summarize, even briefly.** The whole point is the user reading the source, not Claude's gloss of it.
