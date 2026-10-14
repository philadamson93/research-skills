---
name: explain-plan
description: Build the what-changed explainer at the end of a piece of work — a self-contained HTML page on the shared mount showing what was built, how it fits into the repo, a diagram, a before/after, the numbers that moved, and each spec deliverable ticked against the commit or file:line that delivers it — then check the page against the spec and the actual diff, and link it from the PR or commit. This is the hand-over step in claude_ops.md "When the work is finished", after the evaluator agent passes the work. Also renders an older long-format plan doc (Approach / Files to Modify / Open Questions) that is still under review, when Phil asks to see it visually. TRIGGER when work against a spec or plan is finished and about to land, or on `/explain-plan [path]`. SKIP for small work with no spec, and for a spec whose build hasn't started — Phil's confirming the /grill interview is the approval, so no explainer is owed before the build.
argument-hint: "[path to spec or plan] [--plan for a pre-build view of an older long-format plan]"
---

# explain-plan

Phil doesn't read markdown or diffs. When work is done, this skill turns the spec plus what
actually landed into one HTML page Phil can read in a few minutes: what was built, where it sits,
what changed, and proof that each deliverable exists. It is the review surface for finished work
and the context a later session or reviewer reads first, the way a good PR carries a diagram or a
demo.

Two modes:

- **What changed (default).** After the build, after the `evaluator` agent passes it. This is
  the normal case.
- **Plan view (`--plan`).** An older long-format plan still being reviewed before its build.
  Same page shape, describing what *will* change. Kept because 2,000+ of those docs exist; new
  specs never need it.

## Voice

Follow `claude_ops.md` → How to write to me, for every word on the page and every question you
ask. The reader knows the research cold and has not opened the code. Lead with what the work
does and why; put identifiers in parentheses after the plain description. If you need to ask
Phil something, ask about outcomes Phil can judge, through `AskUserQuestion`, never about how the
page is built.

## Inputs

- The spec or plan path: the argument, or the one most recently named in the conversation. Specs
  live in the repo's `docs/plans/` (often an ignored symlink to the mount — open it by name).
- The diff: merge-base with `main` to the branch tip, or, for work that went straight on `main`,
  the commits since the spec was approved (a mount-only spec never enters git; use its *Approved*
  date). `git log --oneline` over that range gives the
  commit list for the deliverables table.
- The evaluator's verdict, the *Done when* output, and any results the work produced (reports,
  parquet summaries, logs on the mount).
- The `Program:` brief, if the spec names one.

Both spec formats must work. Read *Deliverables* or, in an older plan, *Files to Modify* plus
every numbered phase and sub-phase; *Done when* or *Verification*; *Decided* or *Open
Questions*.

## What goes on the page

In this order. The first screen answers "why" and "did it work", not "how".

1. **Header** — title, repo, branch or merge commit, spec path, date, and the spec's SHA-256
   (first 12 characters visible, full value in `<meta name="spec-sha256">`).
2. **Program strip** — one line from the brief: why the program exists, which stage this was,
   and what this stage unblocks. If the spec has no `Program:` line or the brief is missing, say
   so in one plain line. Don't fake it.
3. **TL;DR** — two to four sentences: what was built, what question it answers, whether the
   *Done when* checks passed.
4. **Numbers that moved** — every number the work changed or produced, as before → after with
   units (rows, AUROC, minutes, dollars, files). Link the report or file each came from. If
   nothing measurable moved (a refactor, a doc change), say so rather than leave the section
   empty.
5. **Where it sits** — a Mermaid `flowchart LR` of the repo pipeline around the change: upstream
   sources, the parts that changed, outputs, downstream consumers and sibling repos. Color by
   relation: added, changed, untouched (grey dashed). The untouched parts matter; they show what
   was left alone.
6. **Before / after** — side-by-side diagrams when the shape of the data flow or call graph
   changed. When it didn't, a short table of behaviour before and after is better than two
   near-identical pictures.
