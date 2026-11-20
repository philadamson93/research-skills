#!/usr/bin/env bash
# Snapshot this machine's sessions to the mount, then rebuild the dashboard page.
# Safe to run from cron on every host; each host writes only its own snapshot file.
#   bash ~/code/research-skills/scripts/dashboard/refresh.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
python3 "$here/snapshot_sessions.py" "$@"
# Once a day (it exits at once if it already ran today): one Sonnet call proposes problems, capped at $5/day.
python3 "$here/daily_review.py" || echo "daily review failed; the page still builds"
python3 "$here/build_dashboard.py"
# Keep a copy of the snapshot script on the mount, so machines without this checkout can run it.
bin=/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/bin
mkdir -p "$bin" && cp "$here/snapshot_sessions.py" "$bin/.snapshot_sessions.py.tmp" && mv "$bin/.snapshot_sessions.py.tmp" "$bin/snapshot_sessions.py"
cp "$here/power_off.py" "$bin/.power_off.py.tmp" && mv "$bin/.power_off.py.tmp" "$bin/power_off.py"
cp "$here/send_for_review.py" "$bin/.send_for_review.py.tmp" && mv "$bin/.send_for_review.py.tmp" "$bin/send_for_review.py"
cp "$here/grill_page.py" "$bin/.grill_page.py.tmp" && mv "$bin/.grill_page.py.tmp" "$bin/grill_page.py"
cp "$here/start_snapshot.sh" "$bin/.start_snapshot.sh.tmp" && chmod +x "$bin/.start_snapshot.sh.tmp" && mv "$bin/.start_snapshot.sh.tmp" "$bin/start_snapshot.sh"
