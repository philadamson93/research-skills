#!/bin/bash
# Claude Code PreToolUse hook that enforces the claude_ops.md hard rule
# "Never Open a Remote Shell Into a VM (PHI)". It BLOCKS Bash commands that
# open a remote shell into — or pull data from — a project VM (ssh, gcloud
# compute ssh, IAP SSH tunnels, gcloud compute scp, scp/rsync over ssh), while
# ALLOWING cloud control-plane calls that never enter the VM (gcloud compute
# instances list/describe/start/stop) and local ssh key setup (ssh-keygen etc).
#
# Wire-up: see hooks/README.md.
#
# Contract (identical to phi-vet-gate.sh):
#   Stdin   — Claude Code PreToolUse JSON event
#             ({"tool_name":"Bash","tool_input":{"command":"...", ...}, ...})
#   Stdout  — empty on allow; JSON {"decision":"block","reason":...} on block.
#   Exit 0  — pass control back to the harness (allow, or block via stdout JSON)
#
# Behavior:
#   0. Machine gate — ACTIVE only on planner (PHI-FREE) machines; inert on
#      PHI-bearing VMs (so VM-side / fleet ssh is untouched). Reuses
#      lib/is-phi-free-machine.sh (see hooks/README.md "Machine gate").
#   1. Allow non-Bash tool calls.
#   2. Block when the command matches a reach-into-VM verb in COMMAND POSITION
#      (start of line or after a real shell separator, tolerating sudo/timeout/
#      env/VAR= wrappers) and is not one of the allowed carve-outs.

set -euo pipefail

# ---- 0. machine gate — active ONLY on planner (PHI-FREE) machines -----------
# The reach-into-VM risk lives on the LOCAL/planner box. On a PHI-bearing VM the
# helper exits non-zero and we go inert, so VM-side / fleet-orchestration ssh is
# unaffected. A machine's presence in lib/phi-free-machines.local is its single
# "I am a planner" declaration — it silences phi-vet AND arms this guard.
# (Narrow, self-correcting seam: an UNregistered planner reads as non-PHI-free
#  here and the guard is inert until it is registered — the same registration
#  that stops phi-vet's commit friction also arms this guard.)
hook_dir="$(dirname "$0")"
if ! { [ -x "$hook_dir/lib/is-phi-free-machine.sh" ] && "$hook_dir/lib/is-phi-free-machine.sh"; }; then
  exit 0
fi

# ---- 1. parse stdin --------------------------------------------------------

payload="$(cat)"

tool_name="$(printf '%s' "$payload" | jq -r '.tool_name // empty')"
[ "$tool_name" = "Bash" ] || exit 0

cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
[ -n "$cmd" ] || exit 0

# ---- 2. command matching ---------------------------------------------------
# A verb is in COMMAND POSITION if it starts the line or follows a real shell
# separator (; & | ( backtick $( newline) — NOT plain whitespace (so a verb
# mentioned inside a string arg, e.g. echo "connect via ssh", does not trip).
# Leading wrappers (sudo, nohup, env, command, exec, timeout <n>, VAR=val) are
# consumed so `sudo ssh vm` / `timeout 30 gcloud compute ssh vm` still match.
SEP='(^|[;&|`(]|\$\()'
WRAP='(sudo|nohup|env|command|exec|timeout[[:space:]]+[0-9smhd.]+|[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*)[[:space:]]+'
CMDPOS="${SEP}[[:space:]]*(${WRAP})*"

# A "remote spec" — user@host:path or host:/path|~ — marks scp/rsync as crossing
# to a remote box (so local-only scp/rsync are left alone).
REMOTE='[[:alnum:]_.-]+@?[[:alnum:]_.-]*:(/|~|[[:alnum:]])'

blocked=""

# (a) bare ssh / sshpass opening a remote shell.
#     `ssh` must be followed by whitespace/end so ssh-keygen/ssh-add/ssh-copy-id
#     (hyphen, not space) and the leading token of `sshpass` are NOT matched.
if printf '%s' "$cmd" | grep -qE "${CMDPOS}(ssh|sshpass)([[:space:]]|\$)"; then
  blocked="ssh"
fi

# (b) gcloud [alpha|beta] compute ssh|scp|start-iap-tunnel (flags may interleave;
#     [^;&|]* keeps the match inside one command segment). `compute instances …`
#     and `compute os-login ssh-keys …` do NOT match.
if printf '%s' "$cmd" | grep -qE "${CMDPOS}gcloud[[:space:]]+([^;&|]*[[:space:]]+)?compute[[:space:]]+(ssh|scp|start-iap-tunnel)([[:space:]]|\$)"; then
  blocked="gcloud-compute-shell"
fi

# (c) scp with a remote spec (data pull/push over ssh). Local-only scp: no colon
#     host → not blocked.
if printf '%s' "$cmd" | grep -qE "${CMDPOS}scp([[:space:]]|\$)" \
   && printf '%s' "$cmd" | grep -qE "$REMOTE"; then
  blocked="scp"
fi

# (d) rsync to/from a remote (host:path, or an explicit -e ssh transport).
#     Local-only rsync (rsync -a /src /dst) → not blocked.
if printf '%s' "$cmd" | grep -qE "${CMDPOS}rsync([[:space:]]|\$)" \
   && printf '%s' "$cmd" | grep -qE "($REMOTE|-e[[:space:]]+[\"']?ssh)"; then
  blocked="rsync"
fi

[ -n "$blocked" ] || exit 0

# ---- 3. block, teaching the PHI boundary + the prescribed remedy -----------

reason="🚫 PHI boundary — blocked a command that reaches into a project VM.

This opens a remote shell or pulls data from a VM (ssh / gcloud compute ssh / IAP tunnel / scp / rsync). Per claude_ops.md → \"Hard Boundary: Never Open a Remote Shell Into a VM (PHI)\", a local/planner Claude session must NEVER do this — even a read-only ls/cat/du — because the VM holds PHI and its output would cross into this session's transcript, which lives OUTSIDE the PHI boundary.

Do this instead:
- If VM state must be inspected or a command run there: hand the USER the exact command to run themselves (they paste back only PHI-free output), or do the work in an executor Claude session ON the VM. Never reach in from here.
- Cloud CONTROL-PLANE calls are fine and not blocked: \`gcloud compute instances list\` / \`describe\` (machine type, zone, disk) never enter the VM.

No silent bypass. If the user has explicitly authorized THIS command, they run it themselves (e.g. the \`!\` prefix); do not re-issue it as a tool call."

# PreToolUse decision-block protocol: JSON on stdout.
jq -nc --arg r "$reason" '{decision: "block", reason: $r}'
