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

# ---------------------------------------------------------------- 6. relink refuses off-ref
# check reads origin/main; relink deletes the WORKING TREE and untracks THIS index. On a feature
# branch those differ, and the difference is unprotected -- a file tracked on the branch but not on
# main is never compared to the mount, and an EDIT to a tracked file is not compared either. So
# relink must refuse unless the checkout is actually sitting on the ref that was compared.
echo
echo "plans_offgit relink -- refuses when the checkout is not at the ref"

G="$TMP/guard"; GM="$TMP/guardmount"; mkdir -p "$G" "$GM/$REPO"
git init --bare -b main -q "$TMP/remote2/$REPO.git"
git clone -q "$TMP/remote2/$REPO.git" "$G/$REPO" 2>/dev/null
GR="$G/$REPO"
q "$GR" config user.email test@example.com
q "$GR" config user.name  Test
mkdir -p "$GR/docs/plans"
echo "on main and on the mount" > "$GR/docs/plans/a.md"
q "$GR" add -A; q "$GR" commit -m base; q "$GR" push -u origin main
cp "$GR/docs/plans/a.md" "$GM/$REPO/a.md"          # the mount matches main exactly

# now wander off main: one extra committed plan doc, and one uncommitted edit to a tracked one
q "$GR" checkout -b feature
echo "exists only on this branch" > "$GR/docs/plans/branch-only.md"
q "$GR" add -A; q "$GR" commit -m "a plan doc only this branch has"
echo "an edit that exists nowhere else" >> "$GR/docs/plans/a.md"

OUT="$(PLANS_MOUNT="$GM" CODE_ROOT="$G" uv run --script "$SCRIPT" relink "$REPO" --apply 2>&1)"; rc=$?
check "relink exits non-zero off-ref" "$rc" "1"
if printf '%s' "$OUT" | grep -q 'REFUSING'; then ok "and says it is refusing"; else bad "no refusal in output"; fi
check "the branch-only plan doc survives" \
      "$([ -f "$GR/docs/plans/branch-only.md" ] && echo kept || echo DELETED)" "kept"
check "the uncommitted edit survives" \
      "$(grep -c 'exists nowhere else' "$GR/docs/plans/a.md")" "1"
check "nothing was untracked" "$(git -C "$GR" ls-files docs/plans | wc -l)" "2"
check "no symlink was made" "$([ -L "$GR/docs/plans" ] && echo yes || echo no)" "no"

# and it proceeds once the checkout IS at the ref
q "$GR" stash
q "$GR" checkout main
OUT="$(PLANS_MOUNT="$GM" CODE_ROOT="$G" uv run --script "$SCRIPT" relink "$REPO" --apply 2>&1)"; rc=$?
check "on the ref, relink runs" "$rc" "0"
check "and links" "$([ -L "$GR/docs/plans" ] && echo yes || echo no)" "yes"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
