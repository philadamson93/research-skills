#!/usr/bin/env bash
# Set up Claude Code on a project VM the way phil-sllm-01 has it: Claude Code itself, the shared
# skills/agents from this repo, and a ~/.claude/settings.json that runs Claude through Vertex
# (project som-nero-plevriti-deidbdf, global region) with the PHI commit gate and the other hooks.
#
# Usage, on the VM, as the user who will run the Claude session (on the GPU boxes that is the
# gcsfuse mount owner, e.g. pmayankees, so the session can see that user's screen sessions):
#   git clone git@github.com:philadamson93/research-skills.git ~/code/research-skills ; bash ~/code/research-skills/scripts/setup_claude_vm.sh
# (Re-running is safe: every step skips itself when already done.)
#
# Steps, stopping at the first failure:
#   1. installs Claude Code with Anthropic's installer if `claude` is not on PATH
#   2. links ~/.claude/commands and ~/.claude/agents to this clone
#   3. writes ~/.claude/settings.json if there is none (never overwrites an existing one)
#   4. checks Google credentials for Vertex (the VM's service account, or your own login)
#   5. asks Claude for a one-word reply through Vertex (a fraction of a cent)
#
# Env: SKIP_SMOKE=1 skips step 5.
# Pass = last line "PASS: Claude Code ready". If step 4 fails, run: gcloud auth application-default login

set -uo pipefail
die()  { echo ""; echo "STOP: $*" >&2; exit 1; }
note() { echo "  -> $*"; }

RS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"
mkdir -p "$CLAUDE_DIR" "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"

note "1. Claude Code"
if command -v claude >/dev/null 2>&1; then
  note "already installed: $(claude --version 2>/dev/null)"
else
  curl -fsSL https://claude.ai/install.sh | bash || die "Claude Code installer failed"
  command -v claude >/dev/null 2>&1 || die "installed, but claude is not on PATH (add ~/.local/bin to PATH)"
  grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
  note "installed: $(claude --version 2>/dev/null)"
fi

note "2. shared skills and agents from $RS_DIR"
for d in commands agents; do
  link="$CLAUDE_DIR/$d"
  if [ -L "$link" ]; then
    [ "$(readlink "$link")" = "$RS_DIR/$d" ] || die "$link points to $(readlink "$link"), not $RS_DIR/$d; fix it by hand"
  elif [ -e "$link" ]; then
    die "$link is a real directory; move it aside, then re-run"
  else
    ln -s "$RS_DIR/$d" "$link" || die "could not link $link"
  fi
done

note "3. settings"
SETTINGS="$CLAUDE_DIR/settings.json"
if [ -e "$SETTINGS" ]; then
  note "kept the existing $SETTINGS (compare with phil-sllm-01's if Vertex or the hooks misbehave)"
else
  H="$RS_DIR/hooks"
  cat > "$SETTINGS" <<EOF
{
  "env": {
    "CLAUDE_CODE_ENABLE_AUTO_MODE": "1",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-5-5",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-5-5",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-5-5",
    "CLAUDE_CODE_USE_VERTEX": "1",
    "ANTHROPIC_VERTEX_PROJECT_ID": "som-nero-plevriti-deidbdf",
    "CLOUD_ML_REGION": "global"
  },
  "permissions": {"defaultMode": "auto"},
  "hooks": {
    "PreToolUse": [{"matcher": "Bash", "hooks": [
      {"type": "command", "command": "$H/phi-vet-gate.sh"},
      {"type": "command", "command": "$H/mnt-delete-gate.sh"},
      {"type": "command", "command": "$H/provision-gate.sh"}]}],
    "SessionStart": [{"hooks": [{"type": "command", "command": "$H/post-compact-reinject.sh"}]}],
    "PreCompact": [{"hooks": [{"type": "command", "command": "$H/precompact-wrapup-nudge.sh"}]}]
  },
  "worktree": {"bgIsolation": "none"}
}
EOF
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$SETTINGS" || die "wrote invalid JSON to $SETTINGS"
  note "wrote $SETTINGS"
fi
for h in phi-vet-gate mnt-delete-gate provision-gate post-compact-reinject precompact-wrapup-nudge; do
  [ -x "$RS_DIR/hooks/$h.sh" ] || die "hook $RS_DIR/hooks/$h.sh missing or not executable"
done

note "4. Google credentials for Vertex"
command -v gcloud >/dev/null 2>&1 || die "gcloud not installed"
gcloud auth application-default print-access-token >/dev/null 2>&1 \
  || die "no Google credentials Claude can use; run: gcloud auth application-default login"

if [ "${SKIP_SMOKE:-}" = 1 ]; then
  note "5. skipped (SKIP_SMOKE=1)"
else
  note "5. one-word reply through Vertex"
  reply="$(cd "$HOME" && env -u ANTHROPIC_API_KEY timeout 180 claude -p "Reply with the single word READY." 2>&1)"
  grep -q READY <<<"$reply" || die "Claude did not answer through Vertex: $(tail -5 <<<"$reply")"
fi

echo ""
echo "PASS: Claude Code ready (start a session with: cd ~/code && claude)"
