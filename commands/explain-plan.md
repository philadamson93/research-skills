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
- **The user pastes back the clipboard export** — a blob starting `# Resume: apply explain-plan feedback` or `# Feedback on <plan>`. Route to *Feedback ingestion* below; resolve the plan from the resume header first (fresh session → read the plan doc + related context, `/next`-style; already in flight → apply against the plan you already hold).

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
10. **Feedback sidebar / footer** — a global `<textarea>` plus a single button `Copy all feedback as Claude prompt`. JS gathers all per-section textareas, OQ statuses, and the global box; formats them as a markdown prompt — **prefixed with a resume header** so a *fresh* session that receives the paste can bootstrap itself (plan path + branch + `plan-sha`, plus a one-line read-the-plan instruction; exact format in *Feedback ingestion* below) — then copies to clipboard. **Persist all textarea values to `localStorage` keyed by plan-stem + section-id** — first user complaint after using the HTML is invariably "I refreshed and lost everything." Restore on page load; clear when the plan SHA changes (the HTML has been regenerated, old feedback is stale). Show a small pending-count badge on the button (e.g., "Copy feedback (3 pending)") so the user can see they have unsubmitted notes before navigating away.
11. **Node drill-down panel (OPTIONAL — opt-in per generation; default OFF)** — Mermaid nodes that represent *changing* entities (kind `added` / `modified` / `deferred`) become drillable via double-click; `untouched` / `external` nodes are not drillable (the cursor stays default, so the pointer affordance itself encodes "this box is where the change lives"). Authors can opt in an unchanged-but-load-bearing node with `forceDrillable: true`. Dblclick opens a side panel with kind chip + plan-anchor jump chips (cheap, embedded) plus a **"Generate detail" button**. The button POSTs the drill prompt to a local relay (`research-skills/relay/explain-plan-relay.py`, default `http://127.0.0.1:7237`) that wraps `claude -p`; the markdown response is rendered inline in the panel and cached to `localStorage[\`drill::${planSha}::${nodeId}\`]`. **If the relay isn't running, the button falls back gracefully to clipboard** (copies the prompt, toast tells the reader how to start the relay). **Detail is generated on-the-fly per node the reader inspects — NOT precomputed at HTML-generation time.** See `## Node drill-down (double-click)` below for the contract, prompt template, and relay wiring. **Generation cost (why this is opt-in):** drill-down adds noticeable time and token spend at HTML-generation. Claude has to hand-author a `nodeManifest` entry (label + kind + plan-anchors) for every drillable diagram node — typically 20–40 entries cross-referenced against the plan's `data-section` IDs, plus three additional verification classes (ORPHAN_NODE, ORPHAN_MANIFEST, BROKEN_ANCHOR). Expect roughly an extra 1–3 minutes and a few hundred lines of generated JS. **When generating, ALWAYS surface this trade-off before turning drill-down on** — via `AskUserQuestion` with the cost stated plainly ("Drill-down adds ~1–3 min of generation time and per-node Claude round-trips when the reader inspects a node — include it?"). Default the recommendation to OFF unless the user explicitly requested drill-down (e.g., `/explain-plan <path> --drill`, "include drill-down", "make the nodes clickable"), or the plan is genuinely large (≥ 3 diagrams AND ≥ 25 distinct drillable nodes), in which case lean ON. When turning drill-down ON, **mention the relay in the hand-off message**: "Drill-down is wired to the relay at `RELAY_URL` — run `python research-skills/relay/explain-plan-relay.py` in a spare terminal before double-clicking nodes, or the panel will fall back to clipboard."

### Optional sections (case-by-case)

