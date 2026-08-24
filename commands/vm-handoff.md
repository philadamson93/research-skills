---
name: vm-handoff
description: Author and close the planner-Mac → executor-VM handoff round-trip. TRIGGER on explicit /vm-handoff, or proactively (offer via AskUserQuestion) after planner-Mac work that has never executed and needs first-time validation on real VM data. SKIP when the run is results-producing (linear-probe / KNN / cross-modality sweeps — read from the auto-generated HTML, not smoke-gated) or trivial. Auto-detects author (Mac) vs readback (VM) mode by `hostname` per claude_ops.md Machine-Aware Operating Mode. In author mode it DERIVES the runnable docs/vm-status/<date>-<sha>.md doc from the plan's "Verification & VM handoff" criteria (renders them, never invents), names the executor-fleet class the work targets (Claude-Code CPU / high-throughput CPU / GPU) and — for non-Claude-Code compute — the box the readback runs on, and gives you a tiered sign-off gate before landing; in readback mode it appends the VM's run results into the SAME doc, closing the loop. Reuses /review-plan, /phi-vet, and /commit-review rather than duplicating them.
---

# vm-handoff

## The principle

VISTA work is split across machines: the **planner Mac** authors plans, configs, and
scripts but lacks **GPU / high-throughput capacity**; the **executor
side** holds that compute and runs everything GPU-bound or throughput-heavy. That executor side
is not one box — it's a small **fleet of capability classes** (a Claude-Code CPU box, a
high-throughput CPU box, a GPU box; see *Which machine* below), and part of the handoff is
naming which class the work targets. Every non-trivial change therefore crosses a machine
boundary at least once, and the thing that crosses it is a *handoff doc*: the planner's
statement of what to run, **where**, how to tell it worked, and when to stop and hand back.

The success criteria of that handoff are **not invented here** — they live in the plan. A
VISTA plan's *Verification & VM handoff* section (per `claude_ops.md` Plan Document
Structure) already states what runs on the VM and the per-step **Expected** / **Stop**
criteria, and `/review-plan` already audited them. This skill's author mode **renders** that
already-reviewed section into a concrete, copy-paste-runnable `docs/vm-status/<date>-<sha>.md`
instance; its readback mode records the VM's results back into the same doc. The durable
*spec* is the plan; the vm-status doc is one dated *execution* of it.

This skill does not decide *who* is planner vs executor — that's `claude_ops.md`'s
Machine-Aware Operating Mode. It consumes that posture and does the handoff.

## Where this sits in the workflow chain

```
PLANNER MAC
  plan mode → docs/plans/X.md  (incl. "Verification & VM handoff": Expected/Stop)
  /review-plan X            ── audits design + success criteria + handoff-readiness (fresh-agent implementability)
  …implement (author configs/scripts — GPU/high-throughput runs still need the executor fleet)…
  /review-implementation X · /review-tests X   ── structural audits; route here only if VM-repo + plan needs a handoff
  /vm-handoff  ───────────▶ RENDER the plan's criteria into docs/vm-status/<date>-<sha>.md
       │                    (implementation is still UNCOMMITTED at this point)
       └ tiered success-criteria gate (your sign-off) ──┐
       └ offers → /commit-review (bundles doc + impl) → /phi-vet → push  ────┘
EXECUTOR VM
  pull, run the steps
  /vm-handoff (readback)   ── results appended into the SAME doc
       └ offers → /phi-vet → /commit-review → push
BACK ON MAC
  pull → clean = done · a Stop fired = re-enter plan mode (revise the plan, loop)
```

**Reuse, never duplicate.** Upstream criteria-review is `/review-plan` on the plan; landing
each leg is `/commit-review → /phi-vet`; an independent *re-audit of the criteria* is
`/review-plan` on the **plan** (where they live and where its design-shaped lenses fit), not
on the rendered vm-status doc. The only things this skill uniquely adds are the
**render-from-plan** step, the **tiered sign-off gate**, and the **loop-back** when a Stop fires.

## Mode dispatch — `hostname` decides

Run `hostname` first and resolve the machine's role from the repo's machine posture (its
`CLAUDE.md` / machine registry, per `claude_ops.md` Machine-Aware Operating Mode):

