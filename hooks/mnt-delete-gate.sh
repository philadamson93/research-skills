#!/bin/bash
# Claude Code PreToolUse hook that asks for HUMAN approval before any Bash
# command deletes / overwrites / moves-out data under /mnt (the shared bucket
# mount — irreplaceable).
#
# Wire-up: see hooks/README.md.
#
# Contract:
#   Stdin   — Claude Code PreToolUse JSON event
#             ({"tool_name":"Bash","tool_input":{"command":"..."}, "cwd":...}).
#   Stdout  — empty on allow; on a match (or an internal error), JSON asking the
#             harness to prompt the human:
#               {"hookSpecificOutput":{"hookEventName":"PreToolUse",
#                "permissionDecision":"ask","permissionDecisionReason":"..."}}
#   Exit 0  — always (the decision travels via stdout JSON, not the exit code).
#
# Fail-closed: if jq is missing or the event can't be parsed, we ASK rather than
# silently allow — a guardrail that fails open is worse than a spurious prompt.
#
# Detection scope (honest — see README "Known limits"): whole-string
# co-occurrence on the heredoc-body-stripped command; keyed on /mnt ONLY. It does
# NOT bind a verb to its exact target, split compound commands, or expand
# vars / $() / eval / symlinks. Careless-mistake guardrail, not a sandbox.

set -uo pipefail

here="$(dirname "$(readlink -f "$0")")"
# shellcheck source=lib/shell-scan.sh
. "$here/lib/shell-scan.sh"

# ---- 0. fail-closed dependency check ---------------------------------------
if ! command -v jq >/dev/null 2>&1; then
  emit_ask "/mnt delete gate could not run (jq not found). Asking for manual confirmation so the guardrail fails closed."
  exit 0
fi

# ---- 1. parse stdin (fail-closed on parse error) ---------------------------
payload="$(cat)"
tool_name="$(printf '%s' "$payload" | jq -r '.tool_name // empty' 2>/dev/null)"
if [ $? -ne 0 ]; then
  emit_ask "/mnt delete gate could not parse the hook event. Asking for manual confirmation (fail closed)."
  exit 0
fi
[ "$tool_name" = "Bash" ] || exit 0

cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
[ -n "$cmd" ] || exit 0

# Remove heredoc BODIES (data) but keep the opener and any post-terminator
# commands (see lib/shell-scan.sh for why the old tail-truncation was wrong).
scan="$(strip_heredoc_bodies "$cmd")"

# ---- 2. does the command reference a /mnt path? ----------------------------
# Match `/mnt` only as a path token (followed by `/`, a non-word char, or EOL)
# so `/mntx` / `/mnt_backup` embedded in another word don't trip it.
echo "$scan" | grep -qE '/mnt(/|[^[:alnum:]_]|$)' || exit 0

# ---- 3. does it invoke a destructive verb (against /mnt)? -------------------
# Any of:
#   - rm / rmdir / unlink / shred / truncate  (rm also covers `gsutil rm`,
#                                              `gcloud storage rm` of a /mnt path)
#   - mv                                      (moving data — incl. OUT of /mnt)
#   - dd ... of=...                           (overwrite)
#   - rsync ... --delete                      (mirror-delete)
#   - find ... -delete                        (bulk delete)
#   - `> /mnt/...`                            (truncating redirect onto /mnt)
# The verb need not be bound to the /mnt token (whole-string co-occurrence); this
# can nag on e.g. `mv X /mnt/` (adding data) or `rm /tmp/x && ls /mnt` — accepted
# as safe-direction. Redirect is the one target-bound check (`>` immediately onto
# a /mnt path) to avoid firing on `cat /mnt/a > /tmp/b` (reading FROM /mnt).
destructive=0
if echo "$scan" | grep -qE '\b(rm|rmdir|unlink|shred|truncate)\b'; then destructive=1; fi
if echo "$scan" | grep -qE '\bmv\b'; then destructive=1; fi
if echo "$scan" | grep -qE '\bdd\b' && echo "$scan" | grep -qE 'of='; then destructive=1; fi
if echo "$scan" | grep -qE '\brsync\b' && echo "$scan" | grep -qE '(^|[[:space:]])--delete(\b|=)'; then destructive=1; fi
if echo "$scan" | grep -qE '\bfind\b' && echo "$scan" | grep -qE '(^|[[:space:]])-delete(\b)'; then destructive=1; fi
if echo "$scan" | grep -qE '(^|[^>])>[[:space:]]*['\''"]?/mnt(/|[^[:alnum:]_]|$)'; then destructive=1; fi
[ "$destructive" -eq 1 ] || exit 0

# ---- 4. ask the human ------------------------------------------------------
preview="$(printf '%s' "$cmd" | tr '\n' ' ' | cut -c1-200)"
reason="/mnt delete gate: this command runs a destructive operation (delete / overwrite / move) touching a path under /mnt (the shared bucket mount, which holds irreplaceable results/data). Command: \`${preview}\`. Confirm you intend to modify /mnt data before proceeding."
emit_ask "$reason"
exit 0
