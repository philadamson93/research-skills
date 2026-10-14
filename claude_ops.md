# How Claude Code works on VISTA repos

The standard for every VISTA repo. Read it at the start of each session. Specs and plan docs open with
the line `Reference: docs/claude_ops.md`.

## The workflow, start to finish

1. **Open the session.** `/next` if no task is named. Check the start-of-session items below.
2. **Size it.** Small work (reversible in under an hour): ask one or two questions, do it, skip
   to step 6. Bigger work: go on.
3. **Interview.** `/grill` asks me what changes the outcome and writes a one-page spec to
   `docs/plans/`. My confirming it is the approval.
4. **Build.** In auto mode, in this session or a fresh one handed `build docs/plans/<name>.md`.
   Stop before each *Expensive step* I didn't approve in the interview, and hand me its one-line
   command.
5. **Check.** Run the *Done when* checks, then `/review-implementation <spec>` (it runs the
   `evaluator` agent and saves the verdict). Tick the deliverables. Make the what-changed
   explainer with `/explain-plan <spec>`.
6. **Commit and land.** `/commit-review` (which runs `/phi-vet` where it applies), then `/land`
   for branch work.
7. **Close out.** Print the close-out block after each chunk; `/wrapup` at session end.

Details for each step are in the sections below.

---

## How to write to me

Plain English, always — in chat, in questions, in specs, in commit messages. I read this in a
terminal and usually don't have the code in front of me. Write the way you'd explain it across a
desk to someone who knows the research cold and has never opened the repo.

**Do**

- Short, concrete sentences. Say the thing, then stop.
- Lead with the answer or the number. Reasoning after it, if at all.
- Plain verbs: *use*, not *utilize* or *leverage*; *let*, not *enable*; *so*, not *in order to*;
  *about*, not *approximately*.
- Name the actual thing — the dataset, the table, the step, the number that moved — not "the
  relevant artifact" or "this capability".
- Put consequences in units I feel: minutes, dollars, "we'd re-run the embeddings", "the
  leaderboard numbers move", "that's a day of work thrown away".
- Gloss any term I haven't already used, in five words or less, the first time it appears.
- Keep exact names and numbers. `path/to/file.py:42` and "8,538 rows" are precision, not jargon.

**Don't**

- **IMPORTANT: no shorthand I'd have to look up.** Say what a thing does, not what it's called.
  "Check the tests still pass now that main has moved" — not "gate green-gate freshness." If a
  phrase only means something inside these docs, it doesn't belong in a message to me.
- Don't make a code-level noun the subject of something I have to act on — no function names,
  class names, flags, config keys, or schema fields as the subject. Say what it does in English
  and put the identifier in parentheses after, if it genuinely helps.
- No preamble or self-narration: drop "It's worth noting that", "I'll now", "Let's dive in".
- No inflated diction: *robust, seamless, comprehensive, delve, holistic, leverage, utilize,
  facilitate, myriad, plethora*.
- No hedge-stacking ("it may be the case that this could potentially…"). Say it plainly or cut it.
- No rule-of-three flourishes or stacked em-dashes where one clear clause does the job.
- No filler affirmations ("Great question", "Certainly").

**When you ask me something**

- Describe what each choice leads to, not how it works inside. I usually can't see the code.
  Options describe outcomes, never mechanisms.
