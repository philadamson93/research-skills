Reference: claude_ops.md

# VM-Shell-Guard — PreToolUse hook enforcing the "no remote shell into a VM" PHI boundary

**Status: Implemented — locally verified, pending /commit-review + /land** (2026-07-15)
Hook `hooks/vm-shell-guard.sh` built on branch `feat/vm-shell-guard-hook` and verified
against the test matrix below: **27/27 block/allow cases + 5/5 edge cases pass** (incl.
wrapped/chained/`sshpass`/`gcloud alpha|beta`/IAP-tunnel/scp/rsync blocked; control-plane,
git-over-ssh, `ssh-keygen`/`ssh-add`, `os-login ssh-keys`, local rsync, and `git commit -m
"…ssh…"` allowed). Open Question #1 resolved as the recommended reuse design.

## Goal

Mechanically enforce the claude_ops.md hard rule **"Never Open a Remote Shell Into a VM
(PHI)"** — the section just added to `claude_ops.md` (currently uncommitted) whose closing
line still reads *"A PreToolUse hook to enforce this mechanically is on the research-skills
backlog — but the rule stands now, hook or not."* This plan builds that hook.

**Why a hook, not just prose.** The rule is a PHI boundary: a local/planner Claude that
opens a shell into a project VM pulls VM state (dir listings, file contents, query output)
into this session's transcript, which lives *outside* the PHI boundary — a PHI
exposure/exfiltration risk **regardless of intent** (a read-only `ls`/`cat` is as forbidden
as anything else). claude_ops.md is loaded every session, but under context pressure a
well-intentioned session can drift past it and reach for `gcloud compute ssh` to "just
check something." The hook is the tripwire that catches that reflex.

**Why a hook, not a `deny` rule** (decided with Phil, 2026-07-15): a `permissions.deny`
entry is prefix-matched only (misses `timeout 30 gcloud compute ssh …`, `echo x && ssh vm`,
wrapped forms), cannot inject the *teaching* block-reason that steers the model to the
prescribed remedy (hand the command to the user) instead of provoking a rephrase-and-retry,
and cannot cleanly carve the **allowed** control-plane calls (`gcloud compute instances
list/describe`) from the forbidden `gcloud compute ssh`. The hook does all three, regexes
the whole command string, and lands as a reviewed artifact in the public repo next to its
sibling `phi-vet-gate.sh`.

## Approach

A new `PreToolUse` (Bash-matcher) hook, `hooks/vm-shell-guard.sh`, mirroring the established
contract and structure of `hooks/phi-vet-gate.sh`:

- **Wire contract** (identical to phi-vet-gate): stdin = Claude Code PreToolUse JSON event;
  stdout empty ⇒ allow; stdout `{"decision":"block","reason":…}` ⇒ block; parsed with `jq`.
- **Order of checks** (cheap → specific, exit-early like phi-vet-gate):
  1. **Machine gate** — reuse `hooks/lib/is-phi-free-machine.sh`. Fire the guard **only on
     planner (PHI-free) machines**; be inert on PHI-bearing VMs (so VM-side / fleet ssh is
     untouched). See *Machine gate* below.
  2. **Tool gate** — allow non-`Bash` tool calls (`ssh` can only ride a Bash command).
  3. **Command gate** — extract `.tool_input.command`; if it matches a **block pattern**
     (below) and none of the **allow carve-outs**, block with the teaching reason; else allow.

No companion skill. Unlike phi-vet (whose hook gates a *skill* that does the review work),
this hook has nothing to execute — the remedy is a **human** action (run it yourself / do it
in an executor session on the VM). The block reason carries the remedy inline. This matches
`hooks/README.md`'s "pair with a skill *where appropriate*" — here it isn't.

## Command matching — the behavioral spec

The block/allow **matrix is the contract** (the regexes are an implementation detail the
verification matrix pins down). Match verbs in **command position** — line start, or after a
shell separator (`;` `&&` `||` `|` `(` newline), tolerating leading wrappers (`sudo`,
`timeout <n>`, `nohup`, `env`, `VAR=val` assignments). Command-position matching is what lets
`echo "connect via ssh"` (ssh inside a string arg) pass while `echo hi && ssh vm` (ssh in
command position) blocks.

