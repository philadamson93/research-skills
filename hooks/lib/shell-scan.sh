#!/bin/bash
# Shared helpers for the Bash ask-gates (mnt-delete-gate.sh, provision-gate.sh).
#
# Sourced, not executed. Both gates need identical heredoc-body handling and the
# same fail-closed / decision-emission contract, so those live here once (a single
# tested helper set) rather than duplicated — see hooks/README.md "Known limits".
#
# What lives here is ONLY the shared plumbing: heredoc-body stripping and the
# ask/deny JSON emitters. The two gates differ in how they DETECT:
#   - mnt-delete-gate.sh   binds each destructive verb to its actual argument,
#     splits on `&&`/`||`/`;`/`|`, and resolves the target with `realpath -m`
#     (so a delete reaching /mnt through a symlink is caught). Its own file
#     carries that parser.
#   - provision-gate.sh    still uses WHOLE-STRING co-occurrence on the
#     heredoc-body-stripped command (verb + object appearing together), NOT a
#     real shell parse: no verb/argument binding, no variable / `$()` / `eval`
#     expansion.
# Neither is a sandbox; the true backstop for /mnt is OS/IAM least-privilege on
# the mount. Both fail CLOSED (toward asking), never toward silent-allow.

# ---------------------------------------------------------------------------
# strip_heredoc_bodies <command-string>
#
# Prints the command with heredoc BODIES removed, while PRESERVING the opener
# line and any commands that follow each terminator. This is the correct fix for
# the earlier `${cmd%%<<*}` approach, which truncated everything after the first
# `<<` and thus silently dropped real trailing commands
# (e.g. `cat <<EOF ... EOF; rm -rf /mnt/x`).
#
# Why strip bodies at all: a heredoc body is DATA fed to another program (e.g. a
# review prompt piped to `codex exec`) and must not trip a gate merely by
# mentioning `/mnt` / `rm` / `terraform apply`.
#
# Detection is deliberately CONSERVATIVE (fail toward keeping text = fail toward
# asking): an opener is recognized only when `<<[-]WORD` (optionally quoted) is
# the last token on the line, save trailing redirects. Here-strings (`<<<`) have
# no body and are left intact. Ambiguous constructs (e.g. arithmetic `<<`) are
# left intact, so at worst we keep body text and nag — never silently drop a real
# command.
strip_heredoc_bodies() {
  local input="$1" delim="" line trimmed d
  while IFS= read -r line; do
    if [ -n "$delim" ]; then
      # Inside a heredoc body: drop lines until the terminator (which is also
      # dropped). `<<-` allows a leading-tab-stripped terminator, so compare the
      # left-trimmed line too.
      trimmed="${line#"${line%%[![:space:]]*}"}"
      if [ "$line" = "$delim" ] || [ "$trimmed" = "$delim" ]; then
        delim=""
      fi
      continue
    fi

    # Not inside a body: this is command text — keep it.
    printf '%s\n' "$line"

    # Here-strings (`<<<`) carry no body; never treat them as an opener.
    case "$line" in
      *"<<<"*) continue ;;
    esac

    # Recognize a heredoc opener only when the (optionally quoted) delimiter word
    # is the last token on the line, save trailing redirects — this excludes
    # arithmetic `<<` and mid-line `<<` noise (fail toward NOT stripping).
    if [[ "$line" =~ \<\<-?[[:space:]]*(\"[^\"]+\"|\'[^\']+\'|[A-Za-z_][A-Za-z0-9_]*)[[:space:]]*([<>|&].*)?$ ]]; then
      d="${BASH_REMATCH[1]}"
      d="${d%\"}"; d="${d#\"}"; d="${d%\'}"; d="${d#\'}"
      delim="$d"
    fi
  done <<< "$input"
}

# ---------------------------------------------------------------------------
# emit_decision <ask|deny> <reason>  — print the PreToolUse decision JSON on
# stdout. Uses jq when present; falls back to a hand-built JSON string so the
# gate still fails CLOSED (asks/denies) even if jq is missing.
emit_decision() {
  local decision="$1" reason="$2"
  if command -v jq >/dev/null 2>&1; then
    jq -nc --arg d "$decision" --arg r "$reason" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  else
    # Minimal manual JSON escaping (backslash, double-quote, newline) for the
    # jq-absent fail-closed path.
    local esc="${reason//\\/\\\\}"; esc="${esc//\"/\\\"}"; esc="${esc//$'\n'/ }"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"%s","permissionDecisionReason":"%s"}}\n' "$decision" "$esc"
  fi
}

# emit_ask <reason>  — prompt the human (Y/N); they decide.
emit_ask()  { emit_decision ask  "$1"; }
# emit_deny <reason> — block outright (no prompt); reserved for catastrophic,
# never-intended operations (e.g. deleting a whole bucket mount root).
emit_deny() { emit_decision deny "$1"; }