- Every question must name what changes in the outcome depending on the answer, *and* the default
  you'll take if I shrug. If you can't name the consequence, it isn't a question — decide it and
  record it. (The tiers for what's worth asking are under *Standing rules*.)
- Any multiple-choice question goes through the `AskUserQuestion` tool, not inline prose.

**When you need me to run something**, hand me one line I can paste, never instructions to follow.
The format and the tmux rules it has to survive are under *Which machine to run on*.

The test: read it back as if a person wrote it in a hurry but knew the material cold. If it sounds
like a press release, cut it down. If I answer a question with "what does that mean?", that's a
writing failure, not a misunderstanding.

---

## Start of a session

- Run `hostname`. It tells you which data mounts and GPUs are local to you.
- Check the shared skills repo is current:

  ```bash
  git -C ~/code/research-skills fetch --quiet 2>/dev/null && \
    git -C ~/code/research-skills log HEAD..origin/main --oneline 2>/dev/null | head
  ```

  Behind by even one commit: tell me how far behind, list the commit subjects, and ask before
  pulling `--ff-only`. Up to date, or the path doesn't exist here: say nothing.

- **Fetch before you go looking for anything.** Another machine may have pushed plans, branches,
  or commits since you last synced, so your local refs are stale by default — `main` included.
  Run `git fetch origin` before you search for something another session made, before you check
  out a named branch or commit, and before you tell me it doesn't exist. "Can't find the branch"
  means fetch again. It never means "nobody wrote it, so I'll substitute something similar."

- **Searching a repo may not find its plan docs.** Where `docs/plans` has been moved out of git
  it is an ignored symlink to the shared mount, so `rg` skips it (ignored) and does not follow it
  (a link), and plain `grep -r` and `find` miss it too. `vista-cohort` is there now and the other
  repos are following, so treat this as true everywhere rather than checking per repo. Measured on
  vista-cohort: searching the checkout for a term returns 4 files when the content is really in
  14. An agent that greps and finds nothing concludes the plan does not exist, which is the same
  failure as not fetching.

  **Search the mount, not the checkout** — `rg <term> /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/`
  has no ignore rule and no links in it, and one search covers every repo at once plus the plans
  that only ever lived on the mount. Inside a checkout you need `rg --no-ignore -L`. The in-repo
  path is for *opening a plan you can already name*, never for finding one.

- **Check whether another session is already working in this folder.** VISTA repos are shared
  checkouts: several sessions may sit in the same directory, sharing one working tree and one
  HEAD, so one session's branch switch or reset is instantly visible to the others.

  ```bash
  git -C <repo> status --short          # changes you didn't make?
  git -C <repo> branch --show-current   # a branch you didn't check out?
  git -C <repo> worktree list           # someone else's worktree already open?
  ```

  Also check `MEMORY.md` and `docs/next.md` for branches someone else is on, and treat me
  mentioning another agent as the same signal. If anything looks live, make your own worktree
  before editing (`EnterWorktree`, or `git worktree add`). In a shared tree a `reset`, a broad
  `stash`, or a branch switch can destroy another session's uncommitted work. This has already
  cost three unsaved documents permanently.

---

## Specs

Write down what we're building and how we'll know it's done, not how to build it. The model plans
its own implementation; what I read is the decisions. Plan mode is not part of the workflow
unless I ask for it.

- **Small work** (a fix, a doc change, anything reversible in under an hour): no spec. Ask the
  one or two questions that matter, then do it.
- **Bigger work** (spans sessions, runs on a GPU or VM, writes to PHI data, or needs more than
  about three answers from me): run `/grill`. It interviews me at the level I care about (what,
  why, how we'll know, where it sits, what it costs), then writes a one-page spec to
  `docs/plans/`. The template is in the command.
- My confirming the interview is the approval. No explainer or plan review before the build.
  Approval covers building, not the spec's *Expensive steps*: stop before each GPU run, VM
  hand-off or first PHI write unless I approved that exact run in the interview.
- When a result contradicts the spec: if it changes the results, the cost or what we can conclude,
  stop and ask. Otherwise rethink, keep going, and record what changed. Either way, add it to the
  spec's *Decided* list with the date.
- Where `docs/plans` is in git, commit the spec with the first code that builds it, not before.
  Where `docs/plans` is the ignored symlink to the mount, the spec never enters git; name its mount
  path in that first commit message.

### When the work is finished

- Run every *Done when* check yourself and show what it printed.
- Run `/review-implementation <spec>`: the `evaluator` agent checks the work against the spec from a
  fresh context and the verdict is saved beside the spec's reviews. The builder doesn't grade its
  own work. Fix what it finds, or tell me why not.
- **Tick the deliverables one by one**, each next to the commit or `file:line` that delivers it.
  Anything with no match keeps the spec open, and the brief's stage stays open with it.
- **Hand over a what-changed explainer** with `/explain-plan <spec>`. I don't read markdown. It makes
  a self-contained HTML page on the mount showing what was built (a diagram, a before/after, the
  numbers that moved) and carries the Mac mount write rule. Link it from the PR or close-out block.
- Fix the docs the change made stale. Land branch work with `/land`. Mark the spec
  `Status: Completed (date)` and update `docs/plans/README.md`.

Older plan docs in the long format stay as they are. Finish them on their own terms.

---

## Writing code

- Extend an existing utility rather than building a second version alongside it.
- Write the simplest thing that works. No abstraction or feature nobody asked for yet.
- Put new files in a named directory decided in the spec's *Deliverables*, not the repo root.

---

## Checking your work

This matters more than anything else here.

- Show evidence, not assurances: the command you ran and what it printed.
- A check that cannot fail proves nothing. Work out the expected answer independently of the thing
  you're testing.
- Run the checks yourself. Don't leave assertions for me to run.

---

## Closing out a block of work

When you finish a block — an implementation, a verification run, a review — print exactly this,
the same five labels every time, nothing decorative around it:

```
Program  <name> — stage N of M
Done     <what concretely finished>
Verified <the command you ran and what it printed>
Next     <the one next action>
Yours    <the decision you need from me, or "none">
```

This is not only for session end (`/wrapup` still does that once per session). It fires after every
chunk, so I never have to scroll and ask "what did we do, where did we stop, what's next".

**The block writes, it doesn't only print.** A terminal print dies with the session; the next
session can't read it — which is exactly how I lose the thread across sessions. So when a board and
brief exist for this work (the boards and briefs from the planning layer), the block also:

- upserts this item's board entry with the current stage and the `Next` line, and
- when `Yours` recorded a real decision I made, appends one dated line to the brief's
  `Decided already` ledger.

Until those files exist, just print the block; the writes begin once the board and brief do. That
write is what stops the decision ledger from freezing on the day it was hand-typed.

---

## Which machine to run on

Every machine running Claude Code does the whole job: plan, build, check, commit. There is no
machine that only plans and another that only executes. A session that finds its spec was wrong
revises it where it stands.

The one real difference between machines is hardware. GPU training, embedding generation, and
heavy parallel batch work (linear probes, KNN, bulk preprocessing) need hardware the Mac doesn't
have, so those steps run on whichever box has it.

- Actual hostnames, package-manager rules, and sibling repo paths live in that repo's
  `CLAUDE.md` or `docs/machines.md`, not here.
- Unfamiliar hostname: ask me what that machine can do rather than guessing, then offer to record
  it in the repo so the next session doesn't ask again.
- Running code is allowed on every machine, under the same PHI review that governs commits.
  Claude Code for Education covers the Mac and the project VMs alike.
- A repo may not have `ruff`, `black`, `isort`, `mypy`, or `pytest` installed in its environment
  on this machine. Check the repo's own `uv` environment. That's a setup question, not a ban.
- Data paths may be local or specific to one VM. Confirm a path exists before reading or writing.

**When a step needs a machine you can't run it on yourself** — the GPU box, a host whose
credentials only I have, anywhere without a Claude Code session — the hand-off is **a command I
paste**, not prose telling me what to do. "Log into the GPU box and re-run the embedding job" is
not a hand-off. One line I can paste is. Same rule for anything on this machine you can't do
either, like an interactive `gcloud auth login`.

- **Commit the script, hand over its invocation.** `bash scripts/check_motor_cache.sh`, or
  `SAMPLE=200 uv run scripts/probe_embeddings.py`. The script is versioned, reviewable and
  re-runnable; a block of shell in a chat message is none of those. This is already the pattern —
  `scripts/check_run_vista_02_extract.sh` in `femr-private` is one.
- **Self-contained**: environment setup (`uv sync`, any exports) and the run, in that one command.
  Nobody is watching it, so it judges itself — exit codes, files that must exist and be non-empty,
  numbers in range. Tell me in one line what a pass looks like.
- **Say where to run it.** Hostname first, then the line, then the pass condition.
- It writes results to the shared bucket mount (`su-vista-uscentral1`, mounted on the Mac and on
  the Claude-capable VMs), not into a document. Whichever session needs the numbers reads them
  off the mount.
- Read the results off the mount and write the narrative yourself. For eval runs that means the
  generated HTML at `<results-root>/<version>/<modality>/<dataset>/reports/<model>_<dataset>.html`
  plus the per-task and per-example parquet files. A one-line pointer to results in a backlog or
  `next.md` entry is fine.

### What "pasteable" actually means — I run tmux

Every command you hand me lands in an interactive bash prompt inside tmux. That prompt is not
inert and a multi-line paste does not arrive intact. All four of these have already cost us time:

- **No heredocs and no trailing-backslash continuations.** tmux submits lines early or runs them
  together, and the error that comes back looks like a bug in the work rather than in the paste.
  That burned several rounds of debugging non-problems (2026-09-17).
- **Every line stands alone.** `cd X && cmd` is fine. Setting a variable on one line and using it
  on the next is not — that is where an "unbound variable" error came from. Environment variables
  are a good way to make one line configurable; put them on the same line as the command.
- **No backticks inside double quotes.** In a shell string those are command substitution, not
  markdown quoting, so a progress message that names `git add -A` in backticks actually runs it,
  silently. Single-quote command names, or drop the quotes.
- **No `!!` in a message.** Interactive bash history-expands it even inside double quotes and
  splices my previous command into your text, which only shows up on the day something already
  went wrong. Write `ERROR:` instead, or start the block with `set +H`.

If it won't fit on one line, that is the signal it should have been a committed script.

---

## Git

### Before you commit

- Report which branch you're on. Never assume it's the one you started on.
- Check the branch again in the moment before committing. In a shared checkout another session can
  move HEAD underneath you between starting and committing.
- Tell me if the branch looks wrong for this work.
- Avoid `git reset --hard`, broad `git stash`, and `git checkout -- .` in a shared checkout. They
  act on the whole tree, including another session's uncommitted edits, and work git never staged
  has no saved copy to restore. Move a misplaced commit with `cherry-pick`, `reset --soft`, or by
  moving the branch pointer. If you truly must reset, snapshot the entire tree first, not just the
  files you happened to notice earlier.

### Branches

- Big changes get a feature branch. Documentation updates and small fixes go straight on `main`.
- A purely additive file can also go straight on `main`: a new config, a one-off script, a
  fixture, one new key in a registry-style dictionary. The test is that it only adds something
  nothing else references yet, so it can't break an existing path.
- In `research-skills` itself, a small fix we already discussed — skill wording, a doc correction,
  a hook tweak — goes straight on `main`. Branch here only for a large rewrite or something that
  needs review before it lands.

### Messages

- No AI attribution lines.
- One sentence.
- Split by theme: config in one commit, logic in another, documentation in a third.

### When to commit

- Commit when the work reaches a state worth sharing: an approved spec with its first code, a finished and verified
  change, results ready to use. Or when I ask.
- Running low on context is not a reason to commit. `/wrapup` preserves the session without one.
- Every commit in a medical-data repo goes through the PHI review, including my own read of each
  committed markdown file. Committing on a timer multiplies that cost for no benefit.

---

## What gets committed

Everything committed passes the PHI review, and I personally read every committed markdown file.
Keep that surface small.

- **Commit**: code, approved specs, README and `docs/` updates, write-ups of aggregate numbers.
- **Don't commit**: session notes, verification write-ups, scratch analyses. These live in
  `docs/session/`, which is git-ignored — add it to the repo's `.gitignore` if it isn't already.
  Being ignored also protects them from another session's `reset --hard`.
- **Don't commit yet**: a spec still being revised. Save it to `docs/plans/` immediately, commit
  it with its first code (only where `docs/plans` is in git; see *Specs*).
- **Never commit**: results data — parquet files, HTML reports, metrics tables. Those live on the
  mount. What reaches git is the summary that points at them.

### PHI rules that don't bend

- Never write a patient identifier, a sample row, or report text into any file, committed or not.
  Git-ignoring controls what gets published, not what may be written.
- A git-ignored session note needs no PHI review from me while it stays local. The moment its
  content leaves the secure environment — promoted into a committed doc, pasted into an outside
  system — it needs one, exactly like a commit does.
- The shared bucket mount is inside the secure environment. It's mounted only on the secured Mac
  and the secured VMs, all under the same IRB, so copying onto it is not publishing and needs no
  PHI review (your ruling, 2026-08-27).

---

## Reviews before committing

Use these skills instead of writing review prompts inline. Each one describes itself when you
invoke it, so the short version:

- `/grill` — interview me and write the spec, before building.
- `/review-implementation <spec>` — runs the `evaluator` agent (a fresh-context reviewer) against
  the spec, saves its verdict, and applies the fixes it agrees with, before `/commit-review`.
- `/explain-plan <spec>` — the what-changed explainer, after the build.
- `/review-tests <spec>` — test coverage of uncommitted code, when the change adds new behavior
  worth protecting against regressions.
- `/commit-review` — the commit path. Use this instead of running `git commit` yourself.
- `/phi-vet` — the PHI review. `/commit-review` calls it automatically in repos touching BigQuery,
  OMOP, NeuralFrame, DICOM, EHR, WSI, the pathology bucket, or vista_bench. Never quietly
  substitute an inline scan.

Skip all of these for trivial changes: one-file fixes, doc tweaks, formatting.

Subagents may run code here, under the same PHI rules as the main session. GPU work still goes to
the machines that have GPUs.

---

## Skills

- Expensive skills — multi-agent workflows, large parallel searches, anything that burns a lot of
  context — are never started off a keyword alone. Describe the choice in one sentence and offer
  it through `AskUserQuestion` next to the cheaper options. Spending that budget is my call. Cheap
  skills like `/read-plan` and `/next` run on a direct request.
- Handing work to a subagent: don't pour this session's context into the prompt. Point it at the
  skill or doc it needs and give it just enough to know what to read.
- Building a multi-step workflow: write the skill in markdown first, then the code it calls. The
  instinct is to write a one-off Python script that solves today's problem and then rots. The
  markdown captures the goal, the resources, the success criteria, and when not to use it. Skip
  this layering for small tasks.
- When I do the same multi-step thing by hand twice, offer to turn it into a slash command.

---

## Standing rules

- Sort every decision by what the answer changes, and act on the tier:
  - Changes the results, the cost, or what we can conclude → ask me.
  - Changes only the shape of the code → decide it, say why in the commit message, don't ask.
  - Reversible in under an hour → just do it.
- Whether a failure should fall back or raise is always mine: a silent fallback can hide a real
  error upstream.
- Prefer an existing public skill or agent over writing our own. Copy it into research-skills
  with its source, commit and license noted, and adapt it there.
- When you get something wrong, add the lesson to the repo's `CLAUDE.md` so the next session
  doesn't repeat it.
- Record a non-obvious decision where someone will find it: a short code comment, the commit
  message, or the spec.
