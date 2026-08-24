Reference: claude_ops.md

# Executor/Mac parity — remove the mandatory deviation hand-back

**Status: Draft** (2026-08-24)

## Goal

`retire-planner-mac-phi-vm-split.md` (landed `main` `bc4ea6e`, same day) already reframed *why*
a VM gets Executor role — GPU/high-throughput capacity the Mac lacks, not PHI/compliance — but
it deliberately left the Executor/Planner **authority** split untouched: "Executor-mode bullets
(fetch-before-survey, fleet classes, deviation classification) stay — those are
compute/coordination concerns, not PHI ones." This plan revisits that scoped-out piece.

Today, a VM/executor session that discovers a **plan-level deviation** (a finding that
contradicts a plan assumption, changes scope, or invalidates the approach) is required to
**STOP and hand back to a Mac/planner session** — write a `⚠️ DEVIATION` block, flip a
`next.md` pointer, wait for a *separate* session on a *separate machine* to pull it, re-plan,
and ship a new handoff doc before the VM can proceed. That mandatory round-trip made sense
when the VM ran under Vertex API (a cost/capability-constrained mode) and only the Mac had
the full interactive planning capability. Both machines now run under the same Claude
subscription (Claude Code for Education) with identical capability — so the asymmetry the
round-trip exists to bridge is gone. Per Phil (2026-08-24): **remove it entirely** — "everything
the planner Mac used to be able to do, the VM can now do too."

**What does NOT change:**
- rad-eval's `dispatcher.py` `require_vertex_phi_env()` gate (its optimizer-loop's dispatched
  `claude -p` sessions still route through Vertex for a separate BAA/PHI reason, untouched by
  the prior plan and untouched by this one).
- Genuinely destructive-action confirmation, PHI gates, and "ask when architecturally
  significant" (Communication Standards) — none of those were specific to the Mac/VM split;
  they apply identically to every session regardless of machine, before and after this change.
- The **one real hardware constraint**: a run on a class-2/3 executor box with **no Claude Code
  at all** (a standalone script on a high-throughput CPU / GPU box) has no agent present to make
  *any* judgment call — a deviation surfacing there still has to be read back by whichever
  Claude-Code box is orchestrating the run, simply because no agent exists there to decide. This
  isn't a Mac-vs-VM authority question; it would be true even between two VMs.

## Approach

### Phase 1 — `claude_ops.md`

- **Machine-Aware Operating Mode → Executor mode, "Classify findings, don't improvise"
  bullet**: remove "a plan-level deviation — STOP, document it, and hand back to the planner"
  and "Don't broad-plan or major-rewrite without confirmation." Replace with: a plan-level
  deviation is now handled the same way Core Principle #2 already asks *any* session to handle
  a direction change — reconsider the approach, revise it, document the revision (so the trail
  is legible to whoever reads it next), and continue in the same session. Keep "when uncertain,
  escalate" but reframe it as asking the user directly (live, via `AskUserQuestion`) rather than
  routing to a different machine's session. Keep the in-lane-correction / decision-gate language
  (class 1 / class 2) — those aren't changing.
- **Plan Document Structure → "Anticipated forks" bullet**: "Unanticipated findings that
  contradict the plan are *deviations* — `/vm-handoff`'s Deviation workflow routes those back
  here for revision" assumes the hand-back model. Reword to: the executor resolves them inline
  and documents the revision — no round-trip required, though the plan doc itself should still
  get updated to describe the current recommendation (so a *later* reader isn't misled by a
  now-stale approach).
- **Plan Document Structure → "Handoff phasing" bullet**: "stop/deviation routing" in the
  per-phase field list — keep the field (a phase can still note "if X happens, do Y inline"),
  drop the implication that routing means *leaving* the machine.

### Phase 2 — `VISTA/code/CLAUDE.vm.md`

- **"Stay in Executor lane" bullet**: remove "Don't broad-plan or major-rewrite without user
  confirmation... planning happens on the Mac." The VM can now plan and re-plan same as the
  Mac; ordinary judgment still applies (ask when a call is genuinely architecture-significant —
  same standard `claude_ops.md` Communication Standards already asks of every session, not a
  VM-specific gate). Same caveat as before: no automatic path onto the actual VM — Phil copies
  the edited file over by hand.

### Phase 3 — `commands/vm-handoff.md` (the bulk of the change)

Rewrite the **Deviation workflow** section (currently ~100 lines: the class table, the VM→Mac
procedure, the Mac→VM procedure, "Superseding, not editing"):

- **Class table**: class 3's "Who handles it" changes from *"Executor STOPs, documents the
  finding, hands back"* to *"Executor (if Claude-Code-capable) revises the approach inline,
  documents the deviation for the record, and continues"*; "Round-trip" changes from **Yes** to
  **No — unless the executing box has no Claude Code at all** (see below). Consider renaming
  the class from "plan-level deviation" to something that doesn't presuppose a hand-back, e.g.
  "plan revision" — flagged as an open question below rather than decided here.
- **Replace "VM → Mac (class 3 surfaced during a run)"** with an inline-resolution procedure:
  pause, reconsider the approach (same discipline as re-entering plan mode), decide — ask the
  user directly if attended and genuinely uncertain, otherwise use best judgment — document the
  deviation and the revised approach in the same run's record (readback section / commit
  message), and continue running the revised approach in the same session. No `next.md` pointer
  flip to BLOCKED, no new vm-status doc, no supersede — unless the executor concludes it
  actually can't proceed at all (as opposed to *won't* without asking), which is the one case
  still worth a real stop.
