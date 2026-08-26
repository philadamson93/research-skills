#!/bin/bash
# Claude Code PreToolUse hook that asks for HUMAN approval before any Bash
# command provisions expensive / irreversible cloud infrastructure — VM
# create/start, disk create/resize, terraform apply/destroy, bucket create.
#
# Motivated by a real incident: a post-auto-compact session started a VM and
# created a 1.5TB disk with no approval. These verbs are rare, so an approval
# prompt on each is cheap insurance.
#
# Wire-up: see hooks/README.md.
#
# Contract:
#   Stdin   — Claude Code PreToolUse JSON event
#             ({"tool_name":"Bash","tool_input":{"command":"..."}, ...}).
#   Stdout  — empty on allow; on a match (or an internal error), the "ask" JSON
#             (same shape as mnt-delete-gate.sh).
#   Exit 0  — always.
#
# Fail-closed: missing jq / unparseable event ⇒ ASK, not silent allow.
#
# Detection (honest — see README "Known limits"): a provisioning BINARY token
# (gcloud/gsutil/terraform) co-occurring with its OPERATION phrase, on the
# heredoc-body-stripped command. This tolerates normal flag placement
# (`gcloud beta compute instances create`, `gcloud --project p ...`,
# `gsutil -m mb`, `terraform -chdir=infra apply`). It is NOT a shell parser.

set -uo pipefail

here="$(dirname "$(readlink -f "$0")")"
# shellcheck source=lib/shell-scan.sh
. "$here/lib/shell-scan.sh"

# ---- 0. fail-closed dependency check ---------------------------------------
if ! command -v jq >/dev/null 2>&1; then
  emit_ask "provision gate could not run (jq not found). Asking for manual confirmation so the guardrail fails closed."
  exit 0
fi

# ---- 1. parse stdin (fail-closed on parse error) ---------------------------
payload="$(cat)"
tool_name="$(printf '%s' "$payload" | jq -r '.tool_name // empty' 2>/dev/null)"
if [ $? -ne 0 ]; then
  emit_ask "provision gate could not parse the hook event. Asking for manual confirmation (fail closed)."
  exit 0
fi
[ "$tool_name" = "Bash" ] || exit 0

cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
[ -n "$cmd" ] || exit 0

scan="$(strip_heredoc_bodies "$cmd")"

# ---- 2. match a provisioning binary + operation ----------------------------
# Parallel arrays (NOT a delimited string — the operation regexes contain `|`
# alternation, which would collide with any single-char field separator). We
# require BOTH the binary token and its operation phrase to appear
# (co-occurrence). The operation phrases are specific enough that a benign
# co-occurrence is unlikely; flag placement (global flags, gcloud release tracks
# like `beta`, `gsutil -m`, `terraform -chdir`) is tolerated because we do NOT
# require the binary and operation to be contiguous.
declare -a p_bin=( gcloud gcloud gcloud gcloud gcloud gsutil terraform )
declare -a p_op=(
  'compute[[:space:]]+instances[[:space:]]+create'
  'compute[[:space:]]+instances[[:space:]]+start'
  'compute[[:space:]]+disks[[:space:]]+create'
  'compute[[:space:]]+disks[[:space:]]+resize'
  'storage[[:space:]]+buckets[[:space:]]+create'
  '(^|[[:space:]])mb([[:space:]]|$)'
  '(^|[[:space:]])(apply|destroy)([[:space:]]|$)'
)
declare -a p_label=(
  'gcloud compute instances create'
  'gcloud compute instances start'
  'gcloud compute disks create'
  'gcloud compute disks resize'
  'gcloud storage buckets create'
  'gsutil mb'
  'terraform apply/destroy'
)

matched=""; matched_bin=""
for i in "${!p_bin[@]}"; do
  bin="${p_bin[$i]}"; op="${p_op[$i]}"; label="${p_label[$i]}"
  if echo "$scan" | grep -qE "\b${bin}\b" && echo "$scan" | grep -qE "$op"; then
    matched="$label"; matched_bin="$bin"; break
  fi
done
[ -n "$matched" ] || exit 0

# ---- 2b. scoped help/dry-run suppression -----------------------------------
# Suppress ONLY when --help/--dry-run belongs to the SAME simple command as the
# matched binary (no command separator between them). This avoids the earlier
# global-exemption hole where an unrelated `echo --help && terraform apply`
# suppressed a real provision. `[^;&|]` keeps it within one segment (grep is
# line-oriented, so a separator on another line already breaks the match).
if echo "$scan" | grep -qE "\b${matched_bin}\b[^;&|]*(--help|--dry-run)(\b|=)"; then
  exit 0
fi

# ---- 3. surface the cost knobs in the reason -------------------------------
size="$(echo "$scan" | grep -oE -- '--size[= ][^[:space:]]+' | head -1 || true)"
mtype="$(echo "$scan" | grep -oE -- '--machine-type[= ][^[:space:]]+' | head -1 || true)"
extra=""
[ -n "$size" ] && extra="$extra ${size}"
[ -n "$mtype" ] && extra="$extra ${mtype}"

preview="$(printf '%s' "$cmd" | tr '\n' ' ' | cut -c1-200)"
reason="Provision gate: this command provisions expensive / irreversible cloud infrastructure (\`${matched}\`${extra:+, ${extra# }}). Command: \`${preview}\`. Confirm you intend to create/start/resize this resource — it may incur ongoing cost and is not trivially undone."
emit_ask "$reason"
exit 0
