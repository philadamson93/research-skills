#!/bin/bash
# Claude Code PreToolUse hook that guards destructive Bash operations against the
# shared bucket mount (/mnt/... — irreplaceable data). Unlike the old string-match
# gate, this one BINDS each destructive verb to its actual target, resolves that
# target with `realpath -m` (so a delete that reaches the mount THROUGH a symlink
# is caught, and a delete that merely mentions /mnt in a sibling subcommand is
# not), and then decides three ways:
#
#   DENY  — the target resolves to a protected bucket root (the whole-mount-delete
#           catastrophe this hook exists to stop). Blocked outright, no prompt.
#   PASS  — the target is inside a named write-zone (planning/, session-docs/,
#           plan-explainers/, the named tmp/ scratch roots). Silent.
#   ASK   — a destructive op on the mount OUTSIDE those zones, OR a destructive
#           command whose target we cannot confidently parse (fail-closed).
#
# Wire-up: see hooks/README.md.
#
# Contract:
#   Stdin   — Claude Code PreToolUse JSON event
#             ({"tool_name":"Bash","tool_input":{"command":"..."},"cwd":...}).
#   Stdout  — empty on allow; on ASK/DENY, the hookSpecificOutput JSON with
#             permissionDecision "ask" or "deny".
#   Exit 0  — always (the decision travels via stdout JSON, not the exit code).
#
# Fail-closed everywhere it matters: a false NEGATIVE (a real mount delete going
# silent) is the dangerous failure, so parse uncertainty, a missing dependency,
# or a resolution error all resolve to ASK — never to silent-allow.
#
# Scope (honest — see README "Known limits"): the target extractor is a light,
# per-simple-command parser, NOT a full shell. It splits on && || ; | and
# newlines, strips heredoc bodies, sees through common wrappers (sudo, env,
# timeout, nice, ...) and leading control tokens, but does not expand
# vars / $() / eval. When it finds a destructive verb it cannot bind to a target,
# it ASKS.

set -uo pipefail

here="$(dirname "$(readlink -f "$0")")"
# shellcheck source=lib/shell-scan.sh
. "$here/lib/shell-scan.sh"

# ---- zones -----------------------------------------------------------------
# Protected roots: deleting any of these wipes a whole shared mount. DENY.
PROTECTED_ROOTS=(/mnt /mnt/su-vista-uscentral1 /mnt/su-vista-hot)
# Write-zones: scratch / working areas where routine deletes are expected. PASS.
# Each is matched as an exact root or a descendant — NOT a loose path segment, so
# a deep unrelated `.../production/tmp/...` is NOT auto-passed.
WRITE_ZONES=(
  /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning
  /mnt/su-vista-uscentral1/chaudhari_lab/phil/session-docs
  /mnt/su-vista-uscentral1/chaudhari_lab/phil/plan-explainers
  /mnt/su-vista-uscentral1/chaudhari_lab/tmp
  /mnt/su-vista-uscentral1/vistabench/tmp
)

