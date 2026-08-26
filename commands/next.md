---
name: next
description: Use when the user opens a session asking "what's next?", "where did we leave off?", "what should I work on?", "any next steps?", or similar — and there's no obvious in-flight task already named. Also invoked explicitly via `/next`. FIRST enumerates git worktrees, fetches, and fast-forwards every checkout from remote so it never surveys stale local refs or misses parallel work (a parallel session may have pushed a milestone commit; sibling worktrees hold in-flight work the main checkout can't see), THEN surveys tracking docs (NEXT.md / docs/next.md / TODO.md / BACKLOG.md / docs/plans/README.md / MEMORY.md / docs/session/ readbacks / recent commits / current branch / all local+remote branches + all worktrees for unmerged or uncommitted work), classifies as "clear next" vs "need direction" vs "genuinely empty", surfaces 2-4 candidate tasks with a recommendation via AskUserQuestion when there's a fork, then deep-dives the chosen task (plan doc + memory + recent code) before handing off a concrete first action. SKIP when the user has already named a specific task to work on, or mid-session when context for the current task is already loaded.
---

# next

Session-opener triage. The user is back at the keyboard and wants to know what to do — your job is to survey, surface options, let them steer, then deep-dive the chosen task.

**Lead your first response with a one-line context header naming the repo and current branch** — e.g. `research-skills · main` (add the worktree path when you're in a non-primary checkout: `research-skills · feat/foo · .claude/worktrees/foo`). Phil launches sessions across ~50 repos and multiple worktrees of the same repo, so stating *where you are* up front prevents surveying — or recommending work on — the wrong checkout. Derive it from Phase 0's `git worktree list` + `git branch --show-current`.

Five phases (0–4). Don't skip ahead — **Phase 0 is not optional**; surveying stale refs (or missing a sibling worktree's in-flight work) is the single most common way this skill recommends already-finished or already-in-progress work.

## Phase 0 — Enumerate worktrees + refresh from remote (do this FIRST, before reading anything)

