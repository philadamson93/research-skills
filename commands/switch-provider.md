---
name: switch-provider
description: Switch Claude Code on this machine between Google Vertex AI and the Claude subscription (Stanford Claude Enterprise login), in either direction, without killing sessions already running. Edits the env block of ~/.claude/settings.json, backs it up, checks it parses, then tells Phil how to get new sessions onto the new provider — which means starting a FRESH `claude agents` window, because the old one keeps handing its stale settings to every session it starts. Invoked as `/switch-provider vertex` or `/switch-provider subscription`. TRIGGER when Phil says "switch to Vertex", "switch back to the subscription", "go back to my login", "use Vertex instead", "stop using Vertex", or "new session still says Vertex". SKIP for one-off Vertex calls inside a script or a sandboxed user (those set the variables on their own command line and are unaffected by this).
---

# switch-provider

Move new Claude Code sessions on this machine between **Vertex** (billed to a GCP project) and the
**subscription** (Phil's Claude Enterprise login, Stanford). Running sessions stay on whatever they
started with until they finish. Phil wants it that way: never kill an in-flight session to switch.

Argument: `vertex` or `subscription`. No argument: read the settings file, say which one is on now,
and ask which way to go.

## What decides the provider

Only one place on this machine: the `env` block of `~/.claude/settings.json`. Three keys turn Vertex
on; with them absent, Claude uses the login.

```json
"CLAUDE_CODE_USE_VERTEX": "1",
"ANTHROPIC_VERTEX_PROJECT_ID": "som-nero-plevriti-deidbdf",
"CLOUD_ML_REGION": "global"
```

- Region `global` is what the Claude 5 models need on this project. Older models used `us-east5`.
- The three `ANTHROPIC_DEFAULT_*_MODEL` keys pick which Opus/Sonnet/Haiku version you get. Leave
  them in both modes.
- Nothing in `~/.bashrc`, `~/.profile`, or the tmux environment sets these (checked 2026-11-08).
  If a switch doesn't take, re-check those before assuming anything else.

## Steps

1. **Back up**: `cp ~/.claude/settings.json ~/.claude/settings.json.<vertex|subscription>-backup-$(date +%F)`.
   Earlier backups (`settings.json.vertex-backup-*`) hold a known-good Vertex block to copy from.
2. **Edit** the `env` block: remove the three keys (→ subscription) or add them (→ vertex). Watch
   the trailing comma on the line before.
3. **Check it parses**, and show Phil the env keys:
   `python3 -I -c "import json;print(list(json.load(open('$HOME/.claude/settings.json'))['env']))"`
4. **Prompt Phil to restart `claude agents` and test.** Always end with this prompt, not just a
   note. Give him these steps:
   1. In the `claude agents` window, exit it (`Esc`/`q` back to the shell, or `Ctrl-C`).
   2. Start it again in the same pane: `claude agents`
   3. Start any new session from it (a throwaway is fine), then tell me "done".

   Running sessions keep going. Don't stop the background helper or close windows yourself:
   this session is probably one of its background jobs.
5. **Check it yourself** when he says done. Don't ask him to read `/status`:

   ```
   uv run ~/code/research-skills/scripts/check_claude_provider.py
   ```

   It's read-only. It compares the agents window's start time to the settings edit, and reads the
   environment the background helper recorded for each session started from that window. Exit 0
   = PASS. Exit 1 = FAIL: an old window, or a session on the wrong provider; read its lines and
   act. Exit 2 = nothing started from the fresh window yet; ask him to start one. Show him the
   RESULT line in your own words.
6. **Fallback only** (the check can't decide, or the helper's record format has changed): ask
   Phil for `/status` in a brand-new session and compare:
   - subscription → `Login method: Claude Enterprise account`, `Organization: Stanford University`
   - vertex → `API provider: Google Vertex AI`, `GCP project: som-nero-plevriti-deidbdf`

## Why a new session can still come up on the old provider

Editing the file is not enough. Two things hold the old settings:

1. **The `claude agents` window Phil starts sessions from.** It reads the settings file once, when
   it opens, and passes that copy of the environment to every session it starts (you can see it per
   session under `workers/<id>/dispatch/env` in `~/.claude/daemon/roster.json`). An agents window
   opened before the edit keeps handing out the old provider indefinitely. This was the real cause
   on 2026-11-08.
2. **Pre-started sessions.** The background helper keeps one session started ahead of time. One
   started before the edit carries the old settings. It's used up by the next new session and
   replaced with a fresh one, so this clears on its own.

**The fix that leaves running sessions alone:** exit `claude agents` and start it again (step 4).
The fresh window reads the edited settings file. Running background sessions are not affected:
on 2026-11-08 Phil exited and reopened it while several Vertex sessions were running, and the
background helper and those sessions all kept going. Opening a second `claude agents` in another
tmux window works too.

Do **not** offer `claude daemon stop` as the routine fix. Without `--keep-workers` it ends every
background session, and restarting the agents window is enough.

Pass looks like: the check script in step 5 prints `RESULT PASS`.

## If the new session is still wrong

Diagnose, don't guess. Each of these is one read-only command:

- File really changed: `grep -c VERTEX ~/.claude/settings.json` (0 for subscription).
- Which process the session runs in: the number in `/status` → `Peer address …/cc-socks/<pid>.sock`.
  `tr '\0' '\n' </proc/<pid>/environ | grep VERTEX` shows what it was started with.
- Which settings the agents window passed: search `~/.claude/daemon/roster.json` for the new
  session's worker and read its `dispatch/env`.
- Sessions loaded from somewhere else: `grep -rl CLAUDE_CODE_USE_VERTEX ~/.claude ~/code/*/.claude 2>/dev/null`.
  A hit inside a `permissions.allow` command string (e.g. rad-eval's sandboxed `optimizer` runs)
  is only text, not a setting.

## Subscription → Vertex extras

- Vertex auth uses the VM's Google credentials. If `/status` shows Vertex but calls fail with an
  auth error, Phil may need `gcloud auth application-default login`, which is interactive. Hand
  it over as `! gcloud auth application-default login`.
- Running sessions on the subscription stay there. Same rule as the other direction.
