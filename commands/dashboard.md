---
name: dashboard
description: Refresh and read the work dashboard — the status view built around research questions and engineering features (what finished, what needs Phil, what is running on which machine, what is next for each question), served at the front door's /dashboard/ and on the mount at planning/dashboard/ — then print a short terminal summary. Also sets up the 5-minute snapshot on a machine, runs the daily problem review on demand, and records decisions Phil closed into the program brief's ledger. TRIGGER when Phil comes back after time away and asks "where are we", "what happened while I was out", "who is live", "what's waiting on me", "what finished", "where are the results", or types `/dashboard`; and when a session on a new host is told to "set up the dashboard here". SKIP inside a working session that already knows its task (use /next for one repo), and never use it to message or nudge other sessions (that is /manage).
---

# dashboard

Phil runs many sessions across several machines. The dashboard answers "where are we" without touching any
session: it reads files that already exist and writes pages.

- Served: front door `/phil-dashboard/` (a site on the review server on vista-cohort; Phil's clicks save there).
- Files: `/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/`
- Code and file formats: `~/code/research-skills/scripts/dashboard/README.md`. Spec: `docs/plans/work-dashboard.md`.

## Read it (the common case)

1. Refresh: `bash ~/code/research-skills/scripts/dashboard/refresh.sh` (on phil-sllm-01; elsewhere just read).
2. Summarize from the files, not from memory — `items/*.json`, `hosts/*.json`, `phil-actions.json`,
   `problems-auto.json`, `problems-proposed.json` — in this order, one screen at most:
   - **Needs you**: open decisions by question, runs whose readback says `waiting on Phil`, sessions stopped
     on a question (name, machine, the question), pages with draft wording (count).
   - **What finished** since Phil last looked: by question, one line each with the number.
   - **Running where**: runs by machine and state; any "possibly died"; machines not reporting.
   - **Problems** not yet triaged.
3. End with the link (`/phil-dashboard/` on the front door) and the one session or decision to look at first.

Quote numbers and questions as the item files and readbacks state them; don't re-judge them.

## Record what Phil decided

`phil-actions.json` holds what Phil marked Done, snoozed, triaged and wrote. Its `needs` entries carry the
`item` and `decision` id and the text he acted on; Done on a decision row is how he closes it. For each
decision he marked Done, add one dated line to the program brief's **Decided already** ledger (newest last, "Phil's
call"), then set `closed` on that decision in the item file. Ask him if the comment doesn't make the
decision clear. Never close a decision he didn't mark.

## Daily review on demand

`python3 ~/code/research-skills/scripts/dashboard/daily_review.py --force` (one Sonnet call, cents; capped
at $5 a day across runs). It only writes `problems-proposed.json`.

## Set it up on a machine

On a host that doesn't report yet, follow `planning/dashboard/HOST-SETUP-handoff.md`: one cron line that runs
the mount copy of the snapshot script every 5 minutes. Look at `crontab -l` first and keep what is there.
Only when Phil asked for that host, or a hand-off says to.

## Rules

- Read-only toward sessions: never `SendMessage`, never ask a session for status.
- Local HTML on the mount and the served site only; never publish it as an Artifact.
- Item files: sessions change only cells, findings, checklist, status, decisions and runs. Title, why and
  answer change only through `draft` and Phil's Approve or Accept.
