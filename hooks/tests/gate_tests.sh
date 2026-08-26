#!/bin/bash
# Table-driven regression suite for the guardrail hooks. Part of the landing gate
# (see hooks/README.md). Run from anywhere:
#
#     bash hooks/tests/gate_tests.sh
#
# IMPORTANT: invoke it as `bash <this-file>` — never paste the test payloads onto
# a command line, or the LIVE mnt-delete/provision gates will trip on them.
#
# Exit 0 iff every assertion passes; nonzero (with a FAIL list) otherwise.
set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
MNT="$HOOKS_DIR/mnt-delete-gate.sh"
PROV="$HOOKS_DIR/provision-gate.sh"
REINJECT="$HOOKS_DIR/post-compact-reinject.sh"
PRECOMPACT="$HOOKS_DIR/precompact-wrapup-nudge.sh"

pass=0; fail=0; fails=()

# decision <hook> <command-string>  -> echoes "ask" or "silent"
decision() {
  local hook="$1" cmd="$2" out
  out="$(jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}' | "$hook" 2>/dev/null)"
  if printf '%s' "$out" | grep -q '"permissionDecision":"ask"'; then echo ask; else echo silent; fi
}

# expect_bash <hook> <ask|silent> <label> <command>
expect_bash() {
  local hook="$1" want="$2" label="$3" cmd="$4" got
  got="$(decision "$hook" "$cmd")"
  if [ "$got" = "$want" ]; then pass=$((pass+1)); printf '  PASS [%-6s] %s\n' "$got" "$label"
  else fail=$((fail+1)); fails+=("$label (want=$want got=$got)"); printf '  FAIL want=%-6s got=%-6s %s\n' "$want" "$got" "$label"; fi
}

# expect_raw <hook> <ask|silent> <label> <raw-json-stdin>
expect_raw() {
  local hook="$1" want="$2" label="$3" json="$4" out got
  out="$(printf '%s' "$json" | "$hook" 2>/dev/null)"
  if printf '%s' "$out" | grep -q '"permissionDecision":"ask"'; then got=ask; else got=silent; fi
  if [ "$got" = "$want" ]; then pass=$((pass+1)); printf '  PASS [%-6s] %s\n' "$got" "$label"
  else fail=$((fail+1)); fails+=("$label (want=$want got=$got)"); printf '  FAIL want=%-6s got=%-6s %s\n' "$want" "$got" "$label"; fi
}

# expect_stdout <hook> <present|absent> <needle> <label> <raw-json-stdin>
expect_stdout() {
  local hook="$1" mode="$2" needle="$3" label="$4" json="$5" out got
  out="$(printf '%s' "$json" | "$hook" 2>/dev/null)"
  if printf '%s' "$out" | grep -q -- "$needle"; then got=present; else got=absent; fi
  if [ "$got" = "$mode" ]; then pass=$((pass+1)); printf '  PASS [%-7s] %s\n' "$got" "$label"
  else fail=$((fail+1)); fails+=("$label (want=$mode got=$got)"); printf '  FAIL want=%-7s got=%-7s %s\n' "$mode" "$got" "$label"; fi
}

echo "== mnt-delete-gate: real destructive /mnt -> ask =="
expect_bash "$MNT" ask    "rm -rf /mnt"                       'rm -rf /mnt/su-vista/x'
expect_bash "$MNT" ask    "quoted /mnt path w/ space"         'rm -rf "/mnt/su vista/x"'
expect_bash "$MNT" ask    "find /mnt -delete"                 'find /mnt/x -type f -delete'
expect_bash "$MNT" ask    "rsync --delete into /mnt"          'rsync -a --delete src/ /mnt/dst/'
expect_bash "$MNT" ask    "gsutil rm /mnt"                    'gsutil rm /mnt/bucket/f'
expect_bash "$MNT" ask    "dd of=/mnt"                        'dd if=/dev/zero of=/mnt/x bs=1M'
expect_bash "$MNT" ask    "rmdir /mnt (NEW)"                  'rmdir /mnt/empty'
expect_bash "$MNT" ask    "mv OUT of /mnt (NEW)"              'mv /mnt/x /tmp/x'
expect_bash "$MNT" ask    "redirect-overwrite > /mnt (NEW)"   ': > /mnt/x'
expect_bash "$MNT" ask    "heredoc THEN rm /mnt (regr fix)"   $'cat <<EOF\nhi\nEOF\nrm -rf /mnt/x'
expect_bash "$MNT" ask    "here-string THEN rm /mnt"          $'read x <<< y\nrm -rf /mnt/x'