7. **Deliverables** — a table with one row per deliverable (and per sub-phase in an older plan):
   the item, the commit SHA or `file:line` that delivers it, and a ✅ or ❌. A ❌ row means the
   spec stays open; say that plainly at the top of the table. Don't roll sub-parts up into one
   row; that is how an approved sub-phase once went unbuilt for weeks.
8. **Checks** — each *Done when* check, the command that ran, what it printed (trimmed), and
   the evaluator's PASS line for it. Anything the evaluator flagged and you chose not to fix gets
   a row with the reason.
9. **Decided along the way** — any *Decided* entries added during the build, and anything that
   departed from the spec, with the reason.
10. **Not done / follow-ups** — the spec's *Out of scope* items that came up, and anything left
    for later.

Group diagram nodes by who calls what, not by which folder a file sits in. A new wrapper around
an existing function belongs in its own box beside the things it wraps, not inside them.

**Plan view** swaps sections 4, 7 and 8 for: the steps in order with their status (✅ shipped,
⏳ pending, 🛑 blocked), the files each step touches, and each Open Question restated as one
plain line naming the choice and its consequence, with the original text below it. Nothing on
the page collects feedback; Phil answers in chat.

### Page rules

- One HTML file, CSS and JS inline. External loads only from `cdn.jsdelivr.net`: Mermaid
  `@10` and `svg-pan-zoom@3.6.x`.
- Light and dark palettes via `prefers-color-scheme`. Laptop layout is enough.
- No emojis in prose. Status marks (✅ ⏳ 🛑 ⚠️ ❌) are fine; they carry meaning.
- Diagrams pan and zoom. Wrap each `<pre class="mermaid">` in a fixed-height box (about 520px,
  `overflow: hidden`); call `mermaid.initialize({ startOnLoad: false, flowchart: { useMaxWidth:
  false } })`, then `mermaid.run(...)`, strip the inline `max-width` from each rendered `<svg>`,
  and attach `svg-pan-zoom` (`minZoom: 0.3, maxZoom: 8, fit: true, center: true`). Give each
  diagram Reset and Fullscreen buttons and a "scroll to zoom, drag to pan" hint.
