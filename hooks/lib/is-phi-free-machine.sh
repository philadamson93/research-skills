#!/bin/bash
# Shared machine gate for the PHI tooling (the phi-vet skill + phi-vet-gate hook).
#
# Decides whether THIS machine is on the PHI-FREE allowlist.
#
#   Exit 0  => PHI-FREE. This machine is explicitly listed as never holding PHI
#              (e.g. a planner-only laptop with no BigQuery / data-mount access).
#              phi-vet should be INERT here: no scan, no hard commit gate.
#   Exit 1  => ASSUME PHI. This machine is NOT on the allowlist, so treat it as
#              PHI-bearing and keep phi-vet active.
#
# The allowlist itself is NOT in this (public) repo. It lives in a machine-local,
# git-ignored file next to this script:
#
#       hooks/lib/phi-free-machines.local
#
# one identifier per line (`#` comments and blank lines ignored). This keeps
# real machine names — which on managed Macs embed the hardware serial — out of
# public git history. See phi-free-machines.example for the format, and the
# "Machine gate" section of hooks/README.md.
#
# FAIL-CLOSED BY DESIGN. The default is "assume PHI". A machine is treated as
# PHI-free ONLY if the local allowlist file exists AND lists one of this host's
# names. Consequences (all safe):
#   - Fresh clone with no .local file       -> ASSUME PHI (gate active).
#   - PHI VM with no/old .local file         -> ASSUME PHI (gate active).
#   - PHI-free laptop whose name churns      -> harmless friction until re-listed.
# Exempting a machine requires a deliberate local edit to phi-free-machines.local;
# there is no env-var backdoor.
#
# Flags:
#   --explain   also print a one-line verdict to stdout (for the skill / humans).
#   --names     print this host's candidate identifiers (to populate the .local
#               file), then exit 0. Use the STABLE name, not a DHCP hostname.

set -uo pipefail

mode="verdict"
case "${1:-}" in
  --explain) mode="explain" ;;
  --names)   mode="names" ;;
esac

# --- collect this host's candidate identifiers ------------------------------
candidates=()
candidates+=("$(hostname 2>/dev/null || true)")
candidates+=("$(hostname -s 2>/dev/null || true)")
if command -v scutil >/dev/null 2>&1; then
  candidates+=("$(scutil --get ComputerName 2>/dev/null || true)")
  candidates+=("$(scutil --get LocalHostName 2>/dev/null || true)")
fi

if [ "$mode" = "names" ]; then
  echo "This host's candidate identifiers (add the STABLE one to phi-free-machines.local):"
  for cand in "${candidates[@]}"; do [ -n "$cand" ] && echo "  $cand"; done
  exit 0
fi

# --- load the machine-local allowlist ---------------------------------------
# Resolve next to this script (pwd -P follows the commands/ or hooks/ symlink to
# the physical clone).
script_dir="$(cd "$(dirname "$0")" 2>/dev/null && pwd -P)"
allow_file="$script_dir/phi-free-machines.local"

allow=()
if [ -f "$allow_file" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"                     # strip inline/whole-line comments
    line="$(printf '%s' "$line" | tr -d '[:space:]')"  # trim all whitespace
    [ -n "$line" ] && allow+=("$line")
  done < "$allow_file"
fi

# --- match case-insensitively -----------------------------------------------
shopt -s nocasematch 2>/dev/null || true
for a in "${allow[@]+"${allow[@]}"}"; do
  for cand in "${candidates[@]}"; do
    [ -n "$cand" ] || continue
    if [[ "$cand" == "$a" ]]; then
      [ "$mode" = "explain" ] && echo "PHI_FREE (matched local allowlist)"
      exit 0
    fi
  done
done

[ "$mode" = "explain" ] && echo "ASSUME_PHI (no local allowlist match; phi-vet active)"
exit 1
