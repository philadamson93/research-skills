---
name: read-plan
description: Use when the user signals they're ready to read a spec or plan doc themselves — phrases like "I'll review", "ready to read it", "let me look", "open it for me", "I'll take a look", or a bare "yes"/"ok" right after Claude has named one spec or plan doc. Also invoked explicitly via `/read-plan [path]`. Runs `open <path>` so the doc launches in the user's default `.md` app, then waits for their comments and works through them. Identifies the path from recent conversation (the most recently named spec or plan) or asks via AskUserQuestion if ambiguous. Opening a doc records nothing; it is a reading aid, not an approval step. SKIP when the user asks Claude to read, summarize or audit the doc — this skill hands the doc to the user. SKIP if no spec or plan has been named recently and no path was given.
---

# read-plan

Open a spec or plan doc in the user's own app so they can read it, then get out of the way.
macOS `open <path>` routes `.md` to whatever default app is set. Claude having read the doc is
not the same as the user reading it.

## 1. Find the path

**Open without asking only when the target is obvious:**

- the user ran `/read-plan <path>`; use it as given, or
- Claude named exactly one spec or plan in the immediately preceding turn and the user replied
  with a plain yes ("yes", "ok", "open it", "let me read").

**Otherwise ask** through `AskUserQuestion` (up to four options), most recently mentioned first,
each with a one-line reason it's a candidate ("named in your last message", "spec for the current
branch"). Use `multiSelect: true` when two docs were discussed together. With no candidates, ask
free-form for a path.

Where to look:

- The mount first: `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/<repo>/`. A repo's
  `docs/plans` is often an ignored symlink to it, so searching the checkout misses plans.
- Then `docs/plans/`, `plans/`, `design/`, `rfcs/` in the repo, and any file Claude recently
  called a spec or plan.

Check the path exists before opening; a silent typo wastes the user's attention.

## 2. Open and hand off

```bash
open <path>            # several: open path1 path2
```

Then one line and stop:

> Opened `<path>` — leave comments in it, save, and tell me when you're done.

Don't summarize it, list things to watch for, suggest next skills, or carry on with other work.
The user asked to take the wheel.

## 3. Work through their comments

When they say they're done reading:

- Re-read the whole doc. Use `git diff <path>` if it's tracked; otherwise look for new
  `<!-- -->` comments, `Q:` / `TODO:` / `FIXME:` markers, new blockquotes and inserted prose.
- Answer each comment in order, quoting it briefly: propose the edit, push back with the
  reason, or ask.
- Show a proposed edit and get a yes before writing it. A direct edit the user made is
  authoritative; keep it and fix whatever else it makes inconsistent.

Repeat until they're satisfied. Treat the doc as settled only on an explicit "done" (or "all
done", "final", "ship it"), not on "ok" or "looks good" mid-loop. If a comment is still open
when they say done, name it once before closing.

Nothing is recorded either way. A `/grill` spec is approved by the interview itself, and the old
`Reviewed` column in plan indexes is frozen: don't change it.

## Permission prompts

If `Bash(open:*)` isn't allowlisted, each run prompts. Mention once that `/update-config` can
allow it; don't repeat it.
