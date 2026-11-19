---
name: vm-off
description: Put this machine's final status on the work dashboard and switch this VM off — now, or queued to happen when a long job finishes. Refuses on shared always-on machines (weill), asks before switching off phil-sllm-01 (it builds the dashboard and serves review pages), and refuses while anything else is still running on the box. TRIGGER when Phil says "turn this VM off", "shut this box down", "switch it off when the training is done", "power off after", or types `/vm-off`; and as the last step of /long-job when Phil asked for the box to go off after the job. SKIP on weill, and for stopping a single job (that is not a VM shutdown).
---

# vm-off

Phil switches VMs off when they are idle so they stop billing. A box that just goes dark looks broken on the
dashboard; this skill switches it off on the record: the dashboard shows "switched off <when>: <reason>".

Script: `~/code/research-skills/scripts/dashboard/power_off.py` (or the mount copy
`<mount>/chaudhari_lab/phil/planning/dashboard/bin/power_off.py` on a box without the checkout). A guest
shutdown stops a GCE VM: compute billing ends, disks and everything on them stay.

## Now

1. Finish your own reporting first: readback status line current, item `runs`/`status` updated, anything
   unsaved on local disk copied to the mount (`/wrapup` if this is the end of a session).
2. Confirm with Phil in one line unless he already said to switch this box off in this conversation:
   which box, and what is still on it that dies with it (tmux sessions, local-only files).
3. Run, from the box:
   `python3 ~/code/research-skills/scripts/dashboard/power_off.py --now --reason "<one plain sentence>"`
   It refuses (exit 1) if another Claude session is busy or a long job of Phil's is still running, and names
   them. Don't work around that: tell Phil what is running and offer the queued form below.
   On phil-sllm-01 add `--builder-ok` only after Phil confirms; the dashboard stops refreshing while it is off.
4. It writes the final snapshot and shuts down in 1 minute (`sudo shutdown -c` cancels). Say so in your last
   message; nothing after that reaches Phil.

## Queued: switch off when a job finishes

Start it detached so it outlives this session, as one line:
`nohup python3 ~/code/research-skills/scripts/dashboard/power_off.py --after-job "<text in the job's command>" --reason "<sentence>" > ~/.cache/power-off.log 2>&1 &`
(`--after-pid N` instead, if you have the pid.) The dashboard shows "switches off after <job>" on the machine
while it waits. When the job ends it waits until nothing else is busy on the box, up to 24 h
(`--max-wait-h`); if the box never goes quiet it does not switch off, and the dashboard says "did not switch off:
still busy". Rehearse any form with `--dry-run`.

## Never

- On weill (shared, always on): the script refuses; use `start_snapshot.sh`'s stand-down instead.
- To stop someone else's work, or with the job's results still only on local disk.
