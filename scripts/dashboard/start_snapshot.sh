#!/usr/bin/env bash
# Turn this machine's 5-minute dashboard snapshot (back) on, then take one now.
# For always-on shared boxes (weill): the snapshot stands itself down after STAND_DOWN_HOURS (default 12) with no
# busy session, no long job of yours and no session activity, and removes its own cron line. Run this again when you
# start new work there. Safe to run twice: it never adds a second line. Works from the mount copy in bin/.
#   bash <mount>/chaudhari_lab/phil/planning/dashboard/bin/start_snapshot.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dash="$(dirname "$here")"                       # .../planning/dashboard when run from bin/
[ -d "$dash/hosts" ] || { echo "ERROR: no hosts/ folder next to $here; run the copy in planning/dashboard/bin/"; exit 1; }
hours="${STAND_DOWN_HOURS:-12}"
cmd="python3 $here/snapshot_sessions.py --out $dash/hosts --stand-down-after $hours"
line="*/5 * * * * PATH=\$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin $cmd > \$HOME/.cache/work-dashboard.log 2>&1"
mkdir -p "$HOME/.cache"
touch "$HOME/.cache/work-dashboard.started"   # the stand-down clock starts now
cur="$(crontab -l 2>/dev/null || true)"
if [ "$(printf '%s\n' "$cur" | grep -F "snapshot_sessions.py")" = "$line" ]; then
  echo "cron line already there; leaving it"
else
  # Replace any older snapshot line (e.g. one without the stand-down) with this one; keep every other line.
  { printf '%s\n' "$cur" | grep -vF "snapshot_sessions.py" | grep -v '^$' || true; printf '%s\n' "$line"; } | crontab -
  echo "cron line set (stands down after $hours h with nothing running)"
fi
PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH" $cmd
f="$dash/hosts/$(hostname).json"
[ -s "$f" ] && echo "PASS: $f written $(date -r "$f" +%H:%M)" || { echo "ERROR: no snapshot at $f"; exit 1; }
