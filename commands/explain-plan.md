---
name: explain-plan
description: Convert a plan doc into a self-contained interactive HTML explanation (Mermaid diagrams, blast-radius map, step accordion, inline feedback widgets, clipboard-export button) and then run a drift-verification pass that reconciles the HTML against the source markdown. Use when a plan is too long or repo-wide for prose review to be productive, or when the user invokes `/explain-plan <path>`. Pairs with `/read-plan` (which opens the source markdown) — `/explain-plan` opens the visual companion. Also offered proactively after substantial plan-doc work as an alternative to `/read-plan`, gated by AskUserQuestion. SKIP for trivial plans, typo-fix passes, or completed plans (this is a planning aid, not a historical record).
---

# explain-plan

Convert a plan doc into an interactive HTML explanation. Plans for repo-wide changes encode dense graph-shaped information (knobs → files → outputs → consumers, sequencing constraints, blast radius) in linear prose. Humans absorb diagrams faster than prose; agents are good at the prose. This skill bridges that gap so the user can review *visually* and direct *editorially*.

## When to use

- User invokes `/explain-plan <path-to-plan>` or `/explain-plan` (auto-detect the most-recently-referenced plan in conversation).
- Right after `/review-plan` finishes substantive edits, as an alternative to `/read-plan` for plans the user reports losing track of.
- When the user says "I'm losing the thread" / "show me visually" / "let me see this as a diagram" about a plan doc.

## When NOT to use

- Plan is trivial (single-file edit, ≤3 steps, no cross-file blast radius).
- Plan is already `Completed` — this is a planning aid for live work, not a historical artifact.
- User has explicitly asked for prose review or is mid-implementation.
- The plan is itself a *doc reorg* plan whose payload is mostly text restructuring (HTML adds no visual signal).

## What to generate

A single self-contained HTML file. **Default output path: sibling to the plan** — `<plan-dir>/<plan-stem>.html`. The HTML is checked into the repo for traceability (NOT gitignored) unless the user overrides. Other locations only if requested.

The HTML embeds:

1. **Header card** — title, status, owner, branch, source-doc link, source-doc SHA-256 (for drift detection), generated timestamp.
2. **TL;DR** — 2–4 sentence framing distilled from the plan's "What you're building" / status preamble.
3. **Repo Map** (Mermaid `flowchart LR`) — the *zoomed-out* view: where this PR sits in the whole repo pipeline. Show upstream sources, config layer, query layer, task modules, output tables, downstream/sibling repos. Color-code by relationship to the PR: bright-yellow with thick border = THIS PR adds; solid amber/green = modified/affected; grey dashed = untouched (Phase-2 deferred, or unrelated task families) — *negative space matters here, it tells the reader what is and isn't in scope*. Place this BEFORE the detailed Blast Radius diagram. Skip the Repo Map if the plan's footprint is genuinely confined to a single layer (e.g., a CSS-only tweak with no module/output blast radius); otherwise include it.
4. **Blast radius diagram** (Mermaid `flowchart LR`) — the *zoomed-in* detail: knobs → files touched → output tables → downstream consumers. Mark Out-of-Scope deferred work with a muted color and a "Phase 2" label.
5. **Order-of-operations diagram** (Mermaid `flowchart TD`) — sequenced steps with status chips (SHIPPED ✅ / PENDING ⏳ / BLOCKED 🛑 / PARTIAL ⚠️). Show inter-step dependencies (e.g., "bundle Step 4 + Step 5 in one commit") as edge labels.
6. **Knobs / contracts card** — for each knob: type, default, allowed values, where it's used. Code blocks for default predicates / signatures. Inline annotations on subtle behavioral defaults (fail-closed validators etc.).
7. **Step accordion** — `<details>`/`<summary>` per step. Closed by default. Each step: description, files touched, verify-gate, and a `<textarea class="section-feedback">` for inline comments. For steps with substeps (like a "Materialize and diff" step with 6a–6f), include a sub-flowchart.
8. **Gotchas accordion** — same shape as steps; closed by default to reduce visual load on first open.
9. **Open Questions panel** — one card per OQ with a `<select>` (Pending / Resolved / Deferred), a `<textarea>` for notes, and the full question prose. These pre-populate the export with `OQ<N>: <status> — <notes>` lines.
10. **Feedback sidebar / footer** — a global `<textarea>` plus a single button `Copy all feedback as Claude prompt`. JS gathers all per-section textareas, OQ statuses, and the global box; formats them as a markdown prompt; copies to clipboard. **Persist all textarea values to `localStorage` keyed by plan-stem + section-id** — first user complaint after using the HTML is invariably "I refreshed and lost everything." Restore on page load; clear when the plan SHA changes (the HTML has been regenerated, old feedback is stale). Show a small pending-count badge on the button (e.g., "Copy feedback (3 pending)") so the user can see they have unsubmitted notes before navigating away.