### BLOCK (scope = shell verbs **+ data-pull**, per Phil 2026-07-15)

| Command | Why blocked |
|---|---|
| `ssh vm-host` / `ssh user@vm 'ls /mnt/data'` | opens a remote shell / remote exec |
| `gcloud compute ssh phil-vm --zone …` | remote shell into VM |
| `gcloud alpha compute ssh …` / `gcloud beta compute ssh …` | same, alpha/beta surfaces |
| `gcloud compute start-iap-tunnel phil-vm 22 …` | SSH-over-IAP tunnel |
| `gcloud compute scp phil-vm:/mnt/data/x.csv .` | pulls VM data across the boundary |
| `scp phil-vm:/mnt/data/x.csv .` / `scp ./x phil-vm:/tmp/` | data pull/push over ssh |
| `rsync -avz phil-vm:/mnt/data/ ./local/` / `rsync -e ssh ./ user@phil-vm:/tmp/` | data sync over ssh |
| `timeout 30 gcloud compute ssh phil-vm` / `sudo ssh vm` / `echo hi && ssh vm` | wrapped / chained forms of the above |

### ALLOW (must NOT trip)

| Command | Why allowed |
|---|---|
| `gcloud compute instances list` / `describe phil-vm …` | control-plane metadata; never enters the VM (claude_ops explicitly permits) |
| `gcloud compute instances start`/`stop phil-vm` | control-plane; no shell |
| `git push` / `git pull` / `git clone git@github.com:…` | command is `git`; git-over-ssh to GitHub is not a VM shell |
| `ssh-keygen …` / `ssh-add …` / `ssh-copy-id …` | local key setup; the `ssh-` prefix (hyphen, not space) is excluded |
| `rsync -a /local/src /local/dst` | no remote spec (`host:` / `-e ssh`) → local-only |
| `echo "use ssh to connect"` / `cat notes-mentioning-ssh.md` | verb not in command position |