- When a diagram uses three or more node styles, put a `subgraph legend["Color legend"]` last in
  the source with one sample node per class actually used, color name in the label ("added
  (cyan)"). Missing legend entries were the most common complaint about these pages.
- Pick the "added" color so it can't be mistaken for any other: cyan, magenta or rose. Never
  yellow next to amber.

## Mermaid pitfalls

Each of these has broken a real diagram.

- No `{` or `}` anywhere in a label or subgraph title, even quoted. Write `(dataset)/(split)`.
- No `|` inside a node label; it is the edge-label delimiter. Use `/` or "or".
- No `--` or `---` inside labels (drop CLI-flag dashes in labels). Watch bulk bullet
  replacement, which creates them.
- No `→ ← ↔` or box-drawing characters (`━ ═ │`) in labels.
- No bare `<`, `>`, `<=`, `>=` in labels; the only tags allowed are `<br/>` and `<b>`. Write
  "at or below" or use `&lt;`.
- **Never use a reserved word as a node ID**: `end`, `call`, `class`, `click`, `style`, `link`,
  `href`, `graph`, `subgraph`, `direction`, `flowchart`, `default`, `linkStyle`. In 2026-06 a node
  with the ID `call` failed through three fix attempts because everyone checked the label, not the
  ID. Prefix derived IDs (`n_call`).
- Subgraph titles are stricter than node labels: letters, digits, spaces and commas only.
- Quote multi-line or punctuated labels: `s1["<b>Step 1</b><br/>line two"]`. Line breaks are
  `<br/>`, never `\n`.
- Edge labels use `A -->|label| B`. Dotted with a label needs spaces: `A -. label .-> B`.

Run these before opening the page. Every one must print nothing, and `sg` must equal `end`:

```bash
awk '/<pre class="mermaid"/{f=1;next} /<\/pre>/{f=0} f' <html> > /tmp/mm.txt
grep -nE '\{|\}' /tmp/mm.txt
grep -nE '\[[^]]*\|[^]]*\]' /tmp/mm.txt
grep -nE '\[[^]]*\(\)[^]]*\]' /tmp/mm.txt
grep -nE '<[^b]' /tmp/mm.txt | grep -v '<br'
grep -nE '<=|>=' /tmp/mm.txt
grep -nE 'subgraph[^[]*\[[^]]*[()/+{}|][^]]*\]' /tmp/mm.txt
grep -niE '(^|[[:space:]])(end|call|click|class|graph|subgraph|style|link|href|default|direction|flowchart)[[:space:]]*\[' /tmp/mm.txt
grep -nE '\-\.[A-Za-z][^.]*\.->' /tmp/mm.txt
grep -nE '\[[^]]*---[^]]*\]' /tmp/mm.txt
grep -nE '→|←|↔|━|═|│' /tmp/mm.txt
echo "sg=$(grep -c subgraph /tmp/mm.txt) end=$(grep -cE '^[[:space:]]*end[[:space:]]*$' /tmp/mm.txt)"
```

Clean greps don't prove a diagram parses. If Node is available, run each block through
`mermaid.parse`; if not, and Phil reports "Syntax error in text", paste the block into
<https://mermaid.live> first instead of guessing.

## Check the page against the work

Before handing it over, re-read the spec, the diff and the page side by side, and report one
line per problem in chat:

- **INVENTED** — the page claims something the diff, the results or the spec don't support.
  Highest priority; list every one.
- **DRIFT** — the page and the source disagree (a number, a status, a file).
- **MISSING** — a deliverable, a changed file that matters, or a moved number isn't on the page.
- **UNTICKED** — a deliverable marked ✅ whose commit or `file:line` doesn't contain it. Open
  the commit and look; the ✅ is only as good as that check.

Fix what you find, then summarize the rest as "N sections reconciled". In plan view, check
against the plan doc only (every step, file and Open Question present; nothing invented).

## Where it goes

Write the what-changed page to
`/mnt/su-vista-uscentral1/chaudhari_lab/phil/plan-explainers/<repo>/<spec-stem>.html`. Plan view
writes beside the plan (`planning/<repo>/<stem>.html`), where its existing explainer already lives.
Never commit the HTML.

- **On the Mac**, the mount can accept a write, read it back with a matching checksum, and never
  send it to the bucket (270 files lost this way in 2026-09). Write locally first, then
  `gcloud storage cp <local> gs://su-vista-uscentral1/chaudhari_lab/phil/plan-explainers/<repo>/`,
  and confirm with `gcloud storage ls` on that path. Never verify by re-reading the mount.
- **On a VM**, `cp` to `/mnt/...` works; there's no display, so the mount copy is the delivery.
- The mount is inside the secure environment, so copying there needs no PHI review (Phil's
  ruling, 2026-08-27). The page itself must still never contain a patient identifier, a sample
  row or report text. Aggregate numbers only.

Then:

1. Open it where there's a display (`open <local path>` on the Mac).
2. Link it: put the mount path in the PR description, or for work that went straight on `main`,
   in the spec's close-out block next to the ticked deliverables, so the next session finds it.
3. Hand over one line: the path and what a reader should look at first (usually the numbers or
   the ❌ rows).

Re-running on the same work regenerates the page in place. If the spec's SHA-256 no longer
matches the one in the page header, the spec changed after the page was built; regenerate before
anyone relies on it.

## Plan view and the Reviewed column

The old `Reviewed` column in plan indexes is frozen. Phil's approval of an older plan is recorded
in chat and the close-out block, not by changing that column.

## Improving this skill

When Phil answers a question with "what does that mean?", that's a writing failure; fix the
kind of question here, not just the one instance. When a section of the page keeps getting
skipped, cut it; when one keeps getting asked about, move it up.
