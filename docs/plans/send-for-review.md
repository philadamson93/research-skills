Reference: docs/claude_ops.md
Program: /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/programs/planning-layer.md — stage 8 (new: send for review)

# Send for review: results pages arrive on the dashboard as they are ready
Status: Built (2026-11-20) on feat/send-for-review; evaluator PASS on round 2 (planning/research-skills/reviews/send-for-review-implementation-feedback.md). Open: cross-machine delay check (Phil runs check_review_latency.sh on the serving VM), explainer, land.

## Goal
When a session has a page ready for Phil (results, figures, explainers), it sends it to the work
dashboard website. Phil sees it within about a minute, reads it inside the dashboard, and answers there.
No more mount paths pasted into chat for Phil to open on the Mac.

## Done when
- A session on any machine runs `/send-for-review` on a page → it appears in the "To review" tab of the
  served dashboard (`/phil-dashboard/`) within 90 s, without a dashboard rebuild, unseen count in the tab title.
- Editing the original after sending leaves the reviewed copy unchanged; sending again shows v2 and marks v1 replaced.
- Approve / Needs changes + comment on a verdict page lands in `phil-actions.json` and shows on the item;
  an FYI page counts as done once opened.
- A session left open after sending wakes within ~2 min of a Needs changes click and has the comment text.
- Delete `review-index.json` → the next send or 5-minute rebuild puts every entry back.
- A page with no item tag lands under its path-matched item, or "unattached" if none matches.
- Tests in `scripts/dashboard/tests/` cover send, version bump, index self-heal and verdict merge, and pass.
Stop and come back if: a page sent from another machine takes over ~3 minutes to show on the served
site (the gcsfuse listing assumption is wrong and the server would need a live endpoint after all).

## Decided
- Trigger → a session calls the skill when something is ready; no folder scanning (2026-11-20)
- Pages are mostly results and figures, not plans; the skill covers both (2026-11-20)
- Frozen copy, versioned, never a link to the live original (2026-11-20)
- Item tie → tag written by the sender (item id + one line on what to look at), path match fallback,
  else "unattached" (2026-11-20)
- On arrival → top of list, unseen count in tab title, desktop notification if allowed; never auto-opens (2026-11-20)
- Read inside the dashboard under an answer bar; answers go through the existing click store (2026-11-20)
- Sender marks each page "verdict" or "FYI" (2026-11-20)
- The session does not wait for the verdict; it leaves a background check that wakes it on Needs changes,
  for up to 24 h; if its window is closed the verdict waits on the item (2026-11-20)
- Visible to anyone on the front door (2026-11-20)
- New rule: an HTML page for Phil goes through the skill; chat gives the website link, never a mount path;
  `/explain-plan` sends its page this way (2026-11-20)
- No review-server or front-door change: flat files in the dashboard folder, which the server already serves (2026-11-20)
- Housekeeping, decided without asking: move stray pages from `planning/plan-explainers/` into
  `plan-explainers/`; archive reviewed pages after 30 days into `dashboard/archive/` (2026-11-20)

- Built 2026-11-20: the stray-page move is dropped. `planning/plan-explainers/` also holds the paper-outline
  .docx files, two build scripts that write back into it and live 11-18 work, and is named by 2 items and
  4 memories; moving it breaks those, and the skill makes a page's folder irrelevant (2026-11-20)
- Built 2026-11-20: on the Mac the send uploads with `gcloud storage cp`, since the Mac mount can drop writes
  silently; it raises if the upload fails (2026-11-20)
- Built 2026-11-20: the script is also copied to `planning/dashboard/bin/` by the refresh, so any machine with
  the mount can send without a research-skills checkout (2026-11-20)

- Evaluator round 1 (2026-11-20): file names drop the date (`review-<name>-vN`) because version numbers are
  counted across the archive too, so an id is never reused; the send script keeps its own small file writer
  so it runs alone from `planning/dashboard/bin/` (2026-11-20)
- Evaluator round 1 (2026-11-20): only answers from the emails in `planning/dashboard/review-reviewers.json`
  (Phil) count as verdicts and wake a session; colleagues can still open pages. Edit that file to change it (2026-11-20)

## Out of scope
- Live folder watching or any change to the review server or front door.
- Sending the comment to a session that has been closed (the verdict waits on the item instead).
- Review pages for people other than Phil.

## Code layout
- `commands/send-for-review.md` — new skill: when to send, verdict vs FYI, item id and the one line to write.
- `scripts/dashboard/send_for_review.py` — new: copy the page to `planning/dashboard/review-<name>-vN.html`,
  write its entry `review-<...>.json`, rewrite `review-index.json`, print the website link; `wait` is the wake-on-verdict check.
  Own small file writer (runs alone from `planning/dashboard/bin/`); uploads with gcloud on the Mac.
- `scripts/dashboard/dashboard_template.html` — extends: "To review" tab first, 10 s check of the index,
  viewer with answer bar, unseen count, notification. Reuses the existing `wd:` click store.
- `scripts/dashboard/build_dashboard.py` — extends: rebuild the index from entry files, merge verdicts into
  `phil-actions.json`, "new page" badge on the item, 30-day archive.
- `scripts/dashboard/tests/` — extends with the tests named in Done when.
- `commands/explain-plan.md` — calls the skill at its end.
- `scripts/dashboard/check_review_latency.sh` — times the cross-machine delay on the serving VM.
- `claude_ops.md` — the new rule, one paragraph.

## Deliverables
- [x] `commands/send-for-review.md` — 56dc847
- [x] `scripts/dashboard/send_for_review.py` — c41b66e
- [x] "To review" tab + viewer in `dashboard_template.html` — c41b66e
- [x] index self-heal, verdict merge, item badge, archive in `build_dashboard.py` — c41b66e (item page section in `pages.py`)
- [x] tests — c41b66e, `scripts/dashboard/tests/test_send_for_review.py` (42 pass with the existing ones)
- [x] `/explain-plan` and `claude_ops.md` edits — 56dc847
- [x] ~~stray `planning/plan-explainers/` pages moved~~ dropped, see Decided
- [ ] dashboard item `send-for-review` ticked

## Expensive steps
None.

## Landing
Feature branch `feat/send-for-review` in a separate worktree: `main` has another session's uncommitted
dashboard edits (2026-11-20). Before merge: evaluator pass, explainer sent through the new skill itself,
and a rebase onto whatever that other session lands.