- **Keep, reframed**: the no-Claude-Code-box case. When compute runs on a high-throughput CPU /
  GPU box with no agent present, a deviation there still can't be resolved on the spot — it
  has to be read back by the Claude-Code box orchestrating the run before any revision decision.
  State this as a hardware-presence fact, not a Mac-vs-VM authority rule.
- **"Mac → VM (planner invalidates a shipped handoff)"**: this direction is about async
  coordination between two already-running things (one on stale instructions), not about who's
  *allowed* to decide — likely stays close to as-is. Re-read it during implementation to confirm
  nothing in its wording still assumes "the Mac is the only place a redirect can originate."
- **"Superseding, not editing"**: this is a documentation-hygiene practice (don't rewrite
  history), independent of the authority question — keep it for the narrower set of cases where
  a genuinely new vm-status doc still gets authored (e.g., the no-Claude-Code-box case, or a
  deviation big enough that starting a fresh doc is clearer than a long inline note). Most class-3
  findings will no longer spin a new doc at all now that they resolve inline in the same run.
- **Readback template** (`## VM run results`): the `⚠️ DEVIATION (class 3)` line's framing
  ("why it blocks · escalating to planner") needs to change to something like "why the approach
  changed" — it's no longer inherently blocking.
- **Resume block**'s `<next leg>` field: "a Stop fired → re-plan on the Mac" is no longer the
  only outcome of a fired Stop — most now resolve inline in the same session; reword.
- **"What this skill deliberately does NOT do"** bullet mentioning "the class-1/2/3 deviation
  taxonomy": update in passing to match whatever the class-3 rename lands on (see open question).

### Phase 4 — `references/verification-and-handoff-design.md` (light touch)

Line ~25-26's ownership statement ("does not own... the class-1/2/3 deviation taxonomy...
those are owned by `/vm-handoff`") stays true regardless — no rewrite needed beyond matching
whatever `/vm-handoff` renames class 3 to, if anything. The "expected-vs-unexpected envelope"
section (§2) is a *complementary* discipline (pre-declare benign-vs-bug so fewer things reach
class 3 *at all*) — genuinely unaffected by this plan; leave as-is.

## Files to Modify

- `claude_ops.md` — Phase 1 (Executor mode bullet, two Plan Document Structure bullets)
- `VISTA/code/CLAUDE.vm.md` — Phase 2 (not a git repo; direct edit + manual copy to the VM)
- `commands/vm-handoff.md` — Phase 3 (Deviation workflow section, readback template, resume
  block, "does NOT do" bullet)
- `references/verification-and-handoff-design.md` — Phase 4 (one cross-reference line, only if
  the class-3 name changes)

## Open Questions

1. **Rename "class 3 — plan-level deviation" to something that doesn't presuppose a hand-back
   (e.g. "plan revision"), or keep the name and just change what happens when one fires?** A
   rename is clearer going forward but touches every place the term is quoted (the table, the
   readback template line, the "does NOT do" bullet, this doc). Leaning toward renaming since
   "deviation" reads as inherently bad/blocking, but Phil's call.
2. **Does the "Superseding, not editing" discipline survive as a *recommended* practice for
   big-enough revisions even outside the no-Claude-Code-box case, or only for that one case now?**
   i.e., if a VM session mid-run decides the approach needs a genuinely large pivot, should it
   still be encouraged to spin a fresh vm-status doc (clean historical record) even though it's
   no longer *required*, or is inline-in-the-same-doc always sufficient now?
3. **Does this change anything about `/review-implementation` / `/review-tests`'s "Defensible
   Deviations" language** (Codex-review findings that diverge from the plan but look
   intentional)? Current read: no — that's a different kind of "deviation" (a review-time
   classification of *already-written* code vs. the plan), unrelated to this VM/Mac
   execution-time mechanism. Flagging so a reader doesn't conflate the two "deviation" uses
   across skills.

## Verification & VM handoff

No GPU/throughput work here — docs-only change, verified structurally, not via a VM handoff.

- Grep `commands/vm-handoff.md`, `claude_ops.md`, `VISTA/code/CLAUDE.vm.md` post-edit for
  residual "hand back to the planner" / "STOP... escalating to planner" / "planning happens on
  the Mac" phrasing that Phase 1-3 should have replaced.
- Confirm the no-Claude-Code-box exception is still stated somewhere in `commands/vm-handoff.md`
  after the rewrite (it's the one case that's supposed to survive) — a grep for "no Claude Code"
  should still hit inside the (reframed) Deviation workflow section, not just in the executor-
  fleet-class description elsewhere in the file.
- Read the full rewritten Deviation workflow section end-to-end once done and confirm it reads
  as a coherent, self-consistent procedure (not a patchwork of edited fragments referencing a
  hand-back that no longer exists elsewhere in the same section).

## Landing & cleanup

- **Branch**: `feat/executor-mac-parity-remove-deviation-handback` (this worktree).
- **Landing gate**: Phil's explicit read + approval (same class of stakes as the prior PHI-
  posture plan — this is core operating discipline inherited by every VISTA repo). No VM gate.
- **Merge sequence**: single-branch — land at the end, prune branch + worktree.
- **Cleanup on land**: mark this plan `Status: Completed`; add its row to `docs/plans/README.md`;
  remind to hand-copy `CLAUDE.vm.md`'s new content onto the actual VM (no automatic path, same
  as the prior plan's Phase 5 note).