- **Planner (the Mac; no GPU/high-throughput capacity)** → **Author mode** (render the handoff doc).
- **Executor (the Claude-Code CPU box with data + credentials)** → **Readback mode** (append
  results). This is the only executor class that can run this skill — the readback append is
  Claude-driven, so the high-throughput CPU and GPU boxes (no Claude Code) never invoke it;
  when the compute ran on one of those, a human ran it there and the readback here reads its
  results / logs (see *Which machine* below).
- **Unknown hostname** → do not guess. Ask which role applies, and offer to record it
  wherever the repo declares its posture (its `CLAUDE.md`, or a `docs/machines.md` if it
  uses one — `claude_ops.md` is deliberately non-prescriptive about which) so the next
  session doesn't re-prompt.

State the detected mode in one line before acting (`On <mac-host> → planner → author mode`)
so a mis-detection is visible and correctable.

## Which machine — the executor fleet

The executor side is a **fleet of capability classes**; author mode names which one each step
targets, and renders it into the handoff header. The full taxonomy + routing is the canonical
spec's (`references/verification-and-handoff-design.md` §4) — don't restate it; the operational
essentials:

- **Claude-Code CPU** — the default / interactive executor: smoke tests, structural readback,
  BQ / OMOP queries, moderate eval. **The only class that runs this skill's readback.**
- **High-throughput CPU** — bulk preprocessing, linear-probe / KNN parallelization,
  core-saturating batch. No Claude Code.
- **GPU** — model training, embedding generation, GPU-only tests. No Claude Code.

**Run-machine ≠ readback-machine.** When a step runs on the high-throughput-CPU or GPU class,
the *run* happens there but the *readback* is done on the Claude-Code CPU box (or the Mac reads
results). Render both — the machine switch is its own phase — so the executor isn't left
assuming one box does both. If the plan's *Target machine* field is missing, **recommend** a
class from the routing above rather than defaulting silently, and flag it for the sign-off gate.

