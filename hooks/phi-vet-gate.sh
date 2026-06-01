#!/bin/bash
# Claude Code PreToolUse hook that hard-gates `git commit` in medical-data
# research repos until /phi-vet has signed off on the current staged tree.
#
# Wire-up: see hooks/README.md.
#
# Contract:
#   Stdin   — Claude Code PreToolUse JSON event
#             ({"tool_name":"Bash","tool_input":{"command":"...", ...}, ...})
#   Stdout  — empty on allow; JSON {"decision":"block","reason":...} on block.
#   Exit 0  — pass control back to the harness (allow or block via stdout JSON)
#   Exit !=0 — surface stderr as the block reason (fallback path)
#
# Behavior:
#   1. Allow non-Bash tool calls.
#   2. Allow Bash commands that aren't a `git commit`.
#   3. Allow when cwd is NOT a medical-data research repo (heuristic below).
#   4. Block when staged tree has no matching sign-off marker, instructing
#      Claude to invoke `/phi-vet` to review the staged content (PHI scan +
#      explicit doc-read sign-off) and write the marker.

set -euo pipefail

# ---- 1. parse stdin --------------------------------------------------------

payload="$(cat)"

tool_name="$(printf '%s' "$payload" | jq -r '.tool_name // empty')"
[ "$tool_name" = "Bash" ] || exit 0

cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
[ -n "$cmd" ] || exit 0

# Match `git commit` only when it's at a command position — start of string or
# after a real shell separator (`;`, `&`, `|`, newline). Whitespace alone is
# NOT a separator (otherwise `git log --format="...git commit..."` would match).
# We accept:
#   git commit ...
#   git -C <path> commit ...
#   /path/to/git commit ...
#   ls && git commit ...
# We reject:
#   git commit-tree ...                        (subcommand is `commit-tree`)
#   git log --format='...git commit by ...'    (inside a string)
echo "$cmd" | grep -qE '(^|[;&|]|^[[:space:]]*)[[:space:]]*(git|/[^[:space:]]*/git)([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+commit([[:space:]]|$)' || exit 0

# ---- 2. detect medical-data research repo ---------------------------------

# Operate in the repo the commit will land in. If `git -C <path>` is used,
# extract the path; otherwise use $PWD.
repo_dir="$PWD"
extracted="$(echo "$cmd" | grep -oE 'git[[:space:]]+-C[[:space:]]+[^[:space:]]+' | head -1 | awk '{print $3}' || true)"
[ -n "$extracted" ] && repo_dir="$extracted"

# Must be inside a git work tree.
git_root="$(git -C "$repo_dir" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$git_root" ] || exit 0

# Heuristic: any of these signals trip the gate.
#  - CLAUDE.md mentions PHI/OMOP/NeuralFrame/DICOM/EHR/BigQuery keywords
#  - repo path matches a known medical-data repo name pattern
#  - a memory note about PHI exists (project-level CLAUDE.md or docs/)
is_medical=0
claude_md="$git_root/CLAUDE.md"
if [ -f "$claude_md" ]; then
  if grep -qiE '\b(PHI|OMOP|NeuralFrame|DICOM|EHR|BigQuery|patient[-_ ]data|de-?identif)' "$claude_md"; then
    is_medical=1
  fi
fi
repo_base="$(basename "$git_root")"
case "$repo_base" in
  vista-*|vista_*|meds-*|meds_*|ehr-*|ehr_*|path-extract|crc-extraction-agent|contrastive-3d-onc|MedExtractAgent|ehrshot*|hf_ehr)
    is_medical=1
    ;;
esac
if grep -rqlE 'PHI|patient[-_ ]data' "$git_root/docs" 2>/dev/null; then
  is_medical=1
fi
[ "$is_medical" -eq 1 ] || exit 0

# ---- 3. check for sign-off marker for the current staged tree -------------

# `git write-tree` writes the current index to a tree object and prints its SHA.
# Different staged content -> different SHA -> sign-off doesn't carry over.
tree_sha="$(git -C "$git_root" write-tree 2>/dev/null || true)"
[ -n "$tree_sha" ] || exit 0  # empty index is harmless; let git itself complain

# Resolve the common git dir so the marker path works in both the main
# checkout (.git/ is a directory) and worktrees (.git/ is a regular file
# pointing to .git/worktrees/<name>/; only the common dir is a real dir
# shared across all worktrees).
common_git_dir="$(git -C "$git_root" rev-parse --path-format=absolute --git-common-dir)"
marker_dir="$common_git_dir/phi-vet"
marker="$marker_dir/${tree_sha}.signed-off"

if [ -f "$marker" ]; then
  # Already vetted this exact staged content. Allow.
  exit 0
fi

# ---- 4. block, instructing Claude to run /phi-vet -------------------------

staged_count="$(git -C "$git_root" diff --cached --name-only | wc -l | tr -d ' ')"
doc_count="$(git -C "$git_root" diff --cached --name-only -- '*.md' '*.markdown' '*.rst' '*.txt' '*.html' 2>/dev/null | wc -l | tr -d ' ')"

reason="PHI gate: this commit lands in a medical-data research repo (\`$repo_base\`), and the staged tree \`$tree_sha\` has not been signed off by \`/phi-vet\`. Staged: $staged_count file(s), of which $doc_count are docs requiring the human user to read and acknowledge.

Required: invoke \`/phi-vet\` to (a) scan the staged content for PHI red flags per its threat catalog, (b) surface every doc file in the commit and require the HUMAN USER (not Claude) to explicitly confirm they have personally opened and read it — Claude having read the file during the scan does NOT satisfy this step; the user's appropriateness check is separate from the PHI scan, (c) on full approval, write a sign-off marker at \`<git-common-dir>/phi-vet/${tree_sha}.signed-off\` (the common git dir, resolved via \`git rev-parse --path-format=absolute --git-common-dir\` — same path from main checkout and any worktree). Once the marker exists, re-attempting \`git commit\` will pass this gate.

Skip path: if the user explicitly says 'skip the PHI check' or 'bypass phi-vet' in this turn, write the marker with the rationale appended and proceed — never bypass silently. Never answer the per-doc acknowledgement on the user's behalf, even under context pressure."

# PreToolUse decision-block protocol: JSON on stdout.
jq -nc --arg r "$reason" '{decision: "block", reason: $r}'