- **Before/after diagrams** — include ONLY when the change reshapes data flow (e.g., a refactor that moves a query layer between repos, an API migration where the call graph changes, an architectural extraction). SKIP for mechanical token substitutions (e.g., "regex literal → Jinja variable in 3 templates") — two near-identical diagrams differing only in node labels have low signal density. The behavioral diff in those cases lives in the verification step's diff queries (Step 6 EXCEPT-DISTINCT, etc.), not in a static visual. When in doubt, ask the user via AskUserQuestion.
- **Step-detail sub-flowcharts** — include when any single step has ≥4 sequenced substeps (like Step 6's 6a–6f); don't bother otherwise.
- **Review history table** — include when the plan has been through one or more independent reviewer passes (detectable from a "Provenance" / "Review history" section in the markdown, or from sibling `docs/plans/reviews/<plan-stem>-*.md` artifacts). Render a table near the top (right after TL;DR) with columns `Pass | Reviewer | Verdict | Key findings surfaced | Applied to plan`, one row per pass, linking each reviewer artifact. Surface user-driven architectural pivots (e.g., a decision that supersedes a prior RD) as their own row with a distinct "Pivot" verdict chip. This is the highest-signal section for a reader trying to understand *how the plan reached its current shape* — a plan revised across 3+ passes is otherwise opaque about which decisions are settled vs fresh. SKIP for plans with no reviewer history (a freshly-scoped plan has nothing to tabulate). Keep each cell terse; the reviewer artifacts hold the detail.

### Visual design constraints

- **Single file, no build step.** Inline CSS and JS. External loads are Mermaid + `svg-pan-zoom` (both via CDN — see the pan/zoom requirement below).
- **Readable in dark and light.** Use `prefers-color-scheme` media query; provide both palettes.
- **Mobile-friendly layout** is NOT required — these are reviewed on a laptop.
- **No emojis in body prose.** Status chips (✅ ⏳ 🛑 ⚠️) and Mermaid node labels are the exception — they encode information visually.
- **Diagrams must be pan/zoom-able.** Mermaid's default render is a static SVG that fills its container — fine for small diagrams, useless for the 12-node repo maps and phase flows this skill typically produces. Wrap each `<pre class="mermaid">` in a fixed-height container (e.g. `height: 520px; overflow: hidden`) and after Mermaid renders, attach `svg-pan-zoom` to the resulting `<svg>`. Provide per-diagram controls (Reset zoom/pan, Toggle fullscreen) and a small hint label ("scroll to zoom • drag to pan") so the affordance is discoverable. Reasonable bounds: `minZoom: 0.3, maxZoom: 8, fit: true, center: true`. ESC key exits fullscreen. **Implementation notes:** load `svg-pan-zoom@3.6.x` from `cdn.jsdelivr.net`; set `mermaid.initialize({ startOnLoad: false, flowchart: { useMaxWidth: false } })` and call `mermaid.run({ querySelector: 'pre.mermaid' })` explicitly after wrapping containers, then strip Mermaid's inline `style="max-width:..."` from each rendered `<svg>` (svg-pan-zoom needs to control sizing). Re-fit on window resize and on fullscreen toggle (call `inst.resize(); inst.fit(); inst.center()` with a small `setTimeout` after the class change so layout settles first).
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
- **NEVER use a reserved keyword as a node ID** — this is the highest-frequency "Syntax error in text" that the grep suite below does NOT catch (it inspects label *contents*, not IDs). Banned IDs: `end`, `call`, `class`, `click`, `style`, `link`, `href`, `graph`, `subgraph`, `direction`, `flowchart`, `default`, `linkStyle`. The two that bite most: **`call`** (it's the click-interaction keyword `click X call fn()`) and **`end`** (subgraph terminator). Real incident (2026-06): a blast-radius node `call["convert_dicom_to_nifti..."]` failed to render across three fix attempts because the author kept inspecting label punctuation; the ID itself was the bug. Use a descriptive non-keyword instead (`cvt`, `convNode`, `warnLog`). When auto-deriving IDs from file/function names, prefix or suffix them (`n_call`, `call_`) so a name collision with a keyword is impossible.
- **Never put a bare `<`, `>`, `<=`, or `>=` in a label** — Mermaid feeds labels through an HTML parser, so a bare `<` opens a phantom tag and the diagram dies. `"mismatch <= tol"` breaks; the only `<`/`>` it tolerates are the literal `<br/>` / `<b>` tags you intend. Rewrite comparisons in words (`"at or below tol"`, `"fewer than 2"`) or HTML entities (`&lt;`, `&le;`, `&gt;`). Note `-->` / `-.->` edge arrows are fine — the hazard is `<`/`>` *inside `[...]` labels*.
- **Subgraph titles are parsed MORE strictly than node labels** — parentheses, slashes, and `+` that are perfectly safe inside a quoted *node* label (`x["a (b) / c"]` renders) will break a quoted *subgraph title* (`subgraph s["a (b) / c"]` fails) on 10.x. Keep subgraph titles to letters, digits, spaces, and commas: `subgraph s["Out of scope, Phase 2"]`, not `["Out of scope (Phase 2 / elsewhere)"]`. (This is *in addition* to the `{`-brace hazard, which breaks both.)
- **Edge labels: use pipe syntax `A -->|label| B`**, not `A -- "label" --> B`. Pipe syntax is more permissive about special chars (parens, slashes, commas) and survives parser quirks across Mermaid versions.
- **Dotted arrows with labels: `A -. label .-> B`** (spaces required around the label on both sides). NOT `A -.label.-> B` or `A -.label-->B` — both are malformed-token bugs that 10.x parsers reject silently. Same for thick: `A == label ==> B` (spaces required). Watch for this when you have many `-. <verb> .->` edges with short labels — easy to drop the spaces by reflex.
- **Avoid `•` (bullet) in node labels** if you're seeing parser failures — switch to `,`, `;`, or just rely on `<br/>` for line breaks. `•` usually works but is a known sometimes-fail in older Mermaid versions. **Watch out for blind bullet-replacement**: if you do a bulk `• ` → `-` substitution to fix the bullet issue, you may create new `--` or `---` sequences when `• ` precedes another `-` token (e.g., `• --verify-against-solo` → `---verify-against-solo`).
- **`<br/>` for line breaks in node labels works**; raw `\n` does not. Use HTML-style breaks.
- **Subgraph labels with spaces or punctuation must be quoted**: `subgraph foo["My Label (v2)"]`, not `subgraph foo My Label`. Note: quoting does NOT save you from the `{` hazard inside the label.
- **Wrap multi-line / punctuated node labels in double quotes**: `s1["<b>Slice 1</b><br/>line 2<br/>line 3"]`, not `s1[<b>Slice 1</b><br/>...]`. The quotes harden the label against ambiguity when it contains colons, commas, parentheses, or HTML tags.
- **`class A,B,C classname` is fine**; many node IDs in one assignment is the idiomatic shape.
- **Generation-time validation (run BEFORE opening the file)**: extract `<pre class="mermaid">...</pre>` blocks and grep for every known-bad pattern. Cheap, catches the common cases — but see the hard limit below:

  ```bash
  # Extract label/body content only (drop the <pre> wrapper lines) so the <pre tag isn't a false <-hit.
  awk '/<pre class="mermaid"/{f=1;next} /<\/pre>/{f=0} f' <html> > /tmp/mm.txt
  grep -nE '\{|\}'                              /tmp/mm.txt                 # curly braces (any)
  grep -nE '\[[^]]*\|[^]]*\]'                   /tmp/mm.txt                 # pipe inside node labels
  grep -nE '\[[^]]*\(\)[^]]*\]'                 /tmp/mm.txt                 # empty () inside labels (reads as round-node)
  grep -nE '<[^b]'        /tmp/mm.txt | grep -v '<br'                       # bare < not part of <br/> (HTML-tag opener)
  grep -nE '<=|>='                             /tmp/mm.txt                 # comparison ops in labels
  grep -nE 'subgraph[^[]*\[[^]]*[()/+{}|][^]]*\]' /tmp/mm.txt              # parens/slash/+ in SUBGRAPH titles (stricter than nodes)
  grep -niE '(^|[[:space:]])(end|call|click|class|graph|subgraph|style|link|href|default|direction|flowchart)[[:space:]]*\[' /tmp/mm.txt  # reserved-keyword node IDs
  grep -nE '\-\.[A-Za-z][^.]*\.->'             /tmp/mm.txt                 # dotted arrow missing spaces
  grep -nE '\[[^]]*---[^]]*\]'                 /tmp/mm.txt                 # triple-dash in node labels
  grep -nE '→|←|↔'                             /tmp/mm.txt                 # unicode arrows
  grep -nE '━|═|│'                             /tmp/mm.txt                 # box-drawing chars
  # Balance check: subgraph count must equal end count.
  echo "sg=$(grep -c subgraph /tmp/mm.txt) end=$(grep -cE '^[[:space:]]*end[[:space:]]*$' /tmp/mm.txt)"
  ```

  Every check must return zero hits (and sg==end) before opening.

- **The grep suite is necessary but NOT sufficient — it cannot prove a diagram parses.** It catches *known* character/keyword landmines, not novel ones or structural errors. For ground truth, run the actual parser:
  - **Interactive / one-off (zero setup, best ROI):** paste the failing diagram into the **Mermaid Live Editor — <https://mermaid.live>**. It renders against a pinned Mermaid version and prints the exact parse error with the offending token highlighted. When a user reports "Syntax error in text, mermaid version X.Y.Z" and the greps are clean, go here *first* instead of guessing — guessing burned three round-trips in the 2026-06 incident.
  - **Automated, if a Node runtime exists:** `mermaid.parse(src)` validates WITHOUT rendering (no headless browser needed) and throws with the token; or `mmdc` (`@mermaid-js/mermaid-cli`). A CI lint can iterate every `<pre class="mermaid">` block through `mermaid.parse`. Node-free boxes can `pip install nodejs-bin` to get one, or use a Go validator (`tetrafolium/mermaid-check`). The npm `@a24z/mermaid-parser` lints `.mmd` / markdown blocks from the CLI.
  - **Don't make the user be the parser.** If the greps pass but you can't run a real parser locally, say so and ask the user to paste into mermaid.live — that's faster and more honest than shipping a guess and waiting for "still broken."

## Node drill-down (double-click)

> **Opt-in feature.** Default is OFF — see section 11 in *What to generate* above for the cost rationale and the AskUserQuestion gate. The contract below applies only when drill-down has been turned on for this generation.

A static diagram answers "what's in scope"; a drillable diagram answers "what *changes* in this box, and where do I look for it." Without drill-down the reader still has to scroll 400 lines of markdown to recover the connection between a node and the plan's prose.

**Affordance**: double-click a *changing* node (kind `added` / `modified` / `deferred`) in the Repo Map, Blast Radius, or Order-of-operations diagrams. A side panel opens with the node's details. `untouched` / `external` nodes are not drillable by default — the `cursor: pointer` change is itself the signal that this box is part of the change. Single-click is reserved for pan/drag — don't bind it.

**Why gate on kind**: it doesn't measurably reduce HTML-generation cost (manifest entries are one line each, 40 vs 15 is noise). The point is *signal* — the pointer cursor becomes a kind-encoded affordance, and the reader doesn't waste a Claude round-trip clicking an untouched node to learn it's unchanged.

### Generate detail on-the-fly, not at HTML-generation time

**Do not precompute per-node detail for every diagram node.** A typical plan HTML has 15–40 drillable nodes; a reader inspects 2–5. Precomputing all 40 burns generation tokens (and re-burns them on every plan revision) for content that will never be read. Worse, the detail goes stale the instant the plan is edited.

Instead: drill-down is a **request-time round-trip back to Claude**, same pattern as the existing "Copy feedback as Claude prompt" button. Dblclick → panel opens → panel exports a structured prompt to the clipboard → user pastes into Claude → Claude reads the live plan + code and answers. The HTML stays a static artifact; the *current* state of the plan and the repo is what gets analyzed, not a snapshot frozen at HTML-generation time.

### What to embed at generation time (minimal)

A lightweight `nodeManifest` keyed by Mermaid node ID, with only the cheap fields the JS needs to build the drill prompt and the in-panel plan-jump chips:

```js
const nodeManifest = {
  "orch": {
    label: "cross_modality.py",
    kind: "added",                    // "added" | "modified" | "untouched" | "deferred" | "external"
    planAnchors: ["step-2", "knobs-card"]   // scroll targets in this HTML (data-section IDs)
  },
  "fit": { label: "_fit_and_eval", kind: "modified", planAnchors: ["step-2"] },
  "out_pe": { label: "intersection_per_example.parquet", kind: "added", planAnchors: ["step-2"] },
  "slice4": { label: "Slice 4: HTML / radar", kind: "deferred", planAnchors: ["slice-4"] },
  "vct": {
    label: "vista-ct cohort_all/ct/",
    kind: "external",
    planAnchors: ["gotcha-ct-master"],
    forceDrillable: true              // opt-in: unchanged but load-bearing (gates slice 3)
  },
  // also include manifest entries for untouched/external nodes that are NOT drillable,
  // so the verification pass can confirm they were intentionally non-drillable rather
  // than oversights. Just omit forceDrillable.
  "load": { label: "data_pipeline.load_eval_data", kind: "untouched", planAnchors: [] },
};
```

This is small (one line per node), cheap to author, and stable across the lifetime of the HTML. Everything *substantive* (summary, changes, exploded sub-diagram) is generated by Claude on demand.

**Drillability rule**: a node is drillable iff `manifest[key]` exists AND (`kind ∈ {added, modified, deferred}` OR `forceDrillable === true`). Everything else is rendered with the default cursor and ignores dblclick.

Also embed at generation time:
- `const planPath = "docs/plans/cross-modality-comparison.md";` — the source-of-truth path Claude should re-read on drill.
- `const planSha = "5d12e0431273...";` — the SHA Claude was given. Lets Claude warn the user if the live plan has drifted from the HTML.

### Wiring (JS sketch)

```js
// After mermaid.run(...) and after svg-pan-zoom is attached:
const DRILLABLE_KINDS = new Set(['added', 'modified', 'deferred']);

function isDrillable(entry) {
  return entry && (DRILLABLE_KINDS.has(entry.kind) || entry.forceDrillable === true);
}

function attachDrillHandlers() {
  document.querySelectorAll('pre.mermaid svg g.node').forEach(node => {
    const m = node.id.match(/^flowchart-(.+?)-\d+$/);   // Mermaid 10 ID shape
    const key = m ? m[1] : node.id;
    const entry = nodeManifest[key];
    if (!isDrillable(entry)) return;   // untouched/external nodes stay default-cursor, no dblclick
    node.style.cursor = 'pointer';
    node.classList.add('drillable');
    node.addEventListener('dblclick', (e) => {
      e.preventDefault(); e.stopPropagation();
      openDrillPanel(key, entry);
    });
  });
}

function buildDrillPrompt(key, manifest) {
  return `Drill into node "${key}" (${manifest.label}, kind=${manifest.kind}) from plan ${planPath} (HTML generated against SHA ${planSha.slice(0,12)}).

Re-read the plan and any referenced source files. Produce a markdown-formatted answer with these sections:

1. **Summary** — one paragraph, the node's role in this plan.
2. **Concrete changes** — 3–7 bullets, one line each, named functions / branches / fields / config keys. What will a reader see different if they open the file(s)?
3. **Files touched** — paths only.
4. **Plan steps that reference it** — step numbers + one-line why.
5. **Exploded sub-diagram** (only if the node has non-trivial internal structure) — a fenced \`\`\`mermaid block with a \`flowchart LR\` source. Follow the pitfall rules in the explain-plan skill (no { } | -- → in labels, quoted multi-line labels, etc).

If the live plan SHA differs from ${planSha.slice(0,12)}, flag the drift in a leading paragraph before the sections above.

Return only the markdown answer in your final message — no preamble, no "I'll now..." narration. Do not edit any files; do not write to the HTML.`;
}
```

### Relay integration (preferred path) + clipboard fallback

The drill panel's "Generate detail" button has two modes, in priority order:

1. **Relay (preferred).** A small localhost HTTP relay (`research-skills/relay/explain-plan-relay.py`) wraps `claude -p` and is reachable at `RELAY_URL` (default `http://127.0.0.1:7237`). The HTML POSTs the drill prompt to the relay, which shells out to `claude -p`, captures stdout, and returns it as JSON. The panel renders the markdown response inline via [marked](https://cdn.jsdelivr.net/npm/marked/marked.min.js) and caches the answer in `localStorage[\`drill::${planSha}::${nodeId}\`]`. Subsequent re-opens of the same node hit the cache — no relay round-trip, no token spend. Cache invalidates automatically when `planSha` changes (HTML regenerated from a new plan version).
2. **Clipboard fallback.** If the relay is unreachable (timeout or connection refused), the button copies the prompt to the clipboard with a toast: *"Relay not running — prompt copied to clipboard. Paste into Claude to drill, or `python research-skills/relay/explain-plan-relay.py` to enable inline drill."*

**Embed these constants at generation time** alongside the existing `planPath` / `planSha`:

```js
const RELAY_URL = "http://127.0.0.1:7237";              // localhost relay (see research-skills/relay/)
const REPO_ROOT = "/Users/.../Stanford/VISTA/code/<repo>";   // absolute path; `claude -p` runs here
```

Compute `REPO_ROOT` from the plan's location via `git -C <plan-dir> rev-parse --show-toplevel` at generation time; embed the absolute path so the relay can `cwd` into the repo and `claude -p` sees the codebase.

### Wiring (full flow)

```js
// Render markdown responses via marked (CDN). Add to <head>:
//   <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

async function probeRelay() {
  try {
    const r = await fetch(RELAY_URL, {method: 'GET', signal: AbortSignal.timeout(800)});
    return r.ok;
  } catch { return false; }
}

async function generateDetail(key, manifest, panel) {
  const cacheKey = `drill::${planSha}::${key}`;

  const cached = localStorage.getItem(cacheKey);
  if (cached) {
    renderMarkdownInto(panel, JSON.parse(cached).answer);
    return;
  }

  const prompt = buildDrillPrompt(key, manifest);
  showSpinner(panel, 'Asking Claude…');

  try {
    const r = await fetch(RELAY_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt, cwd: REPO_ROOT, timeout: 300}),
      signal: AbortSignal.timeout(330_000)   // slightly > relay timeout
    });
    if (!r.ok) throw new Error(`relay ${r.status}`);
    const {answer, elapsed_s} = await r.json();
    localStorage.setItem(cacheKey, JSON.stringify({answer, elapsed_s, ts: Date.now()}));
    renderMarkdownInto(panel, answer);
    appendFooter(panel, `via relay · ${elapsed_s}s`);
  } catch (e) {
    // Relay unreachable / errored — graceful fallback to clipboard
    await navigator.clipboard.writeText(prompt);
    renderFallbackInto(panel,
      `**Relay not reachable** (${e.message}).\n\n` +
      `Prompt copied to clipboard — paste into Claude to drill.\n\n` +
      `To enable inline drill: \`python research-skills/relay/explain-plan-relay.py\``
    );
  }
}