**The non-Claude-Code box runs a script, not the doc.** The vm-status doc is Claude-driven
(read → run → interpret Expected/Stop → append); a high-throughput-CPU or GPU box has no agent
to run it, so author mode never renders *"pull the branch and run this doc"* for those classes.
Instead, for the non-Claude-Code leg it renders **(1)** a pointer to the committed standalone
runner script — env setup (`uv sync` + any env exports) **and** the run in one command, a plan
deliverable per the canonical spec (`references/verification-and-handoff-design.md` §4) — and
**(2)** an operator run-block (checkout branch, preconditions, the one command, where results
land). The Claude-Code readback then reads the script's outputs / logs / HTML. Default to
**phasing** — a small Claude-driven smoke on the Claude-Code CPU box, then the standalone full
run on the high-throughput-CPU / GPU box — so the correctness-critical gates get Claude's eyes
before the throughput run. (See *Non-Claude-Code full run — render an operator run-block* under Author mode's skeleton.)

---

## Finding a handoff — the locator (both directions)

A handoff's doc **and** its `next.md` pointer live wherever the work was committed — often an
**unmerged feature branch**, but just as often `main`. Either way the receiver's local copy of that
ref is **stale**: the commit was pushed from another machine, so a receiver who surveys their
checkout — or runs `git log --all` / `git ls-files` / a file-exists check **before fetching** —
finds nothing and wrongly concludes the handoff was never authored, when the commit was simply
never fetched. `main` is **not** the safe case: the VM's local `main` is behind the Mac's
just-pushed `main` exactly as much as any feature branch. This is the most common handoff-*finding*
failure (the handoff itself is fine); head it off by **printing where the artifact lives — and the
one command that syncs to it — in every relay, both directions**:

- **Lead with a locator line.** Every handoff artifact (the doc header) and every relay message
  (the author→VM hand-off, the VM→Mac readback) opens with the coordinates, so the receiver can
  reach the artifact *before* they have it:
  `REPO <repo> · BRANCH <branch> (fetch first — `main` included) [or WORKTREE <path>] · DOC docs/vm-status/<name>.md · SHA <sha | set-at-commit>`.
- **Fetch before you survey — unconditionally, `main` included.** A receiver looking for a handoff
  runs `git fetch origin` *first*, then checks out the named branch / SHA (or `git worktree add`s
  it), and reads the artifact there. A ref that was never fetched is invisible to `git log --all` /
  `git ls-files` / a file-exists check, so "can't find the branch / doc" on a stale tree means
  *fetch + check the named ref* — never *it was never authored, so improvise a plausible substitute*.
  The stale-tree trap is not specific to feature branches: a `<sha>` pushed from another machine is
  absent from *this* machine's `main` too until it fetches.
- **Name the repo explicitly.** Cross-repo handoffs (producer in one repo, consumer + handoff doc
  in another) make "which repo" ambiguous — state it, so the receiver searches the right tree
  rather than the sibling.
- **The pointer is branch-local too.** The `next.md` pointer is committed on the *same* unmerged
  branch as the doc, so a receiver on `main` won't see the pointer either — which is why the
  locator travels in the **relay message** that crosses the machine boundary, not only inside the
  branch. Once the branch merges to `main`, both become visible the ordinary way.

---

## Author mode (planner Mac)

### Phase A1 — Confirm this handoff is warranted

`/vm-handoff` is for work that **has never executed** and needs first-time validation on
real data. **Skip** (say so and stop) when:

- The run is **results-producing** — linear-probe / KNN / cross-modality sweeps. Per
  `claude_ops.md`, those are read directly from the auto-generated HTML
  (`<results-root>/<version>/<modality>/<dataset>/reports/<model>_<dataset>.html`) and the
  on-disk parquets; a one-line pointer in `next.md` to the launch command is enough.
- The change is **trivial** (doc tweak, single-file fix, formatting).

When proactive (not an explicit `/vm-handoff`), offer the skill via `AskUserQuestion`
rather than authoring unprompted.

### Phase A2 — Locate the plan and its criteria (the source of truth)

Find the canonical `docs/plans/<...>.md` this work implements and read its **Verification &
VM handoff** section — that is what you render. Two checks:

- **Criteria present?** If the plan has no Verification & VM handoff section (or it's a bare
  "run it and see"), the plan isn't handoff-ready. **Do not invent criteria here.** Point
  back: add the Expected/Stop section to the plan (so `/review-plan` can audit it — its
  handoff-readiness lens checks the section is present & implementable), *then* return to
  `/vm-handoff`. Inventing un-reviewed
  success criteria at handoff time is the exact failure this chain prevents.
  - **Ad-hoc exception:** for a genuine one-off with no plan (e.g. *"does this script even
    import on the VM"*), you may author a minimal handoff without one — but **state the
    Expected/Stop criteria inline and flag them as ad-hoc (not plan-derived, not
    `/review-plan`-audited)** so the un-reviewed status is explicit on the page. If the smoke
    grows past a one-off, promote it to a plan and re-derive.
- **Plan reviewed?** If a `docs/plans/reviews/<plan-stem>-feedback.md` exists unprocessed,
  surface it once (like `/read-plan` does) before rendering.

Then auto-capture the header facts by reading git / shell (metadata, not running project
code — allowed on the Mac):

- **Date** — `date +%F`. **Branch** — `git branch --show-current`.
- **Commit-state honesty** — the most-dropped field. If the work under test is **already
  committed**, capture `git rev-parse --short HEAD` and name the doc `<date>-<sha>.md`. If
  it's **uncommitted on the Mac**, say so: *"authored this session, never executed — commit
  + push before pulling on the VM; SHA set at commit time"* and name it
  `<date>-<descriptor>.md`. Never write a SHA that doesn't exist yet as if the VM can check
  it out. **Descriptor-named docs are permanent** — don't rename them to a SHA after the
  commit (real practice keeps the descriptor name); the prior-handoff link and the `next.md`
  pointer use the descriptor name too. Reserve `<date>-<sha>.md` for work that is *already*
  committed when you author the handoff.
- **Prior-handoff link(s)** — the most recent `docs/vm-status/*.md` this continues, so the
  lineage of what-ran-when is walkable from this doc alone.
- **Target machine** — read the plan's *Target machine* field and carry its executor class
  (Claude-Code CPU / high-throughput CPU / GPU) into the header. If the plan omits it,
  **recommend** a class from the *Which machine* routing rather than defaulting silently, and
  surface it at the sign-off gate. When the run class has no Claude Code (high-throughput CPU /
  GPU), also name the **readback** machine (the Claude-Code CPU box) — the run and readback split.

### Phase A3 — Render the doc (one doc per session)

Author **one** doc per handoff session at `docs/vm-status/<date>-<sha>.md`, translating the
plan's Verification & VM handoff section into copy-paste-runnable steps. It is
self-contained: the executor never *has* to read the plan to run it (it links the plan for
depth, but states what to run inline). Skeleton:

```markdown
Reference: docs/claude_ops.md

# VM <verb> — <one-line scope>, <version>

**Status: Handoff to VM** (<date>)
**Branch:** `<branch>` (<pinned SHA, or "commit+push first, SHA set at commit time">)
**Locator:** REPO `<repo>` · BRANCH `<branch>` — **`git fetch` first** (even on `main`; or WORKTREE `<path>`) · this doc `docs/vm-status/<name>.md`. Reach it: `git fetch origin && git checkout <branch> && git pull --ff-only` (shared / dirty checkout, or non-ff → `git worktree add ../<repo>-<slug> <sha>`). <— the coordinates a receiver needs to find this doc *and* the code before they have either (see *Finding a handoff*).
**Machine posture:** authored on the planner Mac. Everything below has **not yet executed** on the target executor class — run it on the **<executor class>** box (`<vm-host>`, holds <data it needs>). <If that class has no Claude Code: "Run there; read results back on the Claude-Code CPU box `<readback-host>`.">
**Target machine:** <executor class per step/phase — e.g. "Steps 0–2 Claude-Code CPU; Step 3 GPU (train), readback on Claude-Code CPU"> <— from the plan's Target machine field
**Plans:** [`<plan-stem>.md`](../plans/<plan-stem>.md#verification--vm-handoff) <— criteria source of truth
**Prior handoffs:** [`<date>-<sha>.md`](./<date>-<sha>.md) (omit if first)

## Why this doc
<What changed, what has never run on real data, and what a clean result unblocks — 1 paragraph.>

## Step 0 — get the artifacts onto the VM
```bash
cd <repo>
git fetch origin && git checkout <branch> && git pull --ff-only   # fetch FIRST — local <branch> is stale, even on main
git rev-parse --short HEAD   # must show <sha>; if not, the fetch didn't land the handoff — do not proceed on a stale tree
uv sync --extra dev
```
**Expected:** clean checkout at the intended SHA (`git rev-parse --short HEAD` == `<sha>`); lockfile resolves.
**STOP:** none — pure setup.

## Step 1 — <name>   (rendered from the plan's Expected/Stop for this step)
```bash
<exact, copy-paste-ready command(s) with full paths / flags / env>
```
**Expected:** <exit 0; `<path>` exists & non-empty; metric in sane range; skip-log correct>
**STOP:** <the named halt-and-report conditions. `STOP: none — <reason>` only for steps with no project-specific halt.>

## Step N — ...

## Step <final> — launch the full run (optional; Claude-Code CPU box only; only after smoke is clean)
```bash
<the real run command — e.g. the sweep script>
```
**Expected:** launches; results land at `<results-root>/.../reports/*.html` + parquets.
**STOP:** none — this step *points at* the launch; its results are read from the HTML, **not** pasted into this doc (per `claude_ops.md`). Omit entirely if there is no "real run" beyond the smoke. **If the full run lands on a non-Claude-Code box, drop this step and use the operator run-block below instead.**

## Report back
<What the VM appends on readback: per-step pass/fail, tracebacks, decision-gate outcomes,
counts. What to read from HTML instead of pasting. NO PHI.>

## VM run results
_(left empty by the planner; the executor fills this in readback mode)_
```

Every runnable step carries **both** an Expected block and a Stop line (escape hatch:
`STOP: none — <reason>`). See "Expected vs Stop" below; these should be *traceable to* the
plan's criteria, not freshly authored.

**Multi-repo handoff:** keep it **one doc**, but give Step 0 a checkout block per repo (pin
each repo's branch / SHA explicitly) — cross-repo SHA ripple is exactly why the lineage
belongs in a single place.

**Multi-machine handoff:** when steps span executor classes (e.g. preprocess on
high-throughput CPU → train on GPU → eval on Claude-Code CPU), label **each step** with its
class and treat every machine switch as a phase boundary (per the plan's *Handoff phasing*).
Name the readback box wherever the run box has no Claude Code, so no step is left assuming one
machine does both the run and the Claude-driven readback.

**Non-Claude-Code full run — render an operator run-block, not Claude steps.** When the full run
lands on a high-throughput-CPU or GPU box (no Claude to interpret Expected/Stop), **replace the
optional Step-final above** with an **operator run-block** that points at the committed
runner script (canonical spec §4). Keep the judgment-heavy smoke as Claude-driven steps *above*
this block, gated by a STOP, so the throughput run only launches on a clean smoke:

````markdown
## Full run — operator run-block (high-throughput CPU / GPU `<vm-host>`, no Claude Code)
On `<vm-host>` (no Claude — a person runs this):
```bash
cd <repo>
git checkout <branch> && git pull        # precondition: <what must already be landed>
bash scripts/run_<x>.sh                   # handles `uv sync --extra <...>` + the run end-to-end
```
**Precondition:** <what must exist before launch — landed masters, prior smoke PASS>.
**Results land at:** `<results-root>/.../reports/*.html` + parquets — read back on the
Claude-Code CPU box `<readback-host>` (or the Mac reads the HTML). Not pasted into this doc.
````

The `scripts/run_<x>.sh` runner (env setup + run in one command) is a **committed plan
deliverable** — authored on the Mac during implementation and listed in the plan's *Files to
Modify* (the Mac can write scripts it can't run). As with the Step-final, this block only
*points at* the launch: the run's **results still firewall out per §3 / Phase A1** (read from the
HTML, a one-line `next.md` pointer) — the handoff is warranted by the smoke + new code being
gated, not by the results-producing run itself. If instead the plan chose the
**fully-standalone self-gating** shape (no Claude-driven smoke; every gate baked into the script
as an exit-non-zero assertion), there are no Claude steps: **omit the skeleton's Step 0 / Step
1..N** — the whole handoff is this operator run-block plus the committed script, with the readback
reading the script's exit code + logs.

### Phase A3.5 — Tiered success-criteria gate (your sign-off)

Before landing, surface the criteria for your input — sized to the handoff's complexity:

- **Simple handoff** (a few steps, no decision gates, single repo) → **lightweight
  sign-off**: present the Expected/Stop criteria compactly via `AskUserQuestion`
  (Approve / Revise / Independent review). Cheap eyeball, you stay the gate.
- **Complex handoff** (decision gates, cross-repo SHA ripple, many steps) → in the same
  `AskUserQuestion`, **offer (recommended) to re-audit the criteria at their source: `/review-plan`
  on the plan**, where the criteria live and its design-shaped lenses fit. (Pointing
  `/review-plan` at the rendered vm-status doc works mechanically but yields design-flavored
  findings, not "are these steps runnable / are the Stops complete" — so audit the plan, and
  let this gate confirm the render is faithful and copy-pasteable.)

Revise → edit and re-surface. Approve → Phase A4.

### Phase A4 — Wire the pointer, then offer to land

- Add a **one-line pointer** in the repo's tracking doc (`docs/next.md`, else `next.md`,
  else `NEXT.md` — same precedence as `/next`; create `docs/next.md` if none exists):
  `- VM smoke pending: [docs/vm-status/<date>-<sha>.md](...) — <one-line what>`. Pointer in
  the tracking doc; substance in the handoff doc (pointer-style discipline, like `/wrapup`).
- **Carry the locator in the relay, not only the doc.** The pointer *and* the handoff doc both sit
  on the unmerged branch (see *Finding a handoff*), so whatever crosses to the VM — the
  `AskUserQuestion` hand-off, the message you relay — states `REPO · BRANCH (fetch first) · DOC path`
  explicitly, so the executor lands on the branch and finds the doc instead of surveying `main` and
  reporting "missing."
- Then **offer the next step** via `AskUserQuestion`: run `/commit-review` now, or stop
  here. This is the **single** commit-review for the whole change: because the handoff doc
  was authored while the implementation is *still uncommitted* (`/review-implementation` ·
  `/review-tests` route work that needs a VM handoff to `/vm-handoff` **before** the
  commit-review phase, when the repo uses a Mac/VM split),
  `/commit-review` lands the doc **and** the code it documents (the configs/scripts/tests) in
  **one** PHI-vet + push — not a second cycle after the code already landed. That bundling is
  the reason `/vm-handoff` runs before `/commit-review`, not after. Don't auto-fire it —
  offer it (per `claude_ops.md` Skill Composition). (`/commit-review` escalates to `/phi-vet`
  in medical-data repos — though on the planner Mac `/phi-vet` is inert per its machine gate,
  so the real PHI scan is the VM readback leg, Phase R2.)
- **Print the resume block last** — once the `/commit-review` offer resolves (committed, or
  declined), the final output is the copy-paste **resume block** (see *Resume block* below):
  the same locator, reprinted at the very end so it's the last thing on screen for Phil to
  paste into the VM session that runs this handoff.

---

## Readback mode (executor VM)

The VM ran what the doc said. Close the loop **in the same doc** — one doc per session,
author-then-readback. Do not start a new file or route results to a sibling.

### Phase R1 — Fill `## VM run results`

Under the doc's `## VM run results` heading (create it if the doc predates this skill and
lacks one), append a stamped section:

```markdown
## VM run results — readback on `<hostname>`, <date> · REPO `<repo>` · BRANCH `<branch>` @ `<sha>` (pushed to `origin/<branch>`)
<When compute ran on a different (no-Claude-Code) box, name it too: "compute on `<gpu/ht-cpu-host>`, readback on `<claude-code-cpu-host>`" — so a split run's two machines are both on the record.>
- **Step 0:** ✅ checked out `<sha>`, sync clean.
- **Step 1:** ✅ / ❌ <outcome vs the Expected block; if ❌, the traceback or failing eyeball>
- **Step N:** ...
- **Decision gates (class 2):** <which branch the data selected, with the number that decided it>
- **In-lane corrections (class 1):** <any mechanical fixes made inline, so the planner sees them on pull>
- **⚠️ DEVIATION (class 3):** <expected vs found · why it blocks · escalating to planner> — only if one fired
- **Net:** <smoke clean → cleared to launch the full run · BLOCKED on deviation → back to planner>
```

Record each result **against its Expected block** (so go/no-go reads at a glance), and
**honor every Stop**: if a Stop fired, halt and report it here — do **not** improvise past
it, pick a fallback, or "fix" a planning-level problem. That is the Executor-lane rule from
`claude_ops.md`; the Stop conditions are its concrete teeth. When a Stop reveals the plan
*itself* is wrong, that's a **class-3 deviation** — see *Deviation workflow* below for how
it routes back to the Mac (the blocked doc is never edited to fix the plan).

### Phase R2 — PHI gate the readback (medical-data repos)

The VM touches real medical data; the readback is the likeliest leak point. Before
committing the results, run **`/phi-vet`** (or honor its gate hook): **no** patient
identifiers, sample rows, accession/DICOM UIDs, clinical dates, or report text — only
counts, metrics, pass/fail, and tracebacks scrubbed of data. Read large results from the
HTML / parquets; never paste them in.

### Phase R3 — Offer to land, then update the pointer

**Offer** (via `AskUserQuestion`) to run `/commit-review` (which escalates to `/phi-vet` in
medical-data repos) to push the results section. On landing, update the `next.md` pointer's
status (`VM smoke pending` → `VM smoke PASS <sha>` / `BLOCKED — see doc`). The planner pulls
and reads the round-trip from one file.

Finally, **print the resume block last** (see *Resume block* below) — the locator reprinted
as the copy-paste block, as the final output after the `/commit-review` offer resolves, so the
Mac side can pull and continue from one paste (smoke clean → land / launch full run; a Stop
fired → re-plan).

---

## Resume block — print last, after the commit-review offer (both legs)

The last thing `/vm-handoff` prints — in **both** author mode (after Phase A4's commit-review
offer) and readback mode (after Phase R3's) — is the **locator as a copy-paste resume block**,
so Phil can paste it straight into the next session (Mac → VM for the author leg, VM → Mac for
the readback leg) and land on the right branch + doc without re-deriving them. It's the same
locator already in the doc header (*Finding a handoff*), reprinted at the very end so it's the
last thing on screen. Same field format as `/wrapup`'s resume block, so both skills speak one
language:

```
Resume ▸ <repo>   → <next leg>
  REPO   <repo>
  BRANCH <branch>   [WORKTREE <path>]
  DOC    docs/vm-status/<date>-<sha>.md
  SHA    <pinned sha | set-at-commit | ⚠ UNPUSHED>
  SYNC   git fetch origin && git checkout <branch> && git pull --ff-only   # run FIRST, always — local <branch> is stale; DOC+code live in <sha>. verify: git rev-parse --short HEAD → <sha>
```

- **`<next leg>`** — author mode: `run on <executor class> (<vm-host>)` (name the readback box
  too when the run class has no Claude Code). Readback mode: `pull + read back on the Mac`, or
  `launch full run on <box>` when the smoke cleared, or `re-plan on the Mac` when a Stop fired.
- **BRANCH / WORKTREE** — the branch the doc lives on (`main` or a `feat/…`), plus
  `[WORKTREE <path>]` when a worktree holds it. The branch name is a coordinate, **not** a
  freshness signal — the receiver still fetches first (see SYNC), `main` included.
- **DOC** — the `docs/vm-status/<...>.md` this session authored or read back.
- **SHA** — `set-at-commit` when the offer was declined / still uncommitted, `⚠ UNPUSHED` when
  committed but not yet pushed, else the pushed short SHA. Print the block even when the user
  declined the commit-review — with the honest un-landed SHA — so the coordinates travel anyway.
- **SYNC — the runnable first action, always printed (`main` included).** The receiving session
  lands in a **stale checkout**, so the block carries the exact command to sync *before* surveying
  git, and the receiver runs it verbatim first. A `<sha>` committed on another machine is absent
  from this session's local `<branch>` until it fetches — so "can't find the branch / the DOC file"
  means *hasn't fetched yet*, and the fix is to fetch, not to invent a plausible-looking substitute.
  Shared / dirty tree, or `--ff-only` can't fast-forward → reach the SHA in a worktree instead of
  `reset --hard`: `git worktree add ../<repo>-<slug> <sha>`. When SHA is `⚠ UNPUSHED` /
  `set-at-commit`, origin has nothing to fetch yet → render the SYNC line as
  `⚠ nothing on origin yet — push from <box> first`, so the receiver waits rather than fetching a ghost.

## Deviation workflow — when a finding contradicts the plan

Execution surfaces things planning didn't foresee. Every finding — VM-side during a run, or
Mac-side after a handoff shipped — is classified by one question, *does it change the design
or the Expected/Stop criteria?*, and routed accordingly:

| Class | What it is | Who handles it | Round-trip |
|---|---|---|---|
| **1 — in-lane correction** | Mechanical / local; design + criteria unchanged (wrong path, missing env var, fixture regen) | Executor fixes inline, records it under **In-lane corrections** in the readback | No |
| **2 — decision-gate** | A fork the plan *anticipated*; the Stop says "if X → A else B" | Executor picks the branch, records the deciding number | No (pre-authorized) |
| **3 — plan-level deviation** | Contradicts a plan assumption, changes scope, or invalidates the approach | Executor STOPs, documents the finding, hands back | Yes |

**Bright line (1 vs 3):** if the finding changes what *Expected/Stop* means, it's class 3.
The executor **self-classifies and fixes only obvious class-1 mechanical issues**; **when
uncertain, escalate** (`claude_ops.md` forbids the executor major-rewriting without
confirmation). If the session is live, surface the finding to the user rather than deciding
silently. The more forks the plan pre-encodes as class-2 decision gates, the fewer class-3
round-trips — anticipating likely deviations is a plan-authoring discipline, not a handoff one.

### VM → Mac (class 3 surfaced during a run)

1. **VM:** STOP. Write a `⚠️ DEVIATION (class 3)` block in `## VM run results` — *expected vs
   found, why it blocks* — flip the `next.md` pointer to **BLOCKED**, push. Do **not** fix
   the plan; the finding travels back in the readback (that is its home — no separate
   findings log).
2. **Mac:** pull, read the finding, **re-enter plan mode** with it as the input
   (`claude_ops.md` Core Principle #2 — re-enter plan mode when direction changes).
3. **Mac:** revise the plan's approach + *Verification & VM handoff* criteria; `/review-plan`
   audits the delta (its handoff-readiness lens re-checks the criteria section).
4. **Mac:** `/vm-handoff` renders a **new** vm-status doc that **supersedes** the blocked one
   (see below), linking it as a prior handoff.
5. **VM:** runs the new doc.

### Mac → VM (planner invalidates a shipped handoff)

- **VM not yet started** → supersede: render a new vm-status doc, mark the old one
  superseded, flip the `next.md` pointer. **The live handoff is always the newest
  non-superseded `docs/vm-status/*.md`** — the VM confirms that before launching.
- **VM mid-run** → the planner flags direction-changed; the executor halts at the next safe
  step (treat as a Stop), reports where it got to in the readback, and the supersede flow
  takes over. Cross-machine signalling is async via git — the `next.md` pointer status and
  the superseded header are the source of truth, not a live channel.

### Superseding, not editing

A blocked or invalidated doc is **never edited to carry the revised plan** — it is the
historical record of a run that hit a wall. The revision is a *new* doc:

- New doc header: `**Prior handoffs:** [<blocked-doc>](...) — superseded; see its DEVIATION block`.
- Blocked doc gets a top banner: `> **Superseded by [<new-doc>](...)** (<date>) — <one-line why>`.

One doc per run, lineage walkable both directions. This is why findings live in the readback
(step 1 above): the supersede chain *is* the record of what reality taught the plan.

## Expected vs Stop — the discipline this skill enforces

Every runnable step carries **both**, traceable to the plan's criteria; the skill does not
finalize a step that lacks either (escape hatch: explicit `STOP: none — <reason>`, which
turns a forgotten Stop into a conscious decision):

- **Expected** = *what a correct run looks like* — the executor's self-check for "go." Render
  it as the `**Expected:**` block (older hand-written docs label it `**Eyeball:**` — same
  concept; standardize new docs on `Expected` so the readback's "record against the Expected
  block" matches the page). Always substantive: exit codes, files that must exist & be
  non-empty, metric ranges, skip-logs. Without it, the executor can't tell a clean pass from
  a silent corruption.

- **Stop** = *the named conditions under which the executor halts and reports instead of
  pushing forward.* Three flavors:
  - **Precondition stop** — "if an embedding is missing → generate it or drop that config
    *before* the sweep."
  - **Failure stop** — "AUROC pinned at 0.5 → path/extraction bug, STOP"; "if the fail-fast
    guard test does *not* go red, the wiring is broken, STOP."
  - **Decision gate** — "if metric X < threshold → Design A, else Design B": a fork the
    executor *can* resolve inline (record which and why), versus one it must escalate.

  Without a Stop, the executor improvises past a real problem — exactly the failure
  `claude_ops.md` warns against ("don't assume fallbacks are preferred — they can mask
  upstream errors"). `STOP: none — pure setup` is legitimate for setup steps; a
  *consequential* step (a smoke run, a gate) lacking a Stop is the bug this skill prevents.

## What this skill deliberately does NOT do

- **Decide planner vs executor roles** — that's `claude_ops.md` Machine-Aware mode.
- **Own the machine taxonomy or the class→host binding** — the executor-fleet classes and the
  routing live in the canonical spec (`references/verification-and-handoff-design.md` §4), and
  the concrete class→host binding is repo-local (its `CLAUDE.md` / machine registry). This skill
  only *renders* the plan's *Target machine* field (and *recommends* a class when the plan omits
  it, flagged at the sign-off gate) — it does not invent the taxonomy.
- **Author or audit the design** — the success criteria live in the plan's *Verification &
  VM handoff* section and are reviewed by `/review-plan` (whose verification-design pass audits
  them against the canonical spec, `references/verification-and-handoff-design.md`); this skill
  renders them. If the plan lacks the section, fix the plan (add the section; `/review-plan`
  audits it), don't invent here. When the plan has a **Handoff phasing** sub-block, render the *next* phase's
  steps from it — the spec owns plan-time strategy selection; this skill keeps the operational
  mechanics (rendering, the tiered sign-off gate, Expected/Stop enforcement, the class-1/2/3
  deviation taxonomy, supersede).
- **Carry eval results** — results-producing runs go to HTML/parquets per `claude_ops.md`;
  the handoff doc is smoke / verification only. It *may* point at the launch command for the
  real run once smoke is clean (real docs do — via the optional Step-final on a Claude-Code box,
  or the operator run-block when the run is on a non-Claude-Code box), but the results themselves
  are read from the HTML, never pasted in.
