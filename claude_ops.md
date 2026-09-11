# How Claude Code works on VISTA repos

The standard for every VISTA repo. Read it at the start of each session. Plan docs open with
the line `Reference: docs/claude_ops.md`.

---

## How to write to me

Plain English, always — in chat, in questions, in plan docs, in commit messages. I read this in a
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
- Any multiple-choice question goes through the `AskUserQuestion` tool, not inline prose.

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

## Planning

- Plan before writing code. Iterate until the plan is solid, then build.
- Read the existing docs and code first. Find what already exists before proposing something new.
- Say what you're building and why.
- Ask me "is anything here ambiguous?" It catches requirements I left out.
- A wrong fast answer costs more than a right slow one. Think it through.
- Go back to planning when the direction changes: the approach won't work, a new constraint turns
  up, the job is bigger than it looked, the design has a problem, or you're simply unsure.

### Saving a plan

Plan mode can only write to its own scratch file, never to `docs/plans/`. So:

1. Exit plan mode. That approves the plan's content, not the implementation.
2. Save it to `docs/plans/` with a name that says what it is, not `plan_01.md`.
3. Stop and ask me before building. No task lists, no code, no edits.
4. Don't commit a plan while it's still changing. Commit once I've signed off, so it costs one
   PHI review instead of one per draft.

### What a plan contains

```markdown
Reference: docs/claude_ops.md

# [What this is]

## Goal
What we're building, and why.

## Approach
How.

## Files to Modify
Each path and what changes there. For a new file, name the directory it goes in, and flag
any directory that doesn't exist yet.

## Open Questions
What's still ambiguous.

## Verification
How we'll know it worked:
- What runs, in order, and where. Name a specific machine only when the step needs a GPU or
  heavy parallel compute.
- Per step, what a good result looks like: exit code, a file that must exist and be non-empty,
  a number inside a stated range.
- Per step, what should make you stop and come back to me.
- Any fork you can see coming — a number near a threshold, an optional path — decided in
  advance ("above 0.8 do A, otherwise B") so it resolves while you work instead of costing a
  pause. A finding that contradicts the plan is not a handoff: rethink it, write down what
  changed, keep going.
- If a step needs hardware with no Claude Code on it, name its script under *Files to Modify*
  and give that script its own success criteria here.

## Landing & cleanup
- The branch this lands on, or "straight on main" for docs and small fixes.
- What must be true before it merges: reviewed, any GPU step actually run and checked,
  PHI-reviewed. Name any other branch that has to land first.
- Merge order when several branches are involved: small and foundational first, big renames
  last unless something depends on them.
- What gets retired afterward: the branch, its worktree, the plan's status line, the tracker
  entry, and anything extra like scratch directories or temporary tables.
```

### When a plan is finished

- Land branch work with `/land`, following the plan's landing section. Don't merge or delete
  branches by hand. For work that went straight on `main`, do the three steps below yourself.
- Fix the documentation the change invalidated: stale paths, command examples, imports, links.
- Mark the plan `**Status: Completed** (date)`.
- Update the table in `docs/plans/README.md`.

---

## Writing code

- Look for an existing utility before writing a new one. Extend what's there rather than building
  a second version alongside it.
- Write the simplest thing that works. No abstraction you don't need yet, no feature I didn't ask
  for, nothing built for a future that may not arrive.
- Decide where a file lives while planning, and put that in *Files to Modify*. Don't default to
  the repo root. When a second or third file appears around one concern, give it a directory and
  say why in one line.
- Re-use and "don't build it until you need it" pull against each other. Judge the clear cases
  yourself: a one-off script stays inline, the third caller in one module earns an extracted
  function. When it's a genuine coin flip, ask me with `AskUserQuestion` — before drafting if the
  plan's shape depends on it, otherwise in the plan's *Open Questions*. Don't paper it over with
  "I'll extract it later if needed."

---

## Checking your work