function renderMarkdownInto(panel, md) {
  panel.querySelector('.drill-body').innerHTML = marked.parse(md);
  // Re-run Mermaid on any new ```mermaid``` blocks the answer contained.
  panel.querySelectorAll('pre code.language-mermaid').forEach(b => {
    const pre = document.createElement('pre');
    pre.className = 'mermaid';
    pre.textContent = b.textContent;
    b.parentElement.replaceWith(pre);
  });
  mermaid.run({ querySelector: '.drill-body pre.mermaid' });
}
```

`openDrillPanel(key, manifest)` populates a right-side `<aside id="drill-panel">` with:
1. Header — node label + kind chip + a small "relay: ✓ / ✗" indicator (driven by `probeRelay()` at page load and on panel-open).
2. **Plan-jump chips** — one per `manifest.planAnchors` entry, scrolls to and expands the matching `<details data-section="...">`. Cheap, instant, no Claude round-trip — these always work regardless of relay state.
3. **"Generate detail" button** — calls `generateDetail(key, manifest, panel)`. Disabled while a request is in flight; shows spinner. Re-clicks while a cache hit exists re-render from cache. A "Re-ask (skip cache)" link sits below the button for the case where the plan moved and the user wants a fresh answer.
4. Close button, ESC, backdrop click all dismiss. The diagram stays interactive behind the panel.

### Affordance discovery

- Each diagram's hint label gains `• double-click changing nodes for details` alongside `scroll to zoom • drag to pan` — the word *changing* is load-bearing, it tells the reader which nodes will respond.
- Drillable nodes get `cursor: pointer` and a faint outline on hover.
- Non-drillable nodes (`untouched` / `external` without `forceDrillable`) keep the default cursor — the cursor change is the affordance signal, and itself encodes "this box is part of the change."

### Authoring discipline

Build `nodeManifest` *alongside* the diagram, not after. Include an entry for **every** node in the diagram (including untouched/external ones) — the verification pass uses entry-presence to distinguish "intentionally non-drillable" from "author forgot to add it."

When deciding `kind`: be honest. `modified` means this entity's behavior or signature actually changes in this PR. A file that's *touched but only by import-reordering or rename-tracking* is `untouched` from the reader's perspective — drilling into it would return "nothing interesting." Likewise, a sibling-repo node that *gates* this work (you depend on its output layout) is `external` + `forceDrillable: true` if there's a plan-anchor worth pointing at; plain `external` otherwise.

The manifest is intentionally thin. Resist the temptation to inline `summary` / `changes` / `exploded` fields into it "just for the common case" — that re-introduces the staleness problem and conflates the static HTML with the live plan state.

### Verification update

Add to the verification pass:
- **`ORPHAN_NODE`**: a Mermaid node in any diagram has no `nodeManifest` entry. List every instance. Either add the entry (with the appropriate `kind`) or drop the node — orphans leave the reader guessing about drillability.
- **`ORPHAN_MANIFEST`**: a `nodeManifest` entry has no corresponding Mermaid node ID across any diagram. Stale — delete or add the diagram node.
- **`BROKEN_ANCHOR`**: a `planAnchors` value doesn't match any `data-section` ID in the HTML. The chip would scroll to nothing.
- **`MISLABELED_KIND`**: a node labeled `untouched` / `external` is reachable from a step the plan says is `SHIPPED` or `PENDING` and likely modifies it (and vice-versa: a node labeled `modified` that the plan never mentions in any change-bearing step). Catches "author forgot to update the kind after the plan changed scope." Borderline calls are fine — only flag clear mismatches.

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
# Resume: apply explain-plan feedback
Plan: <repo-relative path> · branch: <branch> · plan-sha: <first-12>
→ If you're picking this up in a fresh session, read the plan doc above (plus any related docs / memory it points to) first. Then apply the feedback below.

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

**Fresh session vs in-flight — resolve the plan cheaply.** The resume header at the top of the paste names the plan path, branch, and `plan-sha`. If you are **already in flight on this plan this session** — you generated the HTML or read the plan earlier and the header's `plan-sha` matches what you hold — apply the feedback against the plan already in your context; you needn't re-open it. If you are a **fresh session**, follow the header: read the plan doc at that path first, plus any related docs or memory it points to, then ingest. If the live plan's SHA has drifted from the header's, flag it — the HTML feedback was written against an older version of the plan.

To ingest:
1. Parse the H2 sections.
2. For each section, find the corresponding part of the plan markdown.
3. Classify each comment:
   - **Bug report on the HTML itself** (e.g., "syntax error in mermaid", "this color is wrong", "section is missing") — fix the HTML directly; do NOT touch the plan.
   - **Clarification request** (e.g., "what is X?") — answer the user. For a one-off question a chat reply is fine; for a **non-trivial round** (several questions at once, a term-glossary ask, or an OQ-by-OQ pass), prefer writing the answers **inline into the HTML** as response callouts (see *Responding inline in the HTML* below) so each lives next to the section it explains. Do NOT silently edit the plan unless the answer reveals the plan is genuinely unclear.
   - **Trivial fix** (typo, broken link) — apply to plan directly.
   - **Substantive scope/content change** (e.g., "drop this task family from scope", "rename X to Y") — surface via `AskUserQuestion` before applying, since these often have cross-section ripple effects (status text, blast-radius edges, diff target tables, file enumerations). DO NOT chain-apply across the plan without the user confirming.
4. Regenerate the HTML (the SHA will change; embed the new one).
5. Re-run verification.

**Partial feedback is normal.** Users typically review and submit feedback in chunks (e.g., "I've reviewed sections 1–2, here's feedback, haven't gotten to the rest"). Treat each paste as additive. Don't pressure the user to finish before applying — they can continue reviewing while you apply the chunk. The localStorage persistence in the HTML widget means their unsubmitted feedback on later sections is safe across reloads.

The skill does NOT auto-apply substantive feedback — it requires user confirmation for non-trivial edits per `feedback_*` memories. For trivial fixes (typo corrections, link patches), apply directly.

### Responding inline in the HTML (non-trivial iterations)

When a feedback round is **non-trivial** — the user asks several questions at once, requests a term glossary, or gives an OQ-by-OQ pass — default to writing your responses **inline into the HTML companion** as visually distinct callouts placed next to the section each answers, rather than only in chat. The HTML is where the user is already reading; co-locating the answer with its section beats a wall of chat prose they have to cross-reference back to the plan.

**Ask preference when it's ambiguous.** The first such round in a session, or for a mixed batch, offer the choice via `AskUserQuestion` — *inline-in-HTML* vs *in chat* (vs *both*). Once the user has expressed a preference, honor it for the rest of the session without re-asking. A direct instruction ("write it into the HTML") overrides the default and skips the ask.

**The `.resp` callout pattern:**
- Add a `.resp` CSS class **distinct from the user's feedback widgets** — e.g. a left-accent border + subtle tint + a small uppercase label (`Claude`, or `Re: "<their question>"`). Keep it visually separate from the `textarea.section-feedback` widgets so the user's own input fields stay clean.
- **Place each response next to what it answers:** inside the relevant step/gotcha `<details>` block; for the JS-rendered OQ panel, add a parallel `OQRESP` map keyed by OQ number (template-literal HTML values) and render it after each OQ's prose, e.g. `(OQRESP[n] ? '<div class="resp">…' + OQRESP[n] + '</div>' : '')`. For cross-cutting term questions, a single *"Answers to your review questions"* card placed right after the Knobs/contracts section reads better than scattering definitions.
- **Never prefill the user's feedback textareas.** Those are localStorage-bound input fields; responses go in separate `.resp` callouts.

**SHA / drift discipline:**
- If you only added response callouts and the **source `.md` is unchanged**, do **NOT** bump `plan-sha256` — the responses are annotation, not plan content. Leaving the SHA untouched avoids a false drift flag *and* preserves the user's existing localStorage feedback (the widget wipes saved input when `__sha` changes).
- If the round also produces genuine plan edits, follow the normal regenerate path (new SHA, re-run verification) — and re-author the response callouts into the regenerated HTML.

**Then re-open** the HTML (`open <path>`) so the user sees the annotations in place, per the open-is-required rule above.

## Completion — recording review approval (peer to `/read-plan`)

`/explain-plan` is a peer of `/read-plan`: an approved, in-sync HTML review is an equally valid path to `Reviewed: Yes` in the plans index (`/review-plan` already offers the two as interchangeable visual-vs-prose review paths). When the user signals the visual review is **done / approved** — an explicit "done", "approved", "reviewed", "looks good, ship it", or unambiguous synonym, **not** a mid-loop "ok" / "looks good" acknowledgment — record the approval, gated on the HTML being SHA-in-sync with the plan:

1. **Confirm SHA-sync — this is the gate.** Recompute the plan's current hash (`shasum -a 256 <plan-path>`, or `sha256sum` on linux) and compare it to the HTML's embedded `<meta name="plan-sha256">`. They **must** match. A freshly generated or regenerated HTML qualifies (this skill embeds the current SHA on every write); a *stale* HTML — one the user reviewed before a later plan edit — must **not** flip the row, since that would record approval of a version the user never saw. If they differ, the HTML is stale: regenerate it (per *Idempotency and re-runs*), have the user re-confirm against the fresh HTML, then re-check.
   - Response-callout-only annotations deliberately leave the SHA untouched (see *SHA / drift discipline*), so an HTML carrying only `.resp` callouts is still in-sync and may promote.
2. **Confirm the plan is settled** — no unaddressed feedback, no open questions left dangling. If something is open, surface it once before closing out: "Before I mark this Reviewed — OQ2 is still Pending. Resolve or defer?"
3. **Mark the plan as Reviewed.** If the project has a plan-tracking index (`docs/plans/README.md` or equivalent with a `Reviewed` column), update this plan's row to `Reviewed: Yes` — the same step as `/read-plan` Phase 5, just reached via the visual path. Confirm inline: "Marked `<plan>` as Reviewed: Yes in `docs/plans/README.md` (HTML in-sync at `<sha-first-12>`)." If no such index exists, skip silently (don't bootstrap one mid-review — that's `/wrapup`'s job).
4. Then offer the natural next steps in one line: commit the plan + HTML via `/commit-review`, run `/review-plan` (its handoff-readiness lens checks fresh-agent implementability), or start implementation.

Like `/read-plan`, this is gated on an **explicit** approval signal — never infer it from a mid-loop "ok" or the user moving on, and never promote on a drifted HTML.

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