echo "== mnt-delete-gate: benign -> silent =="
expect_bash "$MNT" silent "ls /mnt (read)"                    'ls -la /mnt'
expect_bash "$MNT" silent "rm elsewhere (no /mnt)"            'rm -rf ~/code/scratch'
expect_bash "$MNT" silent "/mntx not a token"                 'rm -rf /mntx/foo'
expect_bash "$MNT" silent "read FROM /mnt to /tmp"            'cat /mnt/a > /tmp/b'
expect_bash "$MNT" silent "append >> /mnt (not truncate)"     'echo x >> /mnt/log'
expect_bash "$MNT" silent "heredoc body MENTIONS rm /mnt"     $'codex exec - <<PROMPT\nreview: rm -rf /mnt/x; find /mnt -delete\nPROMPT'

echo "== provision-gate: real provisioning -> ask =="
expect_bash "$PROV" ask    "disks create --size"             'gcloud compute disks create foo --size=1500GB'
expect_bash "$PROV" ask    "instances create"               'gcloud compute instances create vm1 --machine-type=n1-standard-8'
expect_bash "$PROV" ask    "disks resize"                   'gcloud compute disks resize foo --size=2000GB'
expect_bash "$PROV" ask    "gcloud beta ... create (NEW)"   'gcloud beta compute instances create vm'
expect_bash "$PROV" ask    "gcloud --project ... (NEW)"     'gcloud --project p compute instances create vm'
expect_bash "$PROV" ask    "gsutil -m mb (NEW)"             'gsutil -m mb gs://new'
expect_bash "$PROV" ask    "terraform -chdir apply (NEW)"   'terraform -chdir=infra apply'
expect_bash "$PROV" ask    "terraform apply"                'terraform apply -auto-approve'
expect_bash "$PROV" ask    "gsutil mb"                      'gsutil mb gs://newbucket'
expect_bash "$PROV" ask    "help-decoy before apply (fix)" 'echo --help && terraform apply'
expect_bash "$PROV" ask    "apply THEN unrelated --help"   'terraform apply && echo --help'
expect_bash "$PROV" ask    "heredoc THEN terraform apply"  $'cat <<EOF\nx\nEOF\nterraform apply'

echo "== provision-gate: benign -> silent =="
expect_bash "$PROV" silent "instances list"                 'gcloud compute instances list'
expect_bash "$PROV" silent "terraform plan"                 'terraform plan'
expect_bash "$PROV" silent "disks create --help (scoped)"  'gcloud compute disks create --help'
expect_bash "$PROV" silent "instances create --dry-run"    'gcloud compute instances create vm --dry-run'
expect_bash "$PROV" silent "heredoc body MENTIONS create"  $'codex exec - <<PROMPT\nex: gcloud compute disks create foo\nPROMPT'

echo "== accepted conservative nags (co-occurrence, no shell parse) =="
# These are known FALSE POSITIVES we accept as safe-direction: without a real
# shell parser we cannot tell a quoted/commented mention from an executed verb.
expect_bash "$MNT"  ask "cross-subcmd rm /tmp && ls /mnt"   'rm -rf /tmp/x && ls /mnt'
expect_bash "$PROV" ask "commented # terraform apply"       'echo ok # terraform apply'
expect_bash "$MNT"  ask "mv INTO /mnt (adds data)"          'mv /tmp/x /mnt/'
# INCIDENTALLY silent: the closing quote makes `apply'` fail the trailing
# word-boundary. NOT reliable quote-awareness (a trailing space would still nag);
# asserted only to pin current behavior.
expect_bash "$PROV" silent "quoted 'terraform apply' (incidental)" $'printf \'%s\\n\' \'terraform apply\''

echo "== fail-closed: malformed / missing deps -> ask =="
expect_raw "$MNT"  ask "malformed JSON -> ask"              'not json at all'
expect_raw "$PROV" ask "malformed JSON -> ask"             '{"tool_name":'

echo "== non-Bash / empty -> silent =="
expect_raw "$MNT"  silent "non-Bash tool"                   '{"tool_name":"Read","tool_input":{"file_path":"/mnt/x"}}'
expect_raw "$PROV" silent "empty command"                   '{"tool_name":"Bash","tool_input":{"command":""}}'

echo "== lifecycle hooks =="
expect_stdout "$REINJECT"   present "NON-NEGOTIABLES" "post-compact reinject on source=compact" '{"source":"compact"}'
expect_stdout "$REINJECT"   absent  "NON-NEGOTIABLES" "reinject silent on source=startup"       '{"source":"startup"}'
expect_stdout "$PRECOMPACT" present "Auto-compact"    "precompact nudge on trigger=auto"        '{"trigger":"auto"}'
expect_stdout "$PRECOMPACT" absent  "Auto-compact"    "precompact silent on trigger=manual"     '{"trigger":"manual"}'

echo
echo "TOTAL: pass=$pass fail=$fail"
if [ "$fail" -ne 0 ]; then
  printf 'FAILURES:\n'; printf '  - %s\n' "${fails[@]}"
  exit 1
fi