Two things go stale between sessions and both make the survey recommend the wrong work: **remote refs** (a parallel session landed a milestone commit — the local refs don't know yet) and **sibling worktrees** (parallel work on another branch in the *same* repo, often with uncommitted changes the main checkout cannot see). Refresh both before reading anything. This is **not optional** — run the commands, don't just intend to. Note that most in-flight state now lives **uncommitted** in the working tree plus `docs/session/` docs of this checkout (commit is opt-in per `claude_ops.md` → Commit Cadence), so the dirty-worktree scan (step 4) and the `docs/session/` survey (Phase 1) are the primary resume signals; the remote fetch guards against milestone commits pushed elsewhere.

1. **Enumerate worktrees — FIRST.** `git worktree list`. A single repo commonly has several checkouts, each on a different branch — that's how parallel in-flight work is isolated (this very skill may be running inside one). You need the full set *before* refreshing so you fast-forward the right checkout for each branch and don't overlook a worktree holding the freshest work.
2. **Fetch every remote.** `git fetch --all --prune` — refreshes remote-tracking refs so the Phase 1 branch survey (`git branch -a`) and all behind/ahead counts are accurate, not just the current branch. No remote, or fetch fails (offline, auth prompt) → note it in one line and continue with local state.
3. **Fast-forward every active checkout, each in its own worktree.** For the main checkout **and** each worktree from step 1 whose branch is behind its upstream: `git -C <path> pull --ff-only`. A branch checked out in a worktree must be ff'd *in that worktree*, never the main checkout. If a checkout can't fast-forward (diverged) or is dirty in a blocking way, **do not force it** — surface "branch X is N behind origin, can't ff (diverged/dirty)" as a finding and let the user decide. Never `git pull` (merge) or `--rebase` unprompted, and never push.
4. **Flag uncommitted work in every worktree.** `git -C <path> status --short` for each. A worktree with uncommitted changes is in-flight work and a prime Phase 1 candidate — it won't show up in `git log` or branch listings, so this is the only place it surfaces.
5. **Say what the refresh changed.** If a pull brought in commits, state it in one line per checkout — e.g. "pulled 4 commits on `feat/foo` — a milestone landing the verified runner." Note any worktree carrying uncommitted changes too. That incoming delta (remote pull or dirty worktree) is usually the freshest, most decision-relevant signal in the whole survey, so it leads the Phase 4 write-up.

## Phase 1 — Survey the candidates (breadth, not depth)

Read these in parallel — whichever exist:

1. **`NEXT.md`, `docs/next.md`, `TODO.md`, `BACKLOG.md`** at repo root or under `docs/` — explicit next-step trackers. Highest-priority signal.
2. **`docs/plans/README.md`** (or `plans/README.md`, `docs/plans.md`) — index of plan docs; look for "In Progress", "Planned", "Next", or similar status entries.
3. **`MEMORY.md`** — auto-memory pointers, especially `project_*.md` entries flagging current focus, blockers, or in-flight work.
4. **`docs/session/`** — git-ignored structured session docs (readbacks, VM-verify writeups, "what's next" state) from prior sessions in this checkout. This is where the freshest uncommitted state usually lives; skim the most recently modified files (`ls -t docs/session/ 2>/dev/null`).
5. **Recent commits**: `git log --oneline -20` and `git status` — what was last touched, what's uncommitted, what branch is checked out.
6. **Current branch name** — often encodes the in-flight feature (`feat/foo-bar` → "foo bar" is probably the active task).
7. **All existing branches** (local *and* remote): `git branch -a --sort=-committerdate` — surface any non-merged feature branches so in-flight work doesn't get lost. For any branch that looks active (recent commits, not merged into main), note it as a candidate. Cross-check against `git log main..<branch>` to confirm there's unmerged work.
8. **All worktrees** (from Phase 0's `git worktree list`): treat each as a candidate source. A branch checked out in a sibling worktree is active in-flight work even if its newest commit isn't recent — especially one with uncommitted changes (Phase 0 step 4). Don't let the main checkout's branch crowd these out; parallel work across worktrees is exactly what gets dropped otherwise.

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

Once a task is chosen (whether via Phase 2 "clear next" or Phase 3 selection), **first pin where it lives** — the current checkout, a sibling worktree path (from Phase 0's `git worktree list`), or a remote-only branch — and run every read below against *that* source, not the invocation checkout. A task that won via Phase 1 step 7 lives in another worktree; reading `HEAD` here would inspect the wrong branch. Then gather full context:

- **Plan doc** — read in full if it exists (`docs/plans/<task>.md` or wherever the project keeps them).
- **Session doc** — read the task's `docs/session/` readback / state doc in full if one exists; it carries the substance and next steps the resume block pointed at.
- **Memory entries** — grep `MEMORY.md` for the task name and read any matching `*.md` files in the memory directory.
- **Journal / decision entries** — if the project has `docs/journal/`, `docs/decisions/`, or similar, check for recent entries naming the task.
- **Code state** — for in-flight tasks, run the reads in the task's *own* checkout: `git -C <chosen-worktree> log --oneline <branch>` and `git -C <chosen-worktree> diff main...<branch>` for committed work, plus `git -C <chosen-worktree> diff` (and `--staged`) for any *uncommitted* work in that worktree — Phase 0 step 4 flagged it; this is where you actually read it. Use the invocation checkout's `HEAD` (`git diff main...HEAD`) only when the chosen task *is* the current checkout. Read the files most recently touched.
- **Open questions / blockers** — anything the plan or memory flagged as unresolved.

Run the reads in parallel where possible.

Then summarize for the user as bullets — not prose:

- **Where things stand** (1-3 bullets)
- **Open questions / decisions needed** (if any — skip the section if none)
- **Recommended first concrete action** (one bullet, specific: "edit `path/to/file.py:42` to do X", not "start implementing")

End with a hand-off line: "Ready to start with <action>, or want to dig into something else first?"

## What NOT to do

- **Don't survey stale refs or ignore sibling worktrees.** Phase 0 (worktree enum + fetch + ff every checkout) runs first, always — and means *running* the commands, not just intending to. Skipping the pull is how this skill recommends work a VM already finished and pushed; skipping `git worktree list` is how it misses parallel work in another checkout of the same repo.
- **Don't deep-dive multiple candidates in Phase 1.** That wastes context before the user has steered.
- **Don't recommend a task that's already shipped.** Verify status against `git log` and plan-doc state — trackers lag behind reality.
- **Don't skip AskUserQuestion when there are 2+ candidates.** Inline "should I do X or Y?" is the wrong shape here.
- **Don't bootstrap a NEXT.md if it doesn't exist.** That's a wrapup-skill concern. Just note its absence.
- **Don't run this mid-session** when the user is already deep in a task and asks a tangentially-related question. This skill is for the session-opener case.