### Optional sections (case-by-case)

- **Before/after diagrams** — include ONLY when the change reshapes data flow (e.g., a refactor that moves a query layer between repos, an API migration where the call graph changes, an architectural extraction). SKIP for mechanical token substitutions (e.g., "regex literal → Jinja variable in 3 templates") — two near-identical diagrams differing only in node labels have low signal density. The behavioral diff in those cases lives in the verification step's diff queries (Step 6 EXCEPT-DISTINCT, etc.), not in a static visual. When in doubt, ask the user via AskUserQuestion.
- **Step-detail sub-flowcharts** — include when any single step has ≥4 sequenced substeps (like Step 6's 6a–6f); don't bother otherwise.

### Visual design constraints

- **Single file, no build step.** Inline CSS and JS. The only external load is Mermaid via CDN.
- **Readable in dark and light.** Use `prefers-color-scheme` media query; provide both palettes.
- **Mobile-friendly layout** is NOT required — these are reviewed on a laptop.
- **No emojis in body prose.** Status chips (✅ ⏳ 🛑 ⚠️) and Mermaid node labels are the exception — they encode information visually.
- **In-figure color legends.** When a diagram uses ≥3 distinct node styles to encode meaning, include a `subgraph legend["Color legend"]` inside the Mermaid source — disconnected sample nodes, one per style class, with concise labels. Avoid prose-only legends below the figure (small italicized lists) — those force the reader to look away from the diagram to decode color. Place the legend subgraph LAST in the diagram source so it floats to an edge without disrupting the main flow.
- **Legend must enumerate every class actually used.** If the diagram applies an `ext` / `cfg` / `deferred` class to any node, that class needs a legend entry. Missing legend entries are the most common drift complaint after the first user review.
- **Append the color name to each legend label.** "THIS PR adds — new config knobs (cyan)" beats "THIS PR adds (new config knobs)" — readers shouldn't have to match a swatch to text by saccade. The parenthetical color name is a redundant cue but a useful one when colors are subtly different.
- **Pick hues that are visually distinct, not just programmatically distinct.** Yellow + amber are adjacent on the color wheel and read as "the same color, slightly different" to many readers. When a class needs to stand out as the *focus* of the diagram (the PR-add node), pick a hue that is NOT adjacent to any other class — cyan, magenta, or strong rose work well against the typical amber/green/blue/grey palette. Don't use yellow if amber is already in use.

## Mermaid pitfalls

Concrete syntax landmines that have broken diagrams in real plans. Avoid up-front; don't wait for the user to report "syntax error in text, mermaid version X.Y.Z."

- **Never put `{` or `}` in node labels, subgraph titles, or edge labels** — not even single braces. Mermaid's parser treats `{` as a rhombus-node opener even inside quoted strings, and even inside subgraph quoted titles. This breaks placeholders like `{dataset}/{pair_key}` or `{model_a/b}_per_example.parquet` that look perfectly natural in a path-template label. Rewrite as `(dataset)/(pair_key)/` or `(model_a or b)_per_example.parquet` — parentheses inside `[...]` labels are literal text. Same hazard for Jinja `{{ INDEX_FOO }}` — drop braces.
- **Never put `|` (pipe) in node labels** — `|` is the edge-label delimiter in `A -->|label| B`, and the parser gets confused when a pipe appears inside a node's `[...]` label. Replace with `/`, `,`, or the word `or`. E.g., `[results/{ct|ehr|path}/...]` is doubly broken — both `{` and `|` are hazards; rewrite as `[results/(ct, ehr, or path)/...]`.
- **Never put double or triple dashes (`--`, `---`) inside node labels** — Mermaid uses `-->`, `---`, `===` as edge tokens, and a label containing `--verify-against-solo` or `---` (from a separator line) tokenizes ambiguously. Common failure mode: bullet replacement (`• --foo` → `- --foo`) silently creates `---foo` which the parser splits as edge-then-node. Strip leading `--` from labels (drop the CLI-flag dashes when used as a *label*; keep them in the surrounding prose), and avoid `---`/`━━━`/`═══` as visual separators inside labels.
- **Avoid Unicode arrows (`→`, `←`, `↔`) in node labels** — 10.x parsers sometimes choke. Replace with `->`, `<-`, `to`, `vs`, or simply rephrase. (Status chips `✅ ⏳ 🛑 ⚠️` and `▸` *generally* work; arrows specifically don't.)
- **Avoid box-drawing chars (`━`, `═`, `│`) in node labels** as visual separators — same fragility as `---`. Use `<br/><br/>` for visual whitespace or just `<br/>` alone.
- **Edge labels: use pipe syntax `A -->|label| B`**, not `A -- "label" --> B`. Pipe syntax is more permissive about special chars (parens, slashes, commas) and survives parser quirks across Mermaid versions.
- **Dotted arrows with labels: `A -. label .-> B`** (spaces required around the label on both sides). NOT `A -.label.-> B` or `A -.label-->B` — both are malformed-token bugs that 10.x parsers reject silently. Same for thick: `A == label ==> B` (spaces required). Watch for this when you have many `-. <verb> .->` edges with short labels — easy to drop the spaces by reflex.
- **Avoid `•` (bullet) in node labels** if you're seeing parser failures — switch to `,`, `;`, or just rely on `<br/>` for line breaks. `•` usually works but is a known sometimes-fail in older Mermaid versions. **Watch out for blind bullet-replacement**: if you do a bulk `• ` → `-` substitution to fix the bullet issue, you may create new `--` or `---` sequences when `• ` precedes another `-` token (e.g., `• --verify-against-solo` → `---verify-against-solo`).
- **`<br/>` for line breaks in node labels works**; raw `\n` does not. Use HTML-style breaks.
- **Subgraph labels with spaces or punctuation must be quoted**: `subgraph foo["My Label (v2)"]`, not `subgraph foo My Label`. Note: quoting does NOT save you from the `{` hazard inside the label.
- **Wrap multi-line / punctuated node labels in double quotes**: `s1["<b>Slice 1</b><br/>line 2<br/>line 3"]`, not `s1[<b>Slice 1</b><br/>...]`. The quotes harden the label against ambiguity when it contains colons, commas, parentheses, or HTML tags.
- **`class A,B,C classname` is fine**; many node IDs in one assignment is the idiomatic shape.
- **Generation-time validation (run BEFORE opening the file)**: pipe `<pre class="mermaid">...</pre>` blocks to a temp file and grep for every known-bad pattern. Cheap, catches all the common cases:

  ```bash
  awk '/<pre class="mermaid">/,/<\/pre>/' <html> > /tmp/mermaid.txt
  grep -nE '\{|\}'                       /tmp/mermaid.txt   # curly braces (any, not just doubles)
  grep -nE '\[[^]]*\|[^]]*\]'            /tmp/mermaid.txt   # pipe inside node labels
  grep -nE '\-\.[A-Za-z][^.]*\.->'       /tmp/mermaid.txt   # dotted arrow missing spaces
  grep -nE '\[[^]]*---[^]]*\]'           /tmp/mermaid.txt   # triple-dash in node labels
  grep -nE '→|←|↔'                       /tmp/mermaid.txt   # unicode arrows
  grep -nE '━|═|│'                       /tmp/mermaid.txt   # box-drawing chars
  ```

  Every section must return zero hits before opening. If any returns hits, fix and re-run — don't open a broken HTML and force the user to be the parser.

## Inputs

- **Required**: path to plan doc (markdown). Resolve from the skill argument or, if absent, from the most-recently-referenced plan in conversation; fail with a clear message if neither is available.
- **Optional**: output path override. Default is sibling `<stem>.html`.

## Generation flow

1. **Read the plan in full.** Plans are typically 200–500 lines; read directly with `Read`. If the plan exceeds the Read token cap, read in chunks.
2. **Compute the source SHA-256** via `shasum -a 256 <plan-path>` (mac) or `sha256sum` (linux). Embed the full hash in the HTML's `<meta name="plan-sha256">` and the human-visible header (first 12 chars).
3. **Parse the plan structure** — `H2` sections, `H3` subsections, fenced code blocks, links, and tables. Identify:
   - **What you're building** / **Status** / **Owner** / **Branch** (preamble)
   - **Knobs** / **Files you'll touch** (contracts)
   - **Implementation steps** (sequenced)
   - **Gotchas** / **Out of scope** / **Resolved decisions** / **Open questions** (cross-cutting)
   - **Pointers** (links)
4. **Build the diagrams**:
   - Blast radius: entity-level. Nodes are concrete things — file paths, table names, knob identifiers. Edges are "flows into" / "renders" / "consumes." Use `subgraph` groupings.
   - Flow: step-level with status chips.
   - Inset diagrams for complex multi-substep nodes (only if the plan has them).
   - **Group nodes by their call-graph role, not by their filesystem location.** A new orchestrator that *wraps* an existing primitive (e.g., calls `_fit_and_eval` directly while bypassing the outer `run_*` wrapper) is a *meta-orchestrator*, not a peer of the per-modality orchestrators it lives alongside in `eval/`. Putting it in the same subgraph as `run_linear_probe` / `run_knn` / `run_survival` makes the reader assume it's "another per-modality runner" — leading to questions like "shouldn't this feed *into* run_linear_probe?". Instead: put the wrapper in its own subgraph (e.g., `Meta-orchestrator (this plan)`) sibling to but distinct from the per-modality `Orchestrators` subgraph, and label the edge from the wrapped primitive with `calls directly (bypasses run_linear_probe)` or similar to make the call-graph relationship explicit. The diagram is for a fresh reader who has never seen the code — file-system adjacency is irrelevant; what they need is "who calls what."
5. **Write the HTML** to the resolved output path. Use the template structure described above. Inline all CSS and JS; load Mermaid from `cdn.jsdelivr.net/npm/mermaid@10`.
6. **Verification pass** — see next section. Run this BEFORE opening so any drift fixes land before the user sees the file.
7. **Open the file** in the user's default browser — REQUIRED, not optional. Run `open <output-path>` on macOS, `xdg-open <output-path>` on Linux, `start <output-path>` on Windows. Detect platform via `uname -s` if uncertain. The user invoked the skill to *review* the HTML; failing to open it forces an extra manual step. The only exception: if the user explicitly said "just generate, don't open" in the invocation, skip the open. Mention the path in the hand-off message regardless, so the user can re-open it manually if their default app didn't catch the file.

## Verification pass (mandatory in v1)

After writing the HTML, run a drift-reconciliation step. The user explicitly asked for this; do not skip.

1. Re-read both the source `.md` and the generated `.html`.
2. For each major section of the HTML, locate the corresponding plan section. Check:
   - **Coverage**: every plan H2 section is represented OR has a justified omission (e.g., `Implementation history` typically excluded from HTML).
   - **Fidelity**: claims made in the HTML are sourced in the plan, not invented. Paraphrasing is OK; contradiction or fabrication is not.
   - **Status accuracy**: SHIPPED/PENDING markers on steps match the plan's per-step status markers.
   - **Knob/file enumeration**: every knob and every file in the plan's tables appears in the HTML's blast-radius diagram or knobs card.
   - **OQ count**: number of OQs in HTML equals number in plan.
3. Produce a short drift report inline in the chat — bullet points, one per finding. Classes:
   - `MATCH` — section reconciled, no issues (don't list individually; summarize as "Sections N reconciled cleanly").
   - `DRIFT` — HTML and plan disagree. List specifically: "HTML says X, plan says Y at line Z."
   - `MISSING` — plan content not represented in HTML. List with plan line range.
   - `INVENTED` — HTML content not in plan. Highest-priority class — list every instance.
4. If `INVENTED` or `DRIFT` findings exist, offer to fix them in the HTML before handing off to the user.

## Feedback ingestion (when the user pastes back from the clipboard button)

If the user pastes back the clipboard-exported markdown, the format will be:

```
# Feedback on <plan-name>

## blast-radius
<user text>

## step-6
<user text>

## OQ1
Status: Resolved
<user text>

## Overall
<user text>
```

To ingest:
1. Parse the H2 sections.
2. For each section, find the corresponding part of the plan markdown.
3. Classify each comment:
   - **Bug report on the HTML itself** (e.g., "syntax error in mermaid", "this color is wrong", "section is missing") — fix the HTML directly; do NOT touch the plan.
   - **Clarification request** (e.g., "what is X?") — answer in chat; do NOT silently edit the plan unless the answer reveals the plan is genuinely unclear.
   - **Trivial fix** (typo, broken link) — apply to plan directly.
   - **Substantive scope/content change** (e.g., "drop this task family from scope", "rename X to Y") — surface via `AskUserQuestion` before applying, since these often have cross-section ripple effects (status text, blast-radius edges, diff target tables, file enumerations). DO NOT chain-apply across the plan without the user confirming.
4. Regenerate the HTML (the SHA will change; embed the new one).
5. Re-run verification.

**Partial feedback is normal.** Users typically review and submit feedback in chunks (e.g., "I've reviewed sections 1–2, here's feedback, haven't gotten to the rest"). Treat each paste as additive. Don't pressure the user to finish before applying — they can continue reviewing while you apply the chunk. The localStorage persistence in the HTML widget means their unsubmitted feedback on later sections is safe across reloads.

The skill does NOT auto-apply substantive feedback — it requires user confirmation for non-trivial edits per `feedback_*` memories. For trivial fixes (typo corrections, link patches), apply directly.

## Idempotency and re-runs

- Re-running on the same plan: regenerate HTML in place. Diff the old vs new HTML; if structure changed substantively, surface that as a "structure delta" note before handing off.
- If the source plan's SHA-256 differs from the HTML's embedded SHA, the HTML is stale. Warn the user before they review it.
- The HTML is meant to be committed alongside plan revisions; regenerate on every substantive plan edit.

## Iteration mode

This skill is itself iterative — v1 will not be perfect. Patterns to watch for in feedback rounds:
- Diagram nodes too coarse or too fine — adjust granularity.
- Specific sections users keep asking about — promote to top-level cards.
- Specific sections users skip — demote to collapsible or remove.
- Feedback-export format too verbose / too terse — tune the JS.

When the user gives feedback on the *skill itself* (not the generated HTML), edit this SKILL.md.

## Pointers

- `~/.claude/skills/review-plan/` and `~/.claude/skills/read-plan/` — sibling plan skills. Naming and invocation convention follows the verb-plan family.
- Mermaid syntax: <https://mermaid.js.org/intro/> — flowchart, sequence, classDiagram are the useful subset here.
