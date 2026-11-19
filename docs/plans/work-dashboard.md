Reference: docs/claude_ops.md
Program: /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/programs/planning-layer.md — stage 7 (new: the work dashboard)

# Work dashboard: one status view built around questions and features
Status: Completed (2026-11-19). Built 2026-11-18. Evaluator round 1 NEEDS_WORK (12 findings, fixed); round 2 NEEDS_WORK on one fix, fixed with a test that failed first; Phil chose to land without a third round (2026-11-18). Reviews: planning/research-skills/reviews/work-dashboard-implementation-feedback.md. Explainer: plan-explainers/research-skills/work-dashboard.html. Still open from Done when: a week of use; hcpu-c4d not reporting yet

## Goal
Phil comes back from meetings and, from one screen, knows what finished, what needs him, what is running
where, and what is next for each research question, without opening a session. The unit is a question
(tests something) or a feature (builds something), not a session. Sessions, runs and machines hang off them.

## Done when
- After a week of use Phil answers those four things from the first screen alone → he says so.
- Every live session on a reporting machine is attached to a question or feature, or listed as unattached.
- Every run's state on the page matches the status line at the top of its readback (check all runs once).
- A click or comment made in Phil's Mac browser on the served page appears in the mount file within a minute.
- Every machine with a Claude session reports a snapshot under 10 minutes old.
- Works beyond VISTA-Bench experiments: at least one item each from agentic labelers, the Cohort Explorer and RadLex renders correctly, using the findings-list and build-checklist layouts → no VISTA-Bench-specific field is required.
- Question and feature pages, the status page and the method pages are all built from the item files; no hand-written page remains.
Stop and come back if: after the week Phil still opens agent view or sessions to find where things stand.

## Decided
- Item file parts: Phil approves question wording, why it matters and the answer so far; sessions may only fill result cells, update status, add runs and add or close decisions. Anything else is saved as a draft for Phil (2026-11-18)
- A session that fills a cell drafts an updated answer so far; it shows under Needs you; Phil accepts or edits (2026-11-18)
- Any session may propose a new question or feature page as a draft; /grill writes approved ones (2026-11-18)
- Sessions started without a question or feature: the session names one in its first reply or proposes a draft; quick lookups may stay unattached; the page lists unattached sessions (2026-11-18)
- Themes become methods (alone, fusion, disagreement) linked across questions; time point and patient group become grid axes. Each method has a page listing every question that uses it (2026-11-18)
- "Make this permanent?" card when a throwaway script is reused by a second question or feature, or when a result is definitely going into the paper, or when a session raises it (2026-11-18)
- Every readback starts with one status line: running / waiting on Phil / done / failed, plus a one-line plain result. The page trusts that line; readbacks without one show "status unknown", never guessed (2026-11-18)
- A run counts as possibly died only when its status says running, nothing new is written for its quiet period, and its machine shows no matching job. Hand-offs name the job and quiet period. A non-reporting machine shows "can't check the job" (2026-11-18)
- Problems: free rule checks on every 5-minute build, plus a once-a-day Sonnet review of all question pages for duplicates and missing links, capped at $5 a day; it only proposes problems for triage (2026-11-18)
- Served as one more site on the existing review server on vista-cohort, behind the front door at /phil-dashboard/; Phil's clicks, triage and comments save to the mount there and the builder reads them back. Local file copies still open, read-only for clicks (2026-11-18)
- No access check: anyone on the front door can already read the mount (2026-11-18)
- Drafts of all four areas at once (paper, agents vs embeddings, longitudinal, MerlinOnc); each page shows "draft wording" until Phil approves it on the page; Needs you shows one summary line for them (2026-11-18)
- Skill changes land together: hand-off template and /wrapup (readback status line; name question, cell, machine, job, quiet period; fill the cell and draft the answer), /grill (writes the item file), close-out Program line names the brief file, /dashboard, and /manage reads dashboard data instead of its own sweep (2026-11-18)
- Item format is general (Phil 2026-11-18: "don't overfit to these VISTA-Bench experiments"): a common core (title, kind, program, status, needs you, runs, sessions, code, links) plus one optional result layout per item: grid (methods × axes), findings list (result + number per line), or build checklist (features). No field may assume VISTA-Bench (2026-11-18)
- Every machine with Claude runs the snapshot every 5 minutes; the builder runs only on phil-sllm-01 (2026-11-18)
- Served address is /phil-dashboard/, not /dashboard/ (Phil, 2026-11-18)
- Park sets a whole question aside with nothing decided, and it returns on new session activity; Snooze lasts 1 day, 1 week or 1 month (Phil, 2026-11-18)
- First screen is "Now and recent": what is running or wrapped up in the last 24 h, by question, housekeeping folded; Needs you shows the last 7 days, older decisions fold below (Phil, 2026-11-18)
- Staleness: a free check flags a page whose readbacks or results changed after it; no history, overwrite check or locked editor yet, watch for a week (Phil, 2026-11-18)