**Refinements baked into the patterns:**
- `ssh` matches only when followed by whitespace/end (so `ssh-keygen`/`ssh-add`/`ssh-copy-id`
  and `sshpass` don't false-trip on the leading token; a real `ssh` later in a `sshpass … ssh
  host` line still blocks).
- `scp` / `rsync` block **only** with a remote spec present (`\S+@?\S+:` target or `-e ssh`),
  so local-only `rsync`/`scp` pass.
- `gcloud … compute ssh|scp|start-iap-tunnel` matches the `compute <verb>` token sequence
  after a command-position `gcloud` (optionally `alpha`/`beta`), independent of interleaved
  flags (`--zone`, `--project`, `--command`).

**Known limitation** (state it, don't paper over — mirrors phi-vet's "can't see inside an
alias"): the hook sees only the command string. `bash myscript.sh` where `myscript.sh`
contains `ssh` is not caught — script interiors are a deeper layer. The guard is a tripwire
for direct invocations, which is where the accidental reach-in reflex actually fires.

## Machine gate — planner-only, via reuse of `is-phi-free-machine.sh`

Per Phil's choice: fire on **planner** machines, inert on **PHI-bearing VMs** (leaves
VM-side / fleet-orchestration ssh untouched). Implement by reusing the existing helper:

```bash
hook_dir="$(dirname "$0")"
# Guard is ACTIVE only on PHI-free (planner) machines. On a PHI VM (or a machine with no
# allowlist match) the helper exits non-zero and we go inert.
if ! { [ -x "$hook_dir/lib/is-phi-free-machine.sh" ] && "$hook_dir/lib/is-phi-free-machine.sh"; }; then
  exit 0   # not a confirmed planner → inert (VM-side ssh / fleet work unaffected)
fi
```

**One registration, coherent semantics — reuse over a new list.** A machine's presence in
`hooks/lib/phi-free-machines.local` is its "I am a planner" declaration. That single
registration *simultaneously* (a) silences `phi-vet` and (b) **arms** this guard. No new
allowlist file, no new `.gitignore` entry (`phi-free-machines.local` is already ignored).
Phil's Mac is already registered → guard active there today.

**Fail-open caveat (documented, narrow, self-correcting).** The one behavioral seam vs.
phi-vet's fail-*closed* posture: on an **unregistered** planner Mac (fresh clone, no `.local`
yet), `is-phi-free-machine.sh` exits non-zero, so this guard is **inert** — no ssh
protection until the machine is registered. This window is narrow and self-correcting: an
unregistered planner is *also* suffering phi-vet commit friction on every commit, which the
user fixes immediately by registering — and that same registration arms this guard.
claude_ops.md (loaded every session) still carries the rule in the meantime.

> **Open question (raise at /review-plan):** if we want strict fail-*closed* (guard fires on
> *unknown* machines too, inert only on a **confirmed** PHI-VM), that needs a *separate*
> positive allowlist of fleet VMs (`hooks/lib/vm-fleet-ssh-allowed.local` + `.example` +
> gitignore) — the guard would fire *everywhere except* listed fleet boxes. More correct for
> a PHI rule, but a second machine-registry to maintain and it flips the VM default to
> "blocked until registered." **Recommendation: ship the reuse design above** (narrow,
> self-correcting hole; zero new machinery) and only escalate to the dedicated list if the
> fail-open window proves real. Decide with eyes open.

## The block reason (teaching message)

```
🚫 PHI boundary — blocked a command that reaches into a project VM.

This opens a remote shell or pulls data from a VM (ssh / gcloud compute ssh / IAP tunnel /
scp / rsync). Per claude_ops.md → "Hard Boundary: Never Open a Remote Shell Into a VM (PHI)",
a local/planner Claude session must NEVER do this — even a read-only ls/cat/du — because the
VM holds PHI and its output would cross into this session's transcript, which lives OUTSIDE
the PHI boundary.

Do this instead:
- If VM state must be inspected or a command run there: hand the USER the exact command to
  run themselves (they paste back only PHI-free output), or do the work in an executor Claude
  session ON the VM. Never reach in from here.
- Cloud CONTROL-PLANE calls are fine and not blocked: `gcloud compute instances list` /
  `describe` (machine type, zone, disk) never enter the VM.

No silent bypass. If the user has explicitly authorized THIS command, they run it themselves
(e.g. the `!` prefix); do not re-issue it as a tool call.
```

## Files to Modify

- **`hooks/vm-shell-guard.sh`** *(new)* — the hook. ~50 lines: machine gate (reuse helper) →
  tool gate → command gate (block patterns + carve-outs) → `jq`-emitted block JSON. Header
  comment documents the contract, exactly like `phi-vet-gate.sh`. `chmod +x`.
- **`hooks/README.md`** — (1) add a row to the hooks table; (2) add a per-hook install section
  below phi-vet-gate's (Step 1 verify/chmod, Step 2 register in `~/.claude/settings.json`
  under the existing `PreToolUse`→`Bash` matcher array — *append*, don't replace; Step 3
  sanity check; Step 4 the runnable test matrix). Note it reuses the phi-free machine gate
  (inverted sense) and shares `phi-free-machines.local`.
- **`claude_ops.md`** — flip the closing line of the (currently uncommitted) "Hard Boundary"
  section from *"A PreToolUse hook to enforce this mechanically is on the research-skills
  backlog — but the rule stands now, hook or not."* to point at the now-existing
  `hooks/vm-shell-guard.sh`. **Sequencing:** that section is uncommitted (same workstream);
  land the rule text and the hook together, or the rule first then the hook — either way this
  edit rides on top of the existing uncommitted change (no parallel session to reconcile).
- **`backlog.md`** — no open entry exists for this (the "backlog" reference lived only in
  claude_ops.md). Optional: add a one-line *resolved* pointer to this plan for traceability.
- **Memory** — update `no-ssh-into-vm-phi-boundary.md`: enforcement hook is now
  implemented/landed (was "backlogged"), name the hook file.
- **`docs/plans/README.md`** — if research-skills maintains a plans feature table, add a row.
  (Verify at implementation time; the other plan doc here suggests it may not yet exist.)

## Open Questions

1. **Fail-open vs fail-closed machine gate** — reuse `phi-free-machines.local` (recommended,
   narrow self-correcting hole) vs. a dedicated fleet-VM allowlist (strict fail-closed, extra
   machinery). See the *Machine gate* callout. Decide at `/review-plan`.
2. **Hook filename** — `vm-shell-guard.sh` (chosen) vs `vm-reachin-guard.sh` /
   `no-vm-shell.sh`. Trivial; `vm-shell-guard` reads well and the scope note covers data-pull.
3. **Does any VM-side Claude session legitimately issue in-session `ssh` between fleet boxes?**
   (e.g. the shard-CT-preprocessing fan-out.) If yes, the planner-only gate already leaves it
   untouched (guard is inert on VMs) — so this is confirmation, not a blocker. If fleet
   orchestration is *operator-run scripts* rather than Claude tool calls, the hook never saw
   them anyway. Worth a one-line confirmation but does not change the design.

## Verification

**research-skills allows local code execution** (per its `CLAUDE.md`) and is **not** a PHI
repo — so this hook is directly testable here with piped JSON, exactly like phi-vet-gate's
"Step 4" scenarios. **No VM handoff, no `docs/vm-status/` doc** (that channel is for
smoke-test handoffs in the Mac/VM-split *project* repos).

The verification IS a **test matrix** run against the finished script — every BLOCK row must
emit `{"decision":"block",…}`, every ALLOW row must emit nothing (exit 0). Author it as a
runnable block in `hooks/README.md` Step 4:

```bash
HOOK=~/code/research-skills/hooks/vm-shell-guard.sh   # adjust path

blocks() { echo "$1" | jq -R '{tool_name:"Bash",tool_input:{command:.}}' | "$HOOK"; echo "exit=$?"; }

# --- must BLOCK (expect decision:block) ---
blocks 'ssh phil-vm'
blocks "ssh user@phil-vm 'ls /mnt/data'"
blocks 'gcloud compute ssh phil-vm --zone us-central1-a'
blocks 'gcloud alpha compute ssh phil-vm'
blocks 'gcloud compute start-iap-tunnel phil-vm 22 --local-host-port=localhost:2222'
blocks 'gcloud compute scp phil-vm:/mnt/data/x.csv .'
blocks 'scp phil-vm:/mnt/data/x.csv .'
blocks 'rsync -avz phil-vm:/mnt/data/ ./local/'
blocks 'timeout 30 gcloud compute ssh phil-vm'
blocks 'echo hi && ssh phil-vm'

# --- must ALLOW (expect empty stdout, exit=0) ---
blocks 'gcloud compute instances list'
blocks 'gcloud compute instances describe phil-vm --zone us-central1-a'
blocks 'git push origin main'
blocks 'git clone git@github.com:org/repo'
blocks 'ssh-keygen -t ed25519 -f ./id'
blocks 'rsync -a /local/src /local/dst'
blocks 'echo "connect via ssh to the box"'

# --- machine gate: on a PHI-VM (not phi-free) the guard is INERT even for ssh ---
# (verify on a VM, or temporarily by pointing at an empty/absent phi-free-machines.local)
```

Because execution is local, the implementing session runs this matrix itself and reports
pass/fail — no round-trip. A false **block** in an ALLOW row or a missed **block** in a BLOCK
row is a stop-and-fix.

## Landing & cleanup

- **Branch** — small, coherent, multi-file feature: `feat/vm-shell-guard-hook`. (Borderline
  vs. direct-on-main under claude_ops "docs/minor → main"; a new *enforcement hook* warrants a
  branch. Phil's call — noted as the one landing choice.)
- **Landing gate** — test matrix green (above); `/review-plan` sign-off on Open Question #1;
  appropriateness review via `/commit-review`. **No `/phi-vet`** — research-skills is a public
  non-PHI repo (doc/code-only, synthetic test strings, no data files); qualifies for the
  inline-sweep path.
- **Merge sequence** — single branch. Land the (currently uncommitted) claude_ops.md "Hard
  Boundary" section together with the hook so the rule and its enforcement arrive as one
  coherent state; `/land` → main → prune branch + worktree.
- **Commit split** (thematic, per claude_ops): (1) the hook + README; (2) the claude_ops.md
  line flip + the "Hard Boundary" section if not already committed; (3) backlog/plans-README
  pointers. Memory update is not a repo commit.
- **Cleanup on land** — `/land` Phase 4: mark this plan `Status: Completed`, prune branch
  (local+remote) + worktree, update memory `no-ssh-into-vm-phi-boundary.md` (hook landed).
