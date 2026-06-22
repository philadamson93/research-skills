---
name: next
description: Use when the user opens a session asking "what's next?", "where did we leave off?", "what should I work on?", "any next steps?", or similar — and there's no obvious in-flight task already named. Also invoked explicitly via `/next`. FIRST fetches + fast-forwards from remote so it never surveys stale local refs (otherwise pushes from another machine — e.g. a VM test-gate readback — get missed and you recommend already-done work), THEN surveys tracking docs (NEXT.md / docs/next.md / TODO.md / BACKLOG.md / docs/plans/README.md / MEMORY.md / recent commits / current branch / all local+remote branches for unmerged work), classifies as "clear next" vs "need direction" vs "genuinely empty", surfaces 2-4 candidate tasks with a recommendation via AskUserQuestion when there's a fork, then deep-dives the chosen task (plan doc + memory + recent code) before handing off a concrete first action. SKIP when the user has already named a specific task to work on, or mid-session when context for the current task is already loaded.
---

# next

Session-opener triage. The user is back at the keyboard and wants to know what to do — your job is to survey, surface options, let them steer, then deep-dive the chosen task.

Five phases (0–4). Don't skip ahead — **Phase 0 is not optional**; surveying stale refs is the single most common way this skill recommends already-finished work.

## Phase 0 — Refresh from remote (do this FIRST, before reading anything)

Tracking docs, plan status, and branch state are frequently updated from *another machine* — most often a VM that ran a test gate or live run and pushed the readback. If you survey stale local refs you'll miss those updates and may recommend work that's already done. So before the survey:

1. **Fetch** every remote: `git fetch --all --prune`. This refreshes remote-tracking refs so the Phase 1 branch survey (`git branch -a`) and all behind/ahead counts are accurate — not just the current branch. If there's no remote, or the fetch fails (offline, auth prompt), note it in one line and continue with local state.
2. **Fast-forward the branch(es) you'll survey.** For the current branch — and any active feature branch you intend to deep-dive — if it's behind its upstream, `git pull --ff-only`. If it can't fast-forward (diverged) or the worktree is dirty in a blocking way, **do not force it**: surface "branch X is N behind origin, can't ff (diverged/dirty)" as a finding and let the user decide. Never `git pull` (merge) or `--rebase` unprompted, and never push.
3. **Say what the refresh changed.** If the pull brought in commits, state it in one line — e.g. "pulled 4 commits — a VM test-gate readback marking the gate PASSED." That incoming delta is usually the freshest and most decision-relevant signal in the whole survey, so it leads the Phase 4 write-up.

Caveat: if the active branch is checked out in a **git worktree** (common for in-flight work), fast-forward it *in that worktree*, not the main checkout. Use `git -C <worktree> pull --ff-only`.

## Phase 1 — Survey the candidates (breadth, not depth)

Read these in parallel — whichever exist:

1. **`NEXT.md`, `docs/next.md`, `TODO.md`, `BACKLOG.md`** at repo root or under `docs/` — explicit next-step trackers. Highest-priority signal.
2. **`docs/plans/README.md`** (or `plans/README.md`, `docs/plans.md`) — index of plan docs; look for "In Progress", "Planned", "Next", or similar status entries.
3. **`MEMORY.md`** — auto-memory pointers, especially `project_*.md` entries flagging current focus, blockers, or in-flight work.
4. **Recent commits**: `git log --oneline -20` and `git status` — what was last touched, what's uncommitted, what branch is checked out.
5. **Current branch name** — often encodes the in-flight feature (`feat/foo-bar` → "foo bar" is probably the active task).
6. **All existing branches** (local *and* remote): `git branch -a --sort=-committerdate` — surface any non-merged feature branches so in-flight work doesn't get lost. For any branch that looks active (recent commits, not merged into main), note it as a candidate. Cross-check against `git log main..<branch>` to confirm there's unmerged work.

Skim, don't read in full. The goal here is to *identify* candidates, not understand them deeply. Run the file reads in parallel.

If none of the standard tracking files exist, say so explicitly — that's a useful signal in itself, and an offer to bootstrap one (in wrapup) is appropriate later.

## Phase 2 — Classify: clear next, fork, or empty?

After the survey, classify out loud (one sentence) so the user can correct you before you commit to a path:

- **Clear next** — one task is unambiguously the next thing. Signals: a single "In Progress" plan with active commits on the matching branch, a tracking doc with one item at the top and nothing competing, a memory entry flagging a single blocker. Skip Phase 3, go straight to Phase 4.
- **Fork — need direction** — multiple plausible candidates, or status is ambiguous. Go to Phase 3.
- **Genuinely empty** — no tracking doc, no in-flight branch, no obvious next. Say so explicitly and ask the user (free-form) what direction they want to go. Don't fabricate options to fill the void.

Verify "in progress" claims against `git log` / branch state, not just the tracking doc title — trackers go stale.

## Phase 3 — Surface options via AskUserQuestion

When forking, raise candidates as an `AskUserQuestion` — not inline prose. Per global preference, multi-choice selections always go through that tool.

- **2-4 options.** More than four overwhelms; one option means you should have classified as "clear next."
- **Lead with your recommendation as the first option** and mark it as recommended in the label.
- **Each option's label should pack three things**: task name, scope hint ("small fix", "multi-day plan", "blocked on X"), and why it's a candidate ("in progress on this branch", "blocking PET work per MEMORY.md", "top of docs/next.md").
- **Always include an "Other / something else" escape** so the user isn't forced into your framing.

Don't deep-dive any candidate yet. The whole point of this phase is to let the user steer *before* you spend context on the wrong one.

## Phase 4 — Deep-dive the chosen task

Once a task is chosen (whether via Phase 2 "clear next" or Phase 3 selection), gather full context:

- **Plan doc** — read in full if it exists (`docs/plans/<task>.md` or wherever the project keeps them).
- **Memory entries** — grep `MEMORY.md` for the task name and read any matching `*.md` files in the memory directory.
- **Journal / decision entries** — if the project has `docs/journal/`, `docs/decisions/`, or similar, check for recent entries naming the task.
- **Code state** — for in-flight tasks: `git log <branch>` and `git diff main...HEAD` to see what's already done. Read the files most recently touched.
- **Open questions / blockers** — anything the plan or memory flagged as unresolved.

Run the reads in parallel where possible.

Then summarize for the user as bullets — not prose:

- **Where things stand** (1-3 bullets)
- **Open questions / decisions needed** (if any — skip the section if none)
- **Recommended first concrete action** (one bullet, specific: "edit `path/to/file.py:42` to do X", not "start implementing")

End with a hand-off line: "Ready to start with <action>, or want to dig into something else first?"

## What NOT to do

- **Don't survey stale refs.** Phase 0 (fetch + ff) runs first, always — skipping it is how this skill recommends work a VM already finished and pushed.
- **Don't deep-dive multiple candidates in Phase 1.** That wastes context before the user has steered.
- **Don't recommend a task that's already shipped.** Verify status against `git log` and plan-doc state — trackers lag behind reality.
- **Don't skip AskUserQuestion when there are 2+ candidates.** Inline "should I do X or Y?" is the wrong shape here.
- **Don't bootstrap a NEXT.md if it doesn't exist.** That's a wrapup-skill concern. Just note its absence.
- **Don't run this mid-session** when the user is already deep in a task and asks a tangentially-related question. This skill is for the session-opener case.