## Out of scope
- Replying to sessions from the page: Claude Code's agent view does that. Access control. A new server.
- Rewriting old readbacks or sessions; only new and resumed work follows the new rules.

## Code layout
- `research-skills/scripts/dashboard/snapshot_sessions.py` — per-host sessions + machine state; extends the prototype
- `research-skills/scripts/dashboard/build_dashboard.py` — status page, question/feature pages, method pages, rule checks; extends the prototype; absorbs `work_graph_page.py`
- `research-skills/scripts/dashboard/daily_review.py` — new; one Sonnet call per day over item files, writes proposed problems
- `research-skills/scripts/dashboard/mount_links.js` — reused as is
- `vista-onc-labelers` review server (`review_server/serve.py`, `add_site.sh`) — reused unchanged as the host
- Mount `planning/dashboard/`: `items/*.json` (one per question or feature), `hosts/`, `problems.json`, built pages, `bin/` copy of the snapshot script
- `research-skills/commands/{dashboard,wrapup,grill,manage}.md`, the hand-off template, `claude_ops.md` close-out block — wording changes

## Deliverables
- [x] Item file format with Phil-owned vs session-owned parts and drafts, documented in scripts/dashboard/README.md — `scripts/dashboard/README.md:29` (format), `build_dashboard.py:335` (Approve/Accept applied only to wording seen, fingerprint)
- [x] Builder generates every page from item files; agents page regenerated, not hand-written — `pages.py:128` item view, `:189` standalone page, `:199` method pages; hand-written pages moved to `planning/dashboard/archive/`
- [x] Readback status line parsed; died rule uses status + quiet period + machine job list — `build_dashboard.py:218`, `:231`; `snapshot_sessions.py` `procs`; tests `RunStates`, `StatusLine`
- [x] Clicks, triage and comments read back from the review server's saved state — `build_dashboard.py:306`; tested in scratch and `PhilActions` tests. Served-site check waits on the vista-cohort site + deploy
- [x] Rule checks + daily review writing proposed problems — `build_dashboard.py:490`; `daily_review.py:45` (live run 11-18: 8 problems, $0.08); test `DailyCap`
- [x] Draft item files for all four areas (~35), plus at least one each from agentic labelers, the Cohort Explorer and RadLex — 29 files in `planning/dashboard/items/` (24 in the four areas; progression-labeler, explorer-variable-builder, radlex-silver-regex, radgraph-labeler-radlex)
- [x] Skill and template wording changes, as one set — `claude_ops.md:259`, `:272`; `commands/wrapup.md:177`; `commands/grill.md:46`; `commands/manage.md:128`; `commands/dashboard.md`
- [x] /phil-dashboard/ site on vista-cohort and front-door entry — site added on vista-cohort (`planning/dashboard/VISTA-COHORT-site-readback.md`, 11-18 23:13, all pages 200); route on vista-deploy main 89f00b8, deployed by Phil 11-18; first save from his browser seen in `planning/review_answers/` 11-18 23:25

## Expensive steps
- phil-sllm-01: daily review cron, Sonnet, $5/day cap → one problems file per day — approved 2026-11-18
- vista-cohort: `add_site.sh phil-dashboard <mount path>` → page loads at /phil-dashboard/ — approved 2026-11-18 (reuse)
- Phil, from a vista-deploy checkout: `git pull --ff-only && bash front-door/deploy.sh` → /phil-dashboard/ loads after sign-in — Phil runs it
- Each other machine: snapshot cron from `planning/dashboard/HOST-SETUP-handoff.md` → host file under 10 min old — Phil starts those sessions

## Landing
Branch `feat/work-dashboard` in research-skills (large change, skills included). Evaluator pass, explainer, then
/land. The prototype files already in the tree move onto that branch.
At /land, before removing the worktree: repoint phil-sllm-01's cron line from
`~/code/research-skills-work-dashboard/scripts/dashboard/refresh.sh` to `~/code/research-skills/scripts/dashboard/refresh.sh`,
delete the untracked prototype copy in the main checkout's `scripts/dashboard/` and `commands/dashboard.md` so the
merge can write them, and push the vista-deploy `/phil-dashboard/` entry (Phil deploys).