is_on_mount() { case "$1" in /mnt|/mnt/*) return 0 ;; *) return 1 ;; esac; }

is_protected_root() {
  local r="$1" p
  for p in "${PROTECTED_ROOTS[@]}"; do [ "$r" = "$p" ] && return 0; done
  return 1
}

in_write_zone() {
  local r="$1" z
  for z in "${WRITE_ZONES[@]}"; do
    [ "$r" = "$z" ] && return 0
    case "$r" in "$z"/*) return 0 ;; esac
  done
  return 1
}

# classify_target <raw-path>  -> echoes "deny" or "ask" (nothing = pass/off-mount)
# Resolves relative paths against $cwd and follows symlinks via realpath -m. A
# resolution FAILURE is fail-closed to ASK (we don't know where it points).
classify_target() {
  local raw="$1" R
  [ -n "$raw" ] || return 0
  case "$raw" in /*) ;; *) raw="$cwd/$raw" ;; esac
  R="$(realpath -m -- "$raw" 2>/dev/null)" || { echo ask; return 0; }
  [ -n "$R" ] || { echo ask; return 0; }
  is_on_mount "$R" || return 0            # off-mount: not this gate's concern
  if is_protected_root "$R"; then echo deny; return 0; fi
  in_write_zone "$R" && return 0          # scratch zone: pass
  echo ask
}

# tokenize <simple-command>  -> one shell-word per line (quote-aware via xargs;
# falls back to quote-stripped whitespace split on a parse error).
tokenize() {
  local line="$1" out
  if out="$(printf '%s' "$line" | xargs printf '%s\n' 2>/dev/null)" && [ -n "$out" ]; then
    printf '%s\n' "$out"
    return 0
  fi
  line="${line//\"/}"; line="${line//\'/}"
  printf '%s\n' $line
}

# Wrapper words that precede the real command (and may carry their own options).
is_wrapper() {
  case "$1" in
    sudo|env|nice|ionice|timeout|stdbuf|nohup|command|builtin|exec|time|then|do|xargs) return 0 ;;
    *) return 1 ;;
  esac
}
# Short options (of the wrappers above) that consume the FOLLOWING token as their
# argument (union set; over-skipping only risks a fail-closed ASK, never a miss).
opt_takes_arg() {
  case "$1" in
    -u|-g|-U|-C|-h|-p|-r|-t|-T|-R|-D|-n|-c|-s|-k|-o|-i|-e|-P|-I|-d|-E) return 0 ;;
    *) return 1 ;;
  esac
}

# analyze_line <simple-command>
# Emits: first line "D" (a destructive verb/redirect is present) or "S"; then one
# "T<path>" line per candidate target (verb-bound operands + truncating redirects).
# A "D" with no T lines means: destructive, but target unparseable -> caller ASKs.
analyze_line() {
  local line="$1" i n verb start a sub seenrm rp red dur
  local destructive=0
  local -a T args nf targets
  mapfile -t T < <(tokenize "$line")
  n=${#T[@]}
  targets=()

  # --- find the verb: skip leading control chars, env-assignments, wrappers ---
  i=0
  # strip a standalone or glued leading control token from the first word
  if [ "$n" -gt 0 ]; then
    T[0]="${T[0]#!}"; T[0]="${T[0]#(}"; T[0]="${T[0]#\{}"
    [ -z "${T[0]}" ] && i=1
  fi
  while [ "$i" -lt "$n" ]; do
    a="${T[$i]}"
    case "$a" in
      '('|'{'|'!'|')'|'}') i=$((i+1)); continue ;;         # control tokens
      [A-Za-z_]*=*) i=$((i+1)); continue ;;                # env assignment
    esac
    if is_wrapper "$a"; then
      i=$((i+1))
      # consume this wrapper's options (and their args) and a leading duration
      while [ "$i" -lt "$n" ]; do
        case "${T[$i]}" in
          -*) if opt_takes_arg "${T[$i]}"; then i=$((i+2)); else i=$((i+1)); fi; continue ;;
          [0-9]*[smhd]|[0-9]*) i=$((i+1)); continue ;;      # timeout/nice duration
        esac
        break
      done
      continue
    fi
    break
  done

  if [ "$i" -lt "$n" ]; then
    verb="${T[$i]##*/}"                    # strip any path (e.g. /bin/rm)
    start=$((i+1))
    args=("${T[@]:$start}")
    case "$verb" in
      rm|rmdir|unlink|shred|truncate)
        destructive=1
        for a in "${args[@]}"; do case "$a" in --) ;; -*) ;; *) targets+=("$a") ;; esac; done ;;
      mv)
        destructive=1
        # -t DIR / --target-directory=DIR => EVERY operand is a source.
        local tflag=0
        for a in "${args[@]}"; do case "$a" in -t|--target-directory|--target-directory=*) tflag=1 ;; esac; done
        nf=(); local skipnext=0
        for a in "${args[@]}"; do
          if [ "$skipnext" -eq 1 ]; then skipnext=0; continue; fi
          case "$a" in
            -t) skipnext=1 ;;               # its arg is the dest dir, not a source
            --target-directory) skipnext=1 ;;
            --target-directory=*) ;;        # glued dest, ignore
            -*) ;;
            *) nf+=("$a") ;;
          esac
        done
        if [ "$tflag" -eq 1 ]; then
          targets+=("${nf[@]}")            # all operands are sources
        else
          local cnt=${#nf[@]}; local k
          if [ "$cnt" -ge 2 ]; then for ((k=0; k<cnt-1; k++)); do targets+=("${nf[$k]}"); done; fi
        fi ;;
      dd)
        for a in "${args[@]}"; do case "$a" in of=*) destructive=1; targets+=("${a#of=}") ;; esac; done ;;
      find)
        local has=0; for a in "${args[@]}"; do [ "$a" = "-delete" ] && has=1; done
        if [ "$has" -eq 1 ]; then
          destructive=1
          # skip leading traversal options (-H -L -P -Oxx -D flag) then collect
          # path operands until the expression (first remaining -token) begins.
          local j=0 m=${#args[@]}
          while [ "$j" -lt "$m" ]; do
            case "${args[$j]}" in
              -H|-L|-P|-O*) j=$((j+1)); continue ;;
              -D) j=$((j+2)); continue ;;
              -*) break ;;
              *) targets+=("${args[$j]}"); j=$((j+1)) ;;
            esac
          done
          # -delete present but no start path parsed -> leave targets empty (ASK)
        fi ;;
      rsync)
        local has=0; for a in "${args[@]}"; do case "$a" in --delete|--delete=*|--delete-*) has=1 ;; esac; done
        if [ "$has" -eq 1 ]; then
          destructive=1
          nf=(); for a in "${args[@]}"; do case "$a" in -*) ;; *) nf+=("$a") ;; esac; done
          local cnt=${#nf[@]}; [ "$cnt" -ge 1 ] && targets+=("${nf[$((cnt-1))]}")
        fi ;;
      gsutil)
        sub=""; for a in "${args[@]}"; do case "$a" in -*) ;; *) sub="$a"; break ;; esac; done
        if [ "$sub" = "rm" ]; then
          destructive=1; seenrm=0
          for a in "${args[@]}"; do
            if [ "$seenrm" -eq 0 ]; then [ "$a" = "rm" ] && seenrm=1; continue; fi
            case "$a" in -*) ;; *) targets+=("$a") ;; esac
          done
        fi ;;
      gcloud)
        if printf '%s\n' "${args[@]}" | grep -qx storage && printf '%s\n' "${args[@]}" | grep -qx rm; then
          destructive=1
          for a in "${args[@]}"; do case "$a" in storage|rm|-*) ;; *) targets+=("$a") ;; esac; done
        fi ;;
    esac
  fi

  # --- truncating redirects (verb-independent): EVERY single `>` onto a path ---
  # Excludes `>>` (append) and `>&` (fd dup).
  while IFS= read -r red; do
    [ -n "$red" ] || continue
    rp="${red##*>}"; rp="${rp#"${rp%%[![:space:]]*}"}"   # drop up to '>' and trim
    rp="${rp#[\"\']}"                                     # strip a leading quote
    if [ -n "$rp" ]; then destructive=1; targets+=("$rp"); fi
  done < <(printf '%s' "$line" | grep -oE "(^|[^>&])>[[:space:]]*['\"]?[^[:space:]'\"|;&<>]+")

  if [ "$destructive" -eq 1 ]; then printf 'D\n'; else printf 'S\n'; fi
  [ ${#targets[@]} -gt 0 ] && printf 'T%s\n' "${targets[@]}"
  return 0
}

# ---- 0. fail-closed dependency check (jq) ----------------------------------
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

cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty')"
[ -n "$cwd" ] || cwd="$PWD"

# Remove heredoc BODIES (data) but keep the opener and any post-terminator
# commands (see lib/shell-scan.sh for why the old tail-truncation was wrong).
scan="$(strip_heredoc_bodies "$cmd")"

# ---- 2. fast exit if there is nothing destructive at all -------------------
if ! echo "$scan" | grep -qE '\b(rm|rmdir|unlink|shred|truncate|mv|dd|rsync|find|gsutil|gcloud)\b' \
   && ! echo "$scan" | grep -q '>'; then
  exit 0
fi

# Split into simple commands on && || ; | (heredoc bodies already stripped).
simple="$(printf '%s\n' "$scan" | sed -E 's/(\|\||&&|;|\|)/\n/g')"

# realpath is required to bind targets. Without it, fail closed: ASK for any
# command that reaches destructive analysis (a relative/symlink target has no
# literal /mnt to fall back on, so a co-occurrence check would miss it).
if ! command -v realpath >/dev/null 2>&1; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    if [ "$(analyze_line "$line" | head -1)" = "D" ]; then
      emit_ask "/mnt delete gate degraded (realpath not found): a destructive command was issued and its target cannot be resolved. Confirm manually (fail closed)."
      exit 0
    fi
  done <<< "$simple"
  exit 0
fi

# ---- 3. classify each destructive target -----------------------------------
worst=silent
while IFS= read -r line; do
  [ -n "$line" ] || continue
  flag=""; ops=()
  while IFS= read -r ln; do
    if [ -z "$flag" ]; then flag="$ln"; continue; fi
    case "$ln" in T*) ops+=("${ln#T}") ;; esac
  done < <(analyze_line "$line")

  if [ "$flag" = "D" ] && [ ${#ops[@]} -eq 0 ]; then
    # destructive verb/redirect, but no target we could parse -> fail closed
    [ "$worst" = silent ] && worst=ask
  else
    for t in "${ops[@]}"; do
      d="$(classify_target "$t")"
      case "$d" in
        deny) worst=deny; break ;;
        ask)  [ "$worst" = silent ] && worst=ask ;;
      esac
    done
  fi
  [ "$worst" = deny ] && break
done <<< "$simple"

# ---- 4. emit the decision --------------------------------------------------
preview="$(printf '%s' "$cmd" | tr '\n' ' ' | cut -c1-200)"
case "$worst" in
  deny)
    emit_deny "/mnt delete gate: this command would delete a PROTECTED bucket root (a whole shared mount). This is blocked outright. Command: \`${preview}\`. If you truly intend this, do it outside Claude Code."
    ;;
  ask)
    emit_ask "/mnt delete gate: this command runs a destructive operation (delete / overwrite / move) on a path that resolves under /mnt (the shared bucket mount, which holds irreplaceable results/data), outside the known scratch write-zones — or its target could not be parsed. Command: \`${preview}\`. Confirm you intend to modify /mnt data before proceeding."
    ;;
esac
exit 0
