---
name: debate
description: Structured adversarial debate for major design decisions where reasonable people disagree, the stakes are high, and the wrong choice is expensive to reverse. Spawns two agents concurrently — one advocating each option — that prepare codebase-grounded opening arguments (800–1200 words, no generic reasoning), then the main agent moderates 2–4 rounds raising use-case-specific tradeoffs, then synthesizes into a decision document at `docs/decisions/`. **ONLY invoked when the user explicitly types `/debate ...` — NEVER auto-triggered from trigger cues alone.** When a design fork surfaces in conversation that looks like a debate candidate (cross-repo architecture, build system choice, data contract design, config system design, major API surface change, "I keep going back and forth on this"), surface the option via `AskUserQuestion` first ("would you like to spin up `/debate` for this?") rather than spawning the parallel advocates unilaterally — debates are expensive in context and time, and the user owns the decision to spend that budget.
---

# debate

Major design decisions where reasonable people disagree benefit from a structured adversarial debate rather than the main agent reasoning solo. The pattern surfaces tradeoffs the main agent might rationalize away under "let's just pick one and move on" pressure.

## Invocation discipline (load-bearing)

**This skill is never auto-invoked.** Even when trigger cues are obvious, do not spawn the parallel advocates without an explicit user `/debate ...` invocation or an explicit "yes, run debate" answer to an `AskUserQuestion` you've raised.

The reason: each debate spends ~6,000–10,000 tokens across two parallel agent contexts plus 2–4 moderation rounds. That's a real budget item and the user owns the decision to spend it. A debate the user didn't ask for is a debate they wouldn't have authorized — even if the design fork is real.

When a debate-shaped fork surfaces in conversation:
- Name the fork in one sentence ("this looks like a real A vs B fork — monorepo vs multi-repo for the foo extraction")
- Offer `/debate` as one option in an `AskUserQuestion`, alongside lighter-weight alternatives (e.g., "decide inline, document rationale", "defer", "ask me a few clarifying questions first")
- Wait for the user's pick before spawning anything

## When to use (after user has authorized)

Trigger cues that make a fork debate-worthy:

- Cross-repo architecture (monorepo vs multi-repo; what to extract into a sibling repo)
- Build system choices (Bazel vs Make vs Just; uv vs poetry vs pip-tools)
- Data contract design (single wide table vs per-task tables; long vs wide schema; one parquet per modality vs one per task)
- Config system design (json vs yaml vs Python; flat vs nested; per-task vs unified)
- Major API surface changes (REST vs RPC; single endpoint vs many; sync vs async)
- Anywhere the user says "I keep going back and forth on this" or similar

Invocation form: `/debate <option-A> vs <option-B>` (or free-form: `/debate should we extract X into its own repo?`).

## When NOT to use

- Routine implementation choices (variable names, file locations, helper extraction)
- Decisions where one option is obviously dominant — the debate spends context on a foregone conclusion
- Reversible decisions that can be experimented with cheaply (just try one)
- Cases where the user already has a strong preference and is asking for confirmation, not adjudication
- Single-agent reasoning problems (debugging, code review) — those are not multi-option forks

## Flow

1. **Frame the fork.** Restate the decision as A vs B (or a small enumerated set ≤4). If the framing is unclear or the options aren't named, use `AskUserQuestion` to confirm before spawning agents — getting the framing wrong wastes both advocates' context budgets.

2. **Spawn two advocates concurrently** — one `Agent` tool call per side, **both in the same message so they run in parallel**:
   - Each gets the full plan / repo context relevant to the decision: file paths, current architecture, any constraints the user has named, sibling-repo precedents.
   - Each is instructed to advocate for its assigned option with codebase-grounded reasoning — concrete `file:line` references, specific failure modes that have happened in this repo or sibling repos, sibling-repo precedents, named constraints.
   - Opening argument target: **800–1200 words**. Long enough to develop the case, short enough that the main agent can hold both arguments in context for the moderation rounds.
   - **Forbid generic reasoning** ("monorepos are easier to refactor"). Every claim must cite a specific file, function, recent commit, sibling repo, or named constraint. If an advocate's argument could be rewritten verbatim for a different codebase, it's not codebase-grounded.

3. **Moderate 2–4 rounds** as the main agent. Read both opening arguments, then raise the load-bearing tradeoffs the user cares about — not everything in the openings. Each round: short prompt (1–3 questions), each side responds in 200–400 words. Stop when arguments stop generating new information or you hit 4 rounds, whichever comes first. Resist the urge to keep going for symmetry — diminishing returns are real here.

4. **Synthesize a decision document.** Save to `docs/decisions/` (or wherever the project keeps decision records — bootstrap that directory if it doesn't exist). Structure:
   - **Decision** — what was chosen, in one sentence
   - **Context** — what the fork was, why it surfaced now
   - **Options considered** — A and B (or more) with the load-bearing strengths/weaknesses from the debate
   - **Rationale** — why the chosen option won under the criteria the user named
   - **Consequences** — what this commits the project to, and what's deferred or made harder
   - **Open questions** — anything the debate surfaced that needs follow-up

5. **Hand off** by surfacing the decision doc path and inviting the user to read it before implementation. If the user has `/read-plan` available, mention they can use it on the decision doc.

## Output discipline

- The decision document is the artifact, not the chat transcript. Keep the chat-side summary brief — point at the file.
- Do not commit the agent transcripts to the repo unless the user asks. They're a means to the synthesis, not a deliverable.
- If the debate ends inconclusively (both options have strong claims under different criteria), surface that explicitly — "the choice depends on whether the project prioritizes X or Y" — rather than picking arbitrarily. An honest "it depends, here are the conditions" is more useful than a forced verdict.

## Asking discipline

Use `AskUserQuestion` once at the start if the fork framing is unclear, and once at the end if the synthesis surfaces a sub-decision the user needs to make. Do not pause for the user during the moderation rounds themselves — the moderation IS the value-add of this skill, and pausing dilutes it.
