#!/usr/bin/env bash
# How long a page sent from another machine takes to reach the dashboard website. Run ON THE VM THAT SERVES
# /phil-dashboard/ (vista-cohort, review server on port 8810):
#   bash check_review_latency.sh
# It uploads a throwaway file straight to the bucket (exactly what a send from another machine does), then asks
# the local review server for it once a second: first as a new file (like a new page), then after a change
# (like review-index.json being rewritten). PASS when both show within 90 s. Removes the file at the end.
set -uo pipefail
PORT="${PORT:-8810}"
NAME="review-latency-probe-$(hostname)-$$.json"
GS="gs://su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/$NAME"
URL="http://localhost:$PORT/phil-dashboard/$NAME"
tmp="$(mktemp)"
trap 'gcloud storage rm -q "$GS" >/dev/null 2>&1; rm -f "$tmp"' EXIT
curl -s -m 5 -o /dev/null "http://localhost:$PORT/phil-dashboard/" || { echo "FAIL: no review server on localhost:$PORT"; exit 2; }

poll() {   # $1 = text the response must contain; prints seconds, or fails after 300 s
  local t0=$SECONDS
  while (( SECONDS - t0 < 300 )); do
    if curl -s -m 5 "$URL" | grep -q "$1"; then echo $(( SECONDS - t0 )); return 0; fi
    sleep 1
  done
  echo 300; return 1
}

echo "first-$$" > "$tmp"; gcloud storage cp -q "$tmp" "$GS" >/dev/null || { echo "FAIL: upload to $GS"; exit 2; }
new_s=$(poll "first-$$"); new_ok=$?
echo "second-$$" > "$tmp"; gcloud storage cp -q "$tmp" "$GS" >/dev/null || { echo "FAIL: second upload"; exit 2; }
chg_s=$(poll "second-$$"); chg_ok=$?
echo "new file visible after ${new_s} s; changed file visible after ${chg_s} s"
if (( new_ok == 0 && chg_ok == 0 && new_s <= 90 && chg_s <= 90 )); then echo "PASS"; else echo "FAIL: over 90 s"; exit 1; fi
