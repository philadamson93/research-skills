#!/bin/bash
# Claude Code SessionStart hook that re-injects the claude_ops NON-NEGOTIABLES
# into a fresh context after an auto-compact.
#
# Why: the Claude Code docs do NOT guarantee CLAUDE.md / project instructions
# survive (or are re-injected after) a context compaction. A real session lost
# claude_ops after an auto-compact and did unapproved work (started a VM, made a
# 1.5TB disk). This hook re-anchors the core rules whenever a session resumes
# from a compact. It is a POINTER, not a duplicate of claude_ops (modularity) —
# it re-states the few load-bearing rules and tells the agent where to re-read.
#
# Wire-up: see hooks/README.md.
#
# Contract:
#   Stdin   — Claude Code SessionStart JSON event, including a trigger reason.
#             The reason field name has varied across versions, so we read the
#             first of .source / .reason / .trigger_reason.
#   Stdout  — empty for non-compact starts; the re-anchor text (added to the
#             session context) when the start reason is `compact`.
#   Exit 0  — always.

set -euo pipefail

payload="$(cat)"

reason="$(printf '%s' "$payload" | jq -r '.source // .reason // .trigger_reason // empty')"

# Only fire on a compact-triggered start. A normal startup already loads
# CLAUDE.md, so re-injecting there would be redundant noise.
[ "$reason" = "compact" ] || exit 0

cat <<'EOF'
[post-compact re-anchor — injected by post-compact-reinject.sh]

You may be resuming after an AUTO-COMPACT. Earlier context — including
claude_ops.md and any approved plan — may have been dropped. Before taking ANY
action, re-anchor on these NON-NEGOTIABLES, and re-read
~/code/research-skills/claude_ops.md if you are at all unsure:

  1. PLAN BEFORE CODE. Enter plan mode and get EXPLICIT user approval before
     implementing. Do NOT resume or start implementation off a compacted context
     without re-confirming the plan with the user first.
  2. ASK BEFORE DESTRUCTIVE / EXPENSIVE ACTIONS. Deleting /mnt data, and
     provisioning cloud infra (VM create/start, disk create/resize, terraform),
     require the user's go-ahead. (Hooks enforce the worst cases, but treat this
     as a standing rule regardless of what fires.)
  3. PHI DISCIPLINE. Never echo PHI into chat/docs/commits; commits in
     medical-data repos are gated by /phi-vet.
  4. EXECUTOR LANE. Make minor iterative corrections, but do NOT broad-plan or
     major-rewrite without user confirmation. If scope changed, document the
     finding and defer to a new plan.

If you were mid-task, briefly restate to the user what you believe the task and
its approved plan were, and confirm before continuing.
EOF
