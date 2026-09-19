#!/usr/bin/env bash
# Does plans_offgit.py's doctor mode actually find every checkout on the machine?
#
# It claims to, and until 2026-09-19 it did not: it scanned ~/code/* only, which finds 50 of this
# machine's 146 checkouts. The 96 it missed are worktrees nested at <repo>/.claude/worktrees/*,
# worktrees parked outside ~/code, and they matter because a checkout that moves onto the migrated
# main loses its real docs/plans files and, without a link, can no longer open a plan doc at all.
#
# So this builds a throwaway repo with one of each shape and asserts doctor sees all four:
#
#   $CODE/paper-trail                                  the clone itself
#   $CODE/paper-trail/.claude/worktrees/wt-nested      a NESTED worktree   (was missed)
#   $OUTSIDE/wt-outside                                a worktree outside ~/code (was missed)
#   $CODE/paper-trail-extra                            a SEPARATE CLONE, no shared worktree list
#   $TMP/paper-trail-home                              a clone NOT UNDER ~/code at all (was missed;
#                                                      the real one is ~/paper-trail, which holds
#                                                      the live isolation plan)
#
# Everything runs against a scratch CODE_ROOT and PLANS_MOUNT. No real repo and no real mount
# folder is touched; the run aborts if either variable escapes the temp directory.
#
#   bash scripts/tests/plans_offgit_tests.sh

set -uo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SCRIPT="$HERE/../plans_offgit.py"
REPO="paper-trail"   # must be a name the script has in scope; the tree it points at is scratch

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export CODE_ROOT="$TMP/code"
export PLANS_MOUNT="$TMP/mount"
OUTSIDE="$TMP/outside"

case "$CODE_ROOT" in "$TMP"/*) ;; *) echo "REFUSING: CODE_ROOT outside the temp dir"; exit 2;; esac
case "$PLANS_MOUNT" in "$TMP"/*) ;; *) echo "REFUSING: PLANS_MOUNT outside the temp dir"; exit 2;; esac

mkdir -p "$CODE_ROOT" "$PLANS_MOUNT" "$OUTSIDE"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
check(){ if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (wanted [$3], got [$2])"; fi; }

q() { git -C "$1" "${@:2}" >/dev/null 2>&1; }

# ---------------------------------------------------------------- build the fixture
git init --bare -b main -q "$TMP/remote/$REPO.git"
git clone -q "$TMP/remote/$REPO.git" "$CODE_ROOT/$REPO" 2>/dev/null
MAIN="$CODE_ROOT/$REPO"
q "$MAIN" config user.email test@example.com
q "$MAIN" config user.name  Test
mkdir -p "$MAIN/docs/plans"
echo "shared plan" > "$MAIN/docs/plans/a.md"
q "$MAIN" add -A
q "$MAIN" commit -m "a plan doc"
q "$MAIN" push -u origin main

# the three checkout shapes, all created BEFORE the migration commit
q "$MAIN" worktree add -b nested  "$MAIN/.claude/worktrees/wt-nested"
q "$MAIN" worktree add -b outside "$OUTSIDE/wt-outside"
git clone -q "$TMP/remote/$REPO.git" "$CODE_ROOT/$REPO-extra"
EXTRA="$CODE_ROOT/$REPO-extra"
# a clone that is NOT under CODE_ROOT -- found only by scanning CODE_ROOT's parent
git clone -q "$TMP/remote/$REPO.git" "$TMP/$REPO-home"
HOMECLONE="$TMP/$REPO-home"

# the mount holds the canonical tree, plus one file that exists ONLY there
mkdir -p "$PLANS_MOUNT/$REPO"
cp "$MAIN/docs/plans/a.md" "$PLANS_MOUNT/$REPO/a.md"
echo "only on the mount" > "$PLANS_MOUNT/$REPO/mount-only.md"

# the migration commit itself, by hand -- this test is about doctor, not relink
q "$MAIN" rm -r --cached docs/plans
printf '\ndocs/plans\n' >> "$MAIN/.gitignore"
rm -rf "$MAIN/docs/plans"
ln -s "$PLANS_MOUNT/$REPO" "$MAIN/docs/plans"
q "$MAIN" add -A
q "$MAIN" commit -m "untrack docs/plans and link it to the mount"
q "$MAIN" push origin main

run_doctor() { uv run --script "$SCRIPT" doctor "$REPO" "$@" 2>&1; }

echo "plans_offgit doctor -- checkout discovery"

# ---------------------------------------------------------------- 1. discovery
OUT="$(run_doctor)"
for shape in "$MAIN" "$MAIN/.claude/worktrees/wt-nested" "$OUTSIDE/wt-outside" "$EXTRA" "$HOMECLONE"; do
  if printf '%s' "$OUT" | grep -qF " $shape "; then ok "doctor sees ${shape#$TMP/}"
  else bad "doctor never mentions ${shape#$TMP/}"; fi
done
check "all five checkouts listed" \
      "$(printf '%s' "$OUT" | grep -cE 'not yet|linked|would link|REAL DIR')" "5"

# ---------------------------------------------------------------- 2. pre-migration = left alone
check "a checkout still tracking docs/plans is reported 'not yet'" \
      "$(printf '%s' "$OUT" | grep -c 'not yet')" "4"
if [ -f "$MAIN/.claude/worktrees/wt-nested/docs/plans/a.md" ]; then
  ok "its real plan files are untouched"
else
  bad "a pre-migration checkout lost its real plan files"
fi

# ---------------------------------------------------------------- 3. after they move onto main
q "$MAIN/.claude/worktrees/wt-nested" merge main
q "$OUTSIDE/wt-outside"               merge main
q "$EXTRA" pull
q "$HOMECLONE" pull

check "git deleted the real files in the nested worktree" \
      "$([ -e "$MAIN/.claude/worktrees/wt-nested/docs/plans" ] && echo present || echo gone)" "gone"

OUT="$(run_doctor)"
check "dry run offers to link all four, and writes nothing" \
      "$(printf '%s' "$OUT" | grep -c 'would link')" "4"
check "dry run really is dry" \
      "$([ -e "$MAIN/.claude/worktrees/wt-nested/docs/plans" ] && echo present || echo gone)" "gone"

OUT="$(run_doctor --apply)"
check "apply links all four" "$(printf '%s' "$OUT" | grep -c 'LINKING')" "4"

# ---------------------------------------------------------------- 4. the link actually works
for c in "$MAIN/.claude/worktrees/wt-nested" "$OUTSIDE/wt-outside" "$EXTRA" "$HOMECLONE"; do
  n="$(basename "$c")"
  if [ -L "$c/docs/plans" ]; then ok "$n has a symlink"; else bad "$n has no symlink"; fi
  check "$n opens a file that exists only on the mount" \
        "$(cat "$c/docs/plans/mount-only.md" 2>/dev/null)" "only on the mount"
  check "$n shows a clean tree" "$(git -C "$c" status --short | wc -l)" "0"
done

# ---------------------------------------------------------------- 5. idempotent
OUT="$(run_doctor --apply)"
check "a second apply relinks nothing" "$(printf '%s' "$OUT" | grep -c 'LINKING')" "0"
check "and reports all five as linked"  "$(printf '%s' "$OUT" | grep -c 'linked')" "5"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
