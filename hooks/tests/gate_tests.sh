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

# decision <hook> <command-string>  -> echoes "deny", "ask", or "silent"
decision() {
  local hook="$1" cmd="$2" out
  out="$(jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}' | "$hook" 2>/dev/null)"
  if   printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then echo deny
  elif printf '%s' "$out" | grep -q '"permissionDecision":"ask"';  then echo ask
  else echo silent; fi
}

# expect_bash <hook> <ask|silent> <label> <command>
expect_bash() {
  local hook="$1" want="$2" label="$3" cmd="$4" got
  got="$(decision "$hook" "$cmd")"
  if [ "$got" = "$want" ]; then pass=$((pass+1)); printf '  PASS [%-6s] %s\n' "$got" "$label"
  else fail=$((fail+1)); fails+=("$label (want=$want got=$got)"); printf '  FAIL want=%-6s got=%-6s %s\n' "$want" "$got" "$label"; fi
}

# expect_cwd <hook> <deny|ask|silent> <label> <command> <cwd>
# Like expect_bash but supplies the event's .cwd, so relative-path resolution
# (realpath against the tool's working directory) is exercised.
expect_cwd() {
  local hook="$1" want="$2" label="$3" cmd="$4" cwdv="$5" out got
  out="$(jq -nc --arg c "$cmd" --arg w "$cwdv" '{tool_name:"Bash",tool_input:{command:$c},cwd:$w}' | "$hook" 2>/dev/null)"
  if   printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then got=deny
  elif printf '%s' "$out" | grep -q '"permissionDecision":"ask"';  then got=ask
  else got=silent; fi
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

echo "== mnt-delete-gate: protected bucket root -> DENY =="
expect_bash "$MNT" deny   "rm whole mount root"              'rm -rf /mnt/su-vista-uscentral1'
expect_bash "$MNT" deny   "rm ro mount root"                 'rm -rf /mnt/su-vista-hot'
expect_bash "$MNT" deny   "rm /mnt itself"                   'rm -rf /mnt'
expect_bash "$MNT" deny   "mount root w/ trailing slash"     'rm -rf /mnt/su-vista-uscentral1/'

echo "== mnt-delete-gate: write-zone deletes -> silent (PASS) =="
ZP=/mnt/su-vista-uscentral1/chaudhari_lab/phil
expect_bash "$MNT" silent "delete in planning/"             "rm -rf $ZP/planning/boards/old.md"
expect_bash "$MNT" silent "delete in session-docs/"         "rm -rf $ZP/session-docs/note.md"
expect_bash "$MNT" silent "delete in plan-explainers/"      "rm -rf $ZP/plan-explainers/x.html"
expect_bash "$MNT" silent "delete in a tmp/ dir"            'rm -rf /mnt/su-vista-uscentral1/chaudhari_lab/tmp/scratch'
expect_bash "$MNT" ask    "delete on mount OUTSIDE a zone"  "rm -rf $ZP/reports/x"

echo "== mnt-delete-gate: target-bound (no longer nags on safe direction) =="
# These were false positives under the old whole-string co-occurrence gate. The
# target-bound gate resolves the destructive verb's actual argument, so a delete
# aimed off-mount is silent even when a sibling subcommand touches /mnt.
expect_bash "$MNT" silent "rm /tmp AND unrelated ls /mnt"   'rm -rf /tmp/x && ls /mnt'
expect_bash "$MNT" silent "mkdir /mnt zone AND rm /tmp"     'mkdir -p /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/boards && rm -rf /tmp/scratch'
expect_bash "$MNT" silent "mv INTO /mnt (dest, additive)"   'mv /tmp/x /mnt/'

echo "== mnt-delete-gate: symlink resolving onto /mnt (realpath, old gate MISSED) =="
# The old string-match gate waved these through: the command has no literal /mnt
# token, but the target resolves onto the mount through a symlink.
symd="$(mktemp -d)"
ln -s /mnt/su-vista-uscentral1/chaudhari_lab/phil/reports    "$symd/plans_link"
ln -s /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning   "$symd/zone_link"
expect_bash "$MNT" ask    "rm -rf through symlink onto /mnt" "rm -rf $symd/plans_link"
expect_bash "$MNT" ask    "rm a child BELOW a symlink onto /mnt" "rm -rf $symd/plans_link/sub"
expect_bash "$MNT" silent "rm through symlink into a zone"   "rm -rf $symd/zone_link/x"
rm -rf "$symd"

echo "== mnt-delete-gate: destructive verb, target unparseable -> ask (fail closed) =="
# Codex audit caught these going SILENT under the first rewrite: a wrapper or a
# control token hides the verb from a naive scan, or the verb has no argument the
# scanner can bind. The fix equates "destructive verb, no parseable target" with
# "unsafe" -> ask, never silent.
RP=/mnt/su-vista-uscentral1/chaudhari_lab/phil/reports/x
expect_bash "$MNT" ask    "sudo -u root rm on mount"        "sudo -u root rm -rf $RP"
expect_bash "$MNT" ask    "sudo rm on mount"                "sudo rm -rf $RP"
expect_bash "$MNT" ask    "timeout N rm on mount"           "timeout 30 rm -rf $RP"
expect_bash "$MNT" ask    "negated ! rm on mount"           "! rm -rf $RP"
expect_bash "$MNT" ask    "grouped ( rm ) on mount"         "( rm -rf $RP )"
expect_bash "$MNT" ask    "mv -t OUT of mount"              "mv -t /tmp $RP"
expect_bash "$MNT" ask    "mv --target-directory= OUT"      "mv --target-directory=/tmp $RP"
expect_bash "$MNT" ask    "find -L ... -delete on mount"    'find -L /mnt/su-vista-uscentral1/chaudhari_lab/phil/reports -delete'
expect_bash "$MNT" ask    "multi-redirect, mount first"     ": > $RP > /tmp/out"

echo "== mnt-delete-gate: verb-anchored, so incidental mentions stay silent =="
# The scanner binds destructiveness to a verb in command position, not to the
# string "rm" appearing anywhere. These must NOT nag.
expect_bash "$MNT" silent "commit -m mentions rm"           'git commit -m "rm old files"'
expect_bash "$MNT" silent "grep -r rm as an argument"       'grep -r rm .'
expect_bash "$MNT" silent "dd reads FROM mount (no of=)"    'dd if=/mnt/su-vista-uscentral1/x of=/tmp/y'
expect_bash "$MNT" silent "find on mount, no -delete"       'find /mnt/su-vista-uscentral1 -name x'

echo "== mnt-delete-gate: plan's second exact no-nag example =="
expect_bash "$MNT" silent "cp INTO mount THEN rm scratch"   'cp x /mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/ && rm scratch.txt'

echo "== mnt-delete-gate: an unapproved tmp segment is NOT a write-zone -> ask =="
# Only the explicitly-listed tmp roots pass. A 'tmp' segment anywhere else on the
# mount still asks (the first rewrite auto-passed any path with a tmp segment).
expect_bash "$MNT" ask    "deep .../production/tmp/ delete"  'rm -rf /mnt/su-vista-uscentral1/vistabench/production/tmp/checkpoints'

echo "== mnt-delete-gate: relative target resolved against the event's .cwd =="
expect_cwd  "$MNT" ask    "relative rm, CWD on mount outside a zone" 'rm -rf results' '/mnt/su-vista-uscentral1/chaudhari_lab/phil/reports'
expect_cwd  "$MNT" silent "relative rm, CWD inside a write-zone"     'rm -rf old'     '/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/boards'
expect_cwd  "$MNT" silent "relative rm, CWD off the mount"           'rm -rf build'   '/home/philadamson/code'

echo "== accepted conservative nags (co-occurrence, no shell parse) =="
# These are known FALSE POSITIVES we accept as safe-direction: without a real
# shell parser we cannot tell a quoted/commented mention from an executed verb.
expect_bash "$PROV" ask "commented # terraform apply"       'echo ok # terraform apply'
# INCIDENTALLY silent: the closing quote makes `apply'` fail the trailing
# word-boundary. NOT reliable quote-awareness (a trailing space would still nag);
# asserted only to pin current behavior.
expect_bash "$PROV" silent "quoted 'terraform apply' (incidental)" $'printf \'%s\\n\' \'terraform apply\''

echo "== fail-closed: malformed / missing deps -> ask =="
expect_raw "$MNT"  ask "malformed JSON -> ask"              'not json at all'
expect_raw "$PROV" ask "malformed JSON -> ask"             '{"tool_name":'

echo "== mnt-delete-gate: realpath unavailable -> fail closed =="
# The gate resolves targets with `realpath`. If it's missing, it cannot prove a
# path is off-mount, so a destructive verb must ASK (never silently allow); a
# non-destructive command stays silent. Simulate absence with a PATH that has
# every tool the gate needs EXCEPT realpath.
norp="$(mktemp -d)"
for t in bash jq grep sed xargs tr cut cat head readlink dirname env; do
  p="$(command -v "$t" 2>/dev/null)" && ln -s "$p" "$norp/$t"
done
norp_rm="$(jq -nc '{tool_name:"Bash",tool_input:{command:"rm -rf /mnt/su-vista-uscentral1/chaudhari_lab/phil/reports/x"}}' | PATH="$norp" "$MNT" 2>/dev/null)"
if printf '%s' "$norp_rm" | grep -q '"permissionDecision":"ask"'; then
  pass=$((pass+1)); printf '  PASS [%-6s] %s\n' ask "no realpath + destructive -> ask"
else
  fail=$((fail+1)); fails+=("no realpath + destructive -> ask (got: $norp_rm)"); printf '  FAIL %s\n' "no realpath + destructive -> ask"
fi
norp_ls="$(jq -nc '{tool_name:"Bash",tool_input:{command:"ls /mnt"}}' | PATH="$norp" "$MNT" 2>/dev/null)"
if [ -z "$norp_ls" ]; then
  pass=$((pass+1)); printf '  PASS [%-6s] %s\n' silent "no realpath + non-destructive -> silent"
else
  fail=$((fail+1)); fails+=("no realpath + non-destructive -> silent (got: $norp_ls)"); printf '  FAIL %s\n' "no realpath + non-destructive -> silent"
fi
rm -rf "$norp"

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