Give yourself something that tells you pass from fail. This matters more than anything else here.

- Every plan states how we'll know it worked in its *Verification* section, so I review those criteria alongside it.
- Show evidence, not assurances: the command you ran and what it printed, the test output, the
  file that appeared.
- A check that cannot fail proves nothing. Work out the expected answer independently of the thing
  you're testing.
- Run the checks yourself and bring me the results. Don't leave assertions for me to run.

---

## Which machine to run on

Every machine running Claude Code does the whole job: plan, build, check, commit. There is no
machine that only plans and another that only executes. A session that finds its plan was wrong
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

**When a step needs hardware that has no Claude Code session on it**, the deliverable is one
script I can paste onto that box and run. Nobody is watching it, so it has to judge itself.

- Self-contained: environment setup (`uv sync`, any exports) and the run, in a single command.
- It writes results to the shared bucket mount (`su-vista-uscentral1`, mounted on the Mac and on
  the Claude-capable VMs), not into a document. Whichever session needs the numbers reads them
  off the mount.
- It checks its own results: exit codes, files that must exist and be non-empty, numbers in range.
- Read the results off the mount and write the narrative yourself. For eval runs that means the
  generated HTML at `<results-root>/<version>/<modality>/<dataset>/reports/<model>_<dataset>.html`
  plus the per-task and per-example parquet files. A one-line pointer to results in a backlog or
  `next.md` entry is fine.

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

- Commit when the work reaches a state worth sharing: an approved plan, a finished and verified
  change, results ready to use. Or when I ask.
- Running low on context is not a reason to commit. `/wrapup` preserves the session without one.
- Every commit in a medical-data repo goes through the PHI review, including my own read of each
  committed markdown file. Committing on a timer multiplies that cost for no benefit.

---

## What gets committed

Everything committed passes the PHI review, and I personally read every committed markdown file.
Keep that surface small.

- **Commit**: code, approved plans, README and `docs/` updates, write-ups of aggregate numbers.
- **Don't commit**: session notes, verification write-ups, scratch analyses. These live in
  `docs/session/`, which is git-ignored — add it to the repo's `.gitignore` if it isn't already.
  Being ignored also protects them from another session's `reset --hard`.
- **Don't commit yet**: a plan still being revised. Save it to `docs/plans/` immediately, commit
  it after sign-off.
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

- `/review-plan <plan>` — design review of a plan, before building.
- `/review-implementation <plan>` — uncommitted code against the plan, before `/commit-review`.
- `/review-tests <plan>` — test coverage of uncommitted code, when the change adds new behavior
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
- Skills can point at each other. Where two overlap, reference the canonical one instead of
  copying its text, so they don't drift apart.
- Handing work to a subagent: don't pour this session's context into the prompt. Point it at the
  skill or doc it needs and give it just enough to know what to read.
- Building a multi-step workflow: write the skill in markdown first, then the code it calls. The
  instinct is to write a one-off Python script that solves today's problem and then rots. The
  markdown captures the goal, the resources, the success criteria, and when not to use it. Skip
  this layering for small tasks.
- When I do the same multi-step thing by hand twice, offer to turn it into a slash command.

---

## Standing rules

- Ask me about: what to build and how it should behave, anything ambiguous, decisions that shape
  the architecture, anything where a wrong assumption wastes work, whether a failure should fall
  back or raise (don't assume a fallback — it can hide a real error upstream), and what's worth
  testing before you write tests.
- Decide yourself: variable names, code patterns, internal structure, ordinary refactoring,
  obvious bug fixes.
- When you get something wrong, add the lesson to the repo's `CLAUDE.md` so the next session
  doesn't repeat it.
- When a pattern recurs, write it into the right `docs/` file.
- Record a non-obvious decision where someone will find it: a short code comment, the commit
  message, or the plan.
- Start a fresh session for unrelated work.
- Match the rigor to the stakes. A prototype can be loose; production changes get the full
  treatment.
