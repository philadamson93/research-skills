---
name: send-for-review
description: Send an HTML page that is ready for Phil (results, figures, a what-changed explainer, any page Phil should look at) to the "To review" tab of the work dashboard website, where Phil reads it within about a minute and answers Approve or Needs changes with a comment. Freezes a copy so what Phil reviews never changes underneath, ties it to its dashboard item, and leaves a background check that wakes this session when Phil answers. TRIGGER whenever a session has an HTML page for Phil to look at, at the end of /explain-plan, and on `/send-for-review [path]`. SKIP for pages nobody needs to look at yet, and for review pages built for other people (clinician reviewers), which have their own sites.
---

# send-for-review

Phil reads results on the dashboard website, not from mount paths pasted into chat. **An HTML page for
Phil goes through this skill; chat gives the website link it prints, never a mount path.**

## Before sending

- The page is **finished** for this round: the numbers are final for what was asked, and you've checked it.
- It is **self-contained**: images as `data:` URIs, scripts and styles inside the page. The script refuses
  a page that loads files by relative path (the frozen copy can't see them) and says which ones.
- No patient identifier, sample row or report text, as for anything on the mount.

## Send

```bash
python3 /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/bin/send_for_review.py send <page.html> \
  --item <item-id> --look "<one sentence: what to look at or decide>" --by "<this session's name>" [--fyi]
```

(Use the repo copy, `research-skills/scripts/dashboard/send_for_review.py`, where it exists.)

- `--item`: the question or feature id under `planning/dashboard/items/`. Always give it when one fits;
  without it the page is matched by path and often lands as "not tied to a question".
- `--look`: the one thing Phil should check, in plain words: "Is the Haiku arrow in panel c the right
  comparison?" Not "please review".
- `--fyi`: for a page Phil only needs to see (opening it is enough). Leave it off when you need a verdict.
- `--name`: keep the same name when sending a fixed version, so it shows as v2 and v1 is marked replaced.
  The default is the file name, so re-sending the same file already does this.

It prints `link: https://…/phil-dashboard/#r=<id>`. Put **that link** in your close-out block and in the
item file's `sources`.

## Wait for the verdict without waiting

Start a wait **only when you are about to end your turn and go quiet**. While Phil is going back and forth
with you in chat about the page, don't start one: he answers in chat, and a wait per version just piles up
background shells (eleven of them on one figure, v12 to v22, 2026-11-20).

**One wait per page, at most.** Before starting a wait, check your own background shells; if one is already
waiting on an earlier version of this page, stop it (`TaskStop`) first. The script also backs this up: a
wait ends by itself (exit 4) within 30 s of a newer version being sent, from any session or machine.

For a verdict page, start the line the script printed after `wait:` **as a background command** (Bash with
`run_in_background`), then finish your turn as usual:

```bash
python3 <same script> wait <entry-id>          # exits when Phil answers or a newer version is sent; gives up after 24 h
```

When it exits you are woken with what Phil said:

- `APPROVED` → record it on the item (status line, checklist) and carry on with the next step.
- `NEEDS CHANGES` + `comment:` → make the change, re-send the page (same name, so it becomes v2), and
  start a new wait only if you are going quiet again.
- `REPLACED` (exit 4) → a newer version was sent; that version's own wait (if any) covers it. Nothing to do.
- `no verdict … after 24 h` (exit 3) → nothing to do; the verdict will wait on the item for the next session.

Never stop background shells you didn't start (other sessions' servers and waits share the machine).

If your session ends first, nothing is lost: verdicts are in `planning/dashboard/phil-actions.json` under
`review_pages`, keyed by entry id, for whichever session picks the item up.

## When not to use it

- Pages for other reviewers (rad-labeler, treatment review): those have their own front-door sites.
- Work in progress you want feedback on mid-way: ask in chat instead; this tab is for finished rounds.
