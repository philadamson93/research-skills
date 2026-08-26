#!/bin/bash
# Claude Code PreCompact hook (best-effort) that nudges toward /wrapup before an
# AUTOMATIC compaction, so a session wraps up cleanly instead of silently
# compacting mid-task and losing its rails.
#
# It does NOT block compaction: blocking a genuinely-full context risks an
# overflow wall, which is worse than compacting. It only surfaces a message.
#
# Best-effort: which PreCompact output field actually surfaces to the user can
# vary by Claude Code version. This emits both a systemMessage (JSON) and a
# stderr note; if neither surfaces on a given version, this hook is harmless and
# can be dropped — the load-bearing piece is post-compact-reinject.sh.
#
# Wire-up: see hooks/README.md.
#
# Contract:
#   Stdin   — Claude Code PreCompact JSON event. The documented field is
#             `.trigger` (`auto` for automatic, `manual` for /compact); older
#             field names are read as harmless fallbacks.
#   Stdout  — empty for manual; a systemMessage JSON for auto.
#   Exit 0  — always (never block).

set -uo pipefail

payload="$(cat)"

# `.trigger` is the documented PreCompact field; the others are defensive
# fallbacks in case a version differs.
reason="$(printf '%s' "$payload" | jq -r '.trigger // .trigger_reason // .reason // .source // empty' 2>/dev/null)"

# Only nudge on an automatic compact; a manual /compact is already a deliberate
# user action.
[ "$reason" = "auto" ] || exit 0

msg="Auto-compact imminent: context is nearly full. Avoid STARTING new work now — consider running /wrapup to checkpoint cleanly. After the compact, re-confirm the task and plan before continuing (claude_ops: plan-before-code, ask-before-destructive)."

printf '%s\n' "$msg" >&2
jq -nc --arg m "$msg" '{systemMessage:$m}'
