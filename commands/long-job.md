---
name: long-job
description: Before a session goes quiet on a long job (GPU training, an embedding pass, a multi-hour hcpu batch, any run it waits on), register the job on the work dashboard so the dashboard follows it from its own log while the session sleeps — log on the mount, what in the log means done, failed or progress, the job's process name — and optionally queue the VM to switch itself off when the job ends (/vm-off). TRIGGER when a session has just started, or is about to start, a job it expects to run 30+ minutes and will wait on; when a hand-off says to start a training or long hcpu run; or on `/long-job`. SKIP for jobs that finish while you watch, and for runs whose readback the session will keep updating itself.
---

# long-job

A sleeping session never updates its readback, so without this the dashboard shows its run as quiet or
"possibly died" while it is training fine, and can't tell when it finished. The dashboard can read the run's log
instead, if the run says where it is and what to look for.

Format reference: `~/code/research-skills/scripts/dashboard/README.md` (the `runs` example) and
`<mount>/chaudhari_lab/phil/planning/dashboard/TELL-A-SESSION.md`. Mount root `<P>` =
`/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/` (weill mounts it elsewhere: see TELL-A-SESSION.md for its root).

## Do, once the job is running

0. **Linger on, before anything else** (training boxes): `loginctl show-user $USER -p Linger`; if `no`, run
   `sudo loginctl enable-linger $USER` (Phil approved for all GPU boxes, 2026-11-19). With linger off, the last
   login session closing deletes /dev/shm and kills PyTorch DataLoader workers; that killed a 100-epoch run at
   epoch 60 on 11-18.
1. **Find the item** the job serves in `<P>dashboard/items/` (TELL-A-SESSION step 1). No item: report it in
   your close-out and skip to step 4.
2. **Put the log on the mount.** If the job already writes there, use that path. If it writes locally, add a
   cron copy that never touches the job: `*/10 * * * * cp <local log> <P><repo>/runs/<run>/train.log`
   (make the folder first). Check the copy appears.
3. **Register the run** in the item's `runs` (edit only that entry; temp file + rename):
   - `label`, `machine` (`hostname`), `readback` (on the mount, status line on top), `quiet_h`
   - `job`: text that really appears in the process command (`ps -u $USER -o args | grep ...`)
   - `watch`: the mount log path from step 2 (planning-relative)
   - `done_text` (regex the log prints at the end) or `done_file` (the final checkpoint's mount path),
     `fail_text` (e.g. `Traceback|out of memory|NaN`), `progress` (e.g. `[Ee]poch \\d+/\\d+`).
     Read the actual log, or the training script's print statements, to choose them. Don't guess.
   - `wandb`: if the job logs to Weights & Biases, its run path `entity/project/run_id` (a list for several runs).
     The dashboard asks wandb for the run's state every 5 minutes, so a crash shows within minutes even if this
     box and this session are both quiet. Find the id in the job's log (`wandb: Syncing run …` / the run URL).
   - `next`: what happens to the result, naming files, never a session.
4. **Readback status line**: `Status: running — <what, and the expected finish>`.
4b. **Leave a wake-up behind, so you don't sleep blind.** Start one background command (Bash with
   `run_in_background`, so its exit wakes you) that ends when the job's process exits or the log shows a failure:
   `while kill -0 <pid> 2>/dev/null && ! tail -c 8192 <log> | grep -qE '<fail_text>'; do sleep 120; done; tail -n 40 <log>`
   When it wakes you: read the log, set the readback status line to `done` or `failed` with the evidence, update
   the run, and say what happened in your next message (a death is news for Phil, not something to retry silently;
   restarting is his call unless he already said otherwise). If you queued `/vm-off`, it handles the switch-off.
   This only works while this session stays open; the dashboard's log and wandb checks cover the case where it
   exits.
5. **Check it took**: after the next dashboard build (every 5 min), the run in `<P>dashboard/index.html`
   shows running with a `log: …` progress summary, not "quiet" or "possibly died".
6. **Switch-off, only if Phil asked for it** (or the hand-off says so): queue `/vm-off` after this job
   (`--after-job "<job text>"`). Never on weill.

Then say in your close-out that the dashboard is following the run from its log, and go quiet.
