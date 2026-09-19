#!/usr/bin/env bash
# Does the PHI gate ask for a read only on prose that is ENTERING the repo?
#
# The read exists to catch editorialization and private content in words being added. A file
# being DELETED puts no new words anywhere, so it needs no read -- and counting one as if it
# did is not a cosmetic slip: taking the ~1,080 plan docs out of git means commits that are
# almost entirely deletions, and the old count would have asked the user to read and
# acknowledge every one of them. That is precisely the cost the migration exists to remove.
#
# What must stay true, and is asserted below: an ADDED doc still needs a read, a MODIFIED doc
# still needs a read, and the added half of a RENAME still needs a read. Only deletions are free.
#
#   bash hooks/tests/phi_vet_gate_tests.sh

set -uo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
HOOK="$HERE/../phi-vet-gate.sh"

if [ -x "$HERE/../lib/is-phi-free-machine.sh" ] && "$HERE/../lib/is-phi-free-machine.sh"; then
  echo "SKIPPED: this machine is on the PHI-FREE allowlist, so the gate is inert here."
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# basename must match the gate's medical-repo pattern (vista-*) or it exits early by design
REPO="$TMP/vista-scratch"
git init -q -b main "$REPO"
git -C "$REPO" config user.email test@example.com
git -C "$REPO" config user.name  Test

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
check(){ if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (wanted [$3], got [$2])"; fi; }

# run the hook as Claude Code would, and print its block reason (empty string = allowed)
fire() {
  printf '{"tool_name":"Bash","tool_input":{"command":"git -C %s commit -m x"}}' "$REPO" \
    | bash "$HOOK" 2>/dev/null | jq -r '.reason // empty'
}
# the "N are docs requiring..." number the gate reports
docs_asked() { fire | grep -oE 'of which [0-9]+ are docs' | grep -oE '[0-9]+' | head -1; }
# the number it says are deletions needing no read; 0 when it makes no such claim
docs_deleted() { fire | grep -oE 'A further [0-9]+ doc file' | grep -oE '[0-9]+' | head -1; }

echo "phi-vet gate -- which staged docs cost the user a read"

# ---------------------------------------------------------------- a baseline commit to delete from
mkdir -p "$REPO/docs/plans"
for n in one two three; do echo "plan $n" > "$REPO/docs/plans/$n.md"; done
echo "print(1)" > "$REPO/code.py"
git -C "$REPO" add -A
git -C "$REPO" -c core.hooksPath=/dev/null commit -q -m baseline

# ---------------------------------------------------------------- 1. code only
echo "print(2)" > "$REPO/code.py"
git -C "$REPO" add code.py
check "a code-only commit asks for no reads" "$(docs_asked)" "0"
check "and claims no deletions"              "$(docs_deleted)" ""
git -C "$REPO" reset -q

# ---------------------------------------------------------------- 2. an ADDED doc still costs a read
git -C "$REPO" checkout -q -- code.py
echo "brand new prose" > "$REPO/NOTES.md"
git -C "$REPO" add NOTES.md
check "an added doc still costs a read" "$(docs_asked)" "1"
git -C "$REPO" reset -q; rm -f "$REPO/NOTES.md"

# ---------------------------------------------------------------- 3. a MODIFIED doc still costs a read
echo "edited prose" >> "$REPO/docs/plans/one.md"
git -C "$REPO" add docs/plans/one.md
check "a modified doc still costs a read" "$(docs_asked)" "1"
git -C "$REPO" reset -q; git -C "$REPO" checkout -q -- docs/plans/one.md

# ---------------------------------------------------------------- 4. deletions only -- the migration shape
git -C "$REPO" rm -q docs/plans/one.md docs/plans/two.md docs/plans/three.md
check "three deleted docs cost no reads"        "$(docs_asked)" "0"
check "and the gate says so out loud, naming 3" "$(docs_deleted)" "3"
if fire | grep -q "must not be turned into an acknowledgement request"; then
  ok "it tells the next agent not to ask for them"
else
  bad "nothing stops the next agent asking for 3 acknowledgements"
fi
git -C "$REPO" reset -q; git -C "$REPO" checkout -q -- docs/plans

# ---------------------------------------------------------------- 5. mixed: adds are not hidden by deletes
echo "brand new prose" > "$REPO/NOTES.md"
git -C "$REPO" add NOTES.md
git -C "$REPO" rm -q docs/plans/two.md docs/plans/three.md
check "an added doc is still surfaced alongside deletions" "$(docs_asked)" "1"
check "and the two deletions are reported separately"      "$(docs_deleted)" "2"
git -C "$REPO" reset -q; rm -f "$REPO/NOTES.md"; git -C "$REPO" checkout -q -- docs/plans

# ---------------------------------------------------------------- 6. a rename is not a free deletion
git -C "$REPO" mv docs/plans/one.md docs/plans/renamed.md
check "the added half of a rename still costs a read" "$(docs_asked)" "1"
git -C "$REPO" reset -q; git -C "$REPO" checkout -q -- docs/plans; rm -f "$REPO/docs/plans/renamed.md"

# ---------------------------------------------------------------- 7. the gate still actually gates
git -C "$REPO" rm -q docs/plans/one.md
if [ -n "$(fire)" ]; then ok "a deletions-only commit is STILL blocked until signed off"
else bad "deletions-only slipped through the gate entirely"; fi

# ---------------------------------------------------------------- 8. a marker still clears it
CGD="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)"
TREE="$(git -C "$REPO" write-tree)"
mkdir -p "$CGD/phi-vet"; echo "signed" > "$CGD/phi-vet/$TREE.signed-off"
check "and a sign-off marker clears it" "$(fire)" ""
rm -f "$CGD/phi-vet/$TREE.signed-off"
git -C "$REPO" reset -q; git -C "$REPO" checkout -q -- docs/plans

# ---------------------------------------------------------------- 9. non-commit is untouched
OUT="$(printf '{"tool_name":"Bash","tool_input":{"command":"git -C %s status"}}' "$REPO" | bash "$HOOK" 2>/dev/null)"
check "a non-commit command is not gated" "$OUT" ""

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
