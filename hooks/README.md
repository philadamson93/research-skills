# hooks/

Claude Code **hooks** that compose with the slash-command skills in `../commands/`. Unlike skills (which Claude *chooses* to invoke based on intent), hooks fire at fixed lifecycle events the harness recognises — `SessionStart`, `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`. They run as shell commands and can either **inject context** into Claude's view or **block** a tool call entirely.

## What lives here

| Hook | Lifecycle | Purpose |
|---|---|---|
| [`phi-vet-gate.sh`](phi-vet-gate.sh) | `PreToolUse` (Bash) | Hard-gates `git commit` in medical-data research repos until [`/phi-vet`](../commands/phi-vet.md) has signed off on the current staged tree. Forces both a PHI scan **and** explicit per-doc read-acknowledgement **from the human user** (Claude having read the file during the scan does NOT count — the user's own eyes on every staged doc are the load-bearing check) before any commit lands. Self-gates by machine via [`lib/is-phi-free-machine.sh`](#machine-gate--fail-closed-phi-free-allowlist) — inert on PHI-free machines. |
| [`vm-shell-guard.sh`](vm-shell-guard.sh) | `PreToolUse` (Bash) | Enforces the `claude_ops.md` hard rule *"Never Open a Remote Shell Into a VM (PHI)"*. Blocks Bash commands that open a remote shell into — or pull data from — a project VM (`ssh`, `gcloud [alpha\|beta] compute ssh`, IAP SSH tunnels, `gcloud compute scp`, `scp`/`rsync` over ssh) while allowing cloud control-plane calls (`gcloud compute instances list`/`describe`) and local ssh key setup (`ssh-keygen`, …). Reuses the shared [machine gate](#machine-gate--fail-closed-phi-free-allowlist) **inverted** — active on planner (PHI-FREE) machines, inert on the PHI VMs (so VM-side / fleet ssh is untouched). |

The companion script [`lib/is-phi-free-machine.sh`](lib/is-phi-free-machine.sh) is not a hook itself — it's the shared machine check that *both* the hook above and the [`/phi-vet`](../commands/phi-vet.md) skill consult so they never disagree about where PHI tooling is active. See [Machine gate](#machine-gate--fail-closed-phi-free-allowlist).

---

## phi-vet-gate.sh — installation

This hook makes `/phi-vet` non-optional in medical-data repos. Without it, a coding session under context pressure can drift past the skill and commit unreviewed content; with it, the harness refuses to let `git commit` run until the skill's marker file exists.

**Safe to install on every machine.** The hook self-gates by machine (see [Machine gate](#machine-gate--fail-closed-phi-free-allowlist) below): on a machine listed in the PHI-FREE allowlist it is inert and commits proceed normally. So you don't need divergent `settings.json` per machine — wire it the same way everywhere and let the allowlist decide where it actually fires. It depends on `lib/is-phi-free-machine.sh` sitting next to it under `hooks/`; the symlink/clone layout keeps them together.

### Prerequisites

- `jq` on `$PATH` (the hook parses Claude Code's PreToolUse JSON event with it).
- Your `research-skills` clone at a known absolute path. The examples below assume `~/code/research-skills` per the top-level [README](../README.md#one-shot-setup-on-a-fresh-vm-or-local-mac); adjust if yours lives elsewhere.

### Step 1 — Verify the script

```bash
ls -l ~/code/research-skills/hooks/phi-vet-gate.sh
chmod +x ~/code/research-skills/hooks/phi-vet-gate.sh  # if not already executable
```

### Step 2 — Register the hook in `~/.claude/settings.json`

Add the `hooks` block to your existing `~/.claude/settings.json`. If the file is currently `{}` or has just `effortLevel`, merge the structure below in:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/code/research-skills/hooks/phi-vet-gate.sh"
          }
        ]
      }
    ]
  }
}
```

Replace `/Users/YOUR_USERNAME/code/research-skills/...` with the absolute path on your machine (Claude Code does **not** expand `~` in hook command paths).

If you already have a `PreToolUse` block, append this hook entry to the array of matchers (you can have many; they fire in order).

### Step 3 — Sanity check

> **First confirm this machine isn't PHI-free.** Run `hooks/lib/is-phi-free-machine.sh --explain`. If it prints `PHI_FREE`, the hook is *supposed* to stay silent on every repo here (see [Machine gate](#machine-gate--fail-closed-phi-free-allowlist)) — the blocking behavior below only applies on a PHI-active (non-allowlisted) machine.

Open a fresh Claude Code session in any medical-data repo (`vista-eval`, `vista-ct`, `vista_bench`, `path-extract`, …) and ask Claude to make a trivial commit. The hook should block with output like:

> PHI gate: this commit lands in a medical-data research repo (`vista-eval`), and the staged tree `5336…` has not been signed off by `/phi-vet`. Required: invoke `/phi-vet` to (a) scan the staged content … (b) surface every doc file in the commit and require the user to explicitly acknowledge they have read it, (c) on full approval, write a sign-off marker at `.git/phi-vet/5336….signed-off`. Once the marker exists, re-attempting `git commit` will pass this gate.

Claude should then invoke `/phi-vet`, run the PHI scan, walk **you** through per-doc read-acknowledgement (one AskUserQuestion per staged doc — your "Yes, I read it" is what the marker depends on, not Claude's scan), write the marker, and re-attempt the commit.

In a non-medical repo (e.g., this `research-skills` repo itself), the hook stays silent and commits proceed as normal.

### Step 4 — Verify with the test scenarios (optional)

The hook is small and easy to exercise without making real commits:

```bash
HOOK=~/code/research-skills/hooks/phi-vet-gate.sh

# Non-Bash → silent
echo '{"tool_name":"Read","tool_input":{"file_path":"/foo"}}' | "$HOOK"; echo "exit=$?"

# Bash but not git commit → silent
echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' | "$HOOK"; echo "exit=$?"

# git commit in a medical repo → blocks (cd into the repo first)
( cd ~/code/vista-eval && echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m foo"}}' | "$HOOK" )

# git commit in this repo (non-medical) → silent
( cd ~/code/research-skills && echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m foo"}}' | "$HOOK" )
```

---

## vm-shell-guard.sh — installation

Blocks a local/planner Claude from opening a remote shell into — or pulling data from — a project VM. This is the mechanical enforcement of `claude_ops.md` → *"Hard Boundary: Never Open a Remote Shell Into a VM (PHI)"*: the VMs hold PHI, and a shell opened from a local Claude pulls VM output into this session's transcript, which lives *outside* the PHI boundary.

**Safe to install on every machine.** Like `phi-vet-gate.sh` it self-gates via the shared [machine gate](#machine-gate--fail-closed-phi-free-allowlist) — but **inverted**: it is active on **planner (PHI-FREE)** machines (where the reach-into-VM risk lives) and inert on the PHI VMs (so VM-side / fleet-orchestration ssh is untouched). It depends on `jq` on `$PATH`.

**No companion skill.** Unlike `phi-vet-gate.sh` (which gates the `/phi-vet` *skill*), this hook has nothing to execute — the remedy is a human action (run the command yourself, or do the work in an executor Claude session *on* the VM). The block reason carries that remedy inline.

### Step 1 — Verify the script

```bash
ls -l ~/code/research-skills/hooks/vm-shell-guard.sh
chmod +x ~/code/research-skills/hooks/vm-shell-guard.sh  # if not already executable
```

### Step 2 — Register the hook in `~/.claude/settings.json`

Append it to the existing `PreToolUse` → `Bash` matcher array (a matcher can hold many hooks; they fire in order — this one runs alongside `phi-vet-gate.sh`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "/Users/YOUR_USERNAME/code/research-skills/hooks/phi-vet-gate.sh" },
          { "type": "command", "command": "/Users/YOUR_USERNAME/code/research-skills/hooks/vm-shell-guard.sh" }
        ]
      }
    ]
  }
}
```

Use the absolute path (Claude Code does **not** expand `~` in hook command paths).

### Step 3 — Machine gate (shared with phi-vet)

This hook reuses the **same** `phi-free-machines.local` allowlist as `phi-vet` — one "I am a planner" registration *both* silences `phi-vet`'s commit gate AND arms this guard. Confirm this machine's status:

```bash
hooks/lib/is-phi-free-machine.sh --explain
# PHI_FREE   → this guard is ACTIVE here (blocks reach-into-VM commands)
# ASSUME_PHI → inert (a PHI VM, or an unregistered planner — see the seam below)
```

**Narrow seam vs. phi-vet's fail-*closed* posture:** an *unregistered* planner reads as `ASSUME_PHI` → this guard is inert until the machine is registered. The window is self-correcting: an unregistered planner is *also* getting `phi-vet` commit friction on every commit, and the same registration that stops that friction arms this guard. See [Machine gate](#machine-gate--fail-closed-phi-free-allowlist).

### Step 4 — Verify with the test matrix

The hook is easy to exercise without touching any VM (research-skills allows local execution and is non-PHI):

```bash
HOOK=~/code/research-skills/hooks/vm-shell-guard.sh
blk() { echo "$1" | jq -R '{tool_name:"Bash",tool_input:{command:.}}' | "$HOOK"; echo "  <exit $?>"; }

# --- must BLOCK (each prints a {"decision":"block",…} JSON) ---
blk 'ssh phil-vm'
blk 'gcloud compute ssh phil-vm --zone us-central1-a'
blk 'gcloud alpha compute ssh phil-vm'
blk 'gcloud compute start-iap-tunnel phil-vm 22 --local-host-port=localhost:2222'
blk 'gcloud compute scp phil-vm:/mnt/data/x.csv .'
blk 'scp phil-vm:/mnt/data/x.csv .'
blk 'rsync -avz phil-vm:/mnt/data/ ./local/'
blk 'timeout 30 gcloud compute ssh phil-vm'   # wrapped
blk 'echo hi && ssh phil-vm'                   # chained

# --- must ALLOW (each prints nothing) ---
blk 'gcloud compute instances list'            # control-plane
blk 'gcloud compute instances describe phil-vm --zone us-central1-a'
blk 'git push origin main'                      # git-over-ssh to GitHub, not a VM shell
blk 'ssh-keygen -t ed25519 -f ./id'             # local key setup
blk 'rsync -a /local/src /local/dst'            # local-only rsync
blk 'echo "connect via ssh to the box"'         # ssh only inside a string arg
```

On a **PHI-FREE** machine every BLOCK line emits block-JSON and every ALLOW line is silent. On a **PHI VM** the hook is inert (all silent) — verify there, or by temporarily pointing at an empty `phi-free-machines.local`.

### Uninstallation

Remove the corresponding entry from your `~/.claude/settings.json`. The script remains in this repo; restoring the hook is just re-adding the JSON.

---

## Machine gate — fail-closed PHI-FREE allowlist

PHI lives only on the data-bearing machine (the GCP / VM executor). A planner-only machine — e.g. a local laptop with no BigQuery credentials or data mounts — has no PHI to leak, so the gate there is pure friction. The hook therefore consults [`lib/is-phi-free-machine.sh`](lib/is-phi-free-machine.sh) **before anything else** and exits silently (allow) if this machine is on the PHI-FREE allowlist.

The same script is the [`/phi-vet`](../commands/phi-vet.md) skill's Step 0 check, so the skill and the hook always agree about where PHI tooling is live.

**Fail-closed by design.** The default is *assume PHI* — the gate is active everywhere **except** machines explicitly listed as PHI-free. Failure modes are deliberately the safe ones:

- A PHI VM that gets recreated/renamed and falls off any future allowlist → reverts to *assume PHI* → gate stays **on**.
- A PHI-free laptop whose name churns → loses its convenience exemption → harmless commit-gate friction until re-listed.
- The helper missing/unreadable next to the hook → the hook does **not** early-exit → gate stays **on**.

There is intentionally **no env-var backdoor** that could silently disable the gate on a PHI machine. Exempting a machine requires a deliberate edit to its local allowlist file.

### The allowlist is machine-local (not committed)

Real machine names — on managed Macs the `scutil` name often embeds the hardware serial — are kept **out of this public repo**. The committed [`lib/is-phi-free-machine.sh`](lib/is-phi-free-machine.sh) holds only the generic logic; it reads the actual names from a git-ignored file beside it:

```
hooks/lib/phi-free-machines.local      # git-ignored; one identifier per line
hooks/lib/phi-free-machines.example    # committed template showing the format
```

A fresh clone has no `.local` file, so every machine is treated as PHI-bearing (fail-closed) until you create one. The tradeoff vs. a committed allowlist: not shared/auditable across clones, but no machine identifiers leak into public history.

### Exempting a machine

On the machine you want to exempt (a planner-only laptop with no PHI), copy the template and add this host's **stable** identifier:

```bash
cd hooks/lib
cp phi-free-machines.example phi-free-machines.local
./is-phi-free-machine.sh --names   # prints this host's candidate names
# add the STABLE one (e.g. the macOS scutil name) to phi-free-machines.local,
# NOT a network/DHCP hostname that churns between networks
./is-phi-free-machine.sh --explain; echo "exit=$?"
# exit 0 → PHI_FREE (inert here);  exit 1 → ASSUME_PHI (gate active)
```

The script matches case-insensitively against `hostname`, `hostname -s`, and (on macOS) `scutil --get ComputerName` / `LocalHostName`.

## What counts as a "medical-data research repo"?

On a machine where the gate is active (not PHI-free), the hook trips its gate when **any** of the following is true for the target repo:

1. `CLAUDE.md` at the repo root contains case-insensitive keywords: `PHI`, `OMOP`, `NeuralFrame`, `DICOM`, `EHR`, `BigQuery`, `patient data`, `de-identif`.
2. The repo's basename matches a known pattern: `vista-*`, `vista_*`, `meds-*`, `meds_*`, `ehr-*`, `ehr_*`, `path-extract`, `crc-extraction-agent`, `contrastive-3d-onc`, `MedExtractAgent`, `ehrshot*`, `hf_ehr`.
3. Any file under `docs/` contains the strings `PHI` or `patient data`.

If you maintain a medical-data repo that doesn't hit any of these signals (rare), add one to its `CLAUDE.md` so the gate engages.

## What the gate is keyed on

Each pass through `/phi-vet` writes:

```
.git/phi-vet/<staged-tree-sha>.signed-off
```

where `<staged-tree-sha>` is the SHA-1 of `git write-tree` on the current index. **Different staged content → different SHA → the previous marker doesn't apply.** Staging additional changes after a sign-off invalidates the sign-off, forcing a fresh review.

These markers live under `.git/` and are local-only — they don't pollute the repo, aren't committed, and aren't shared between teammates. Each teammate signs off on their own commits.

## Bypassing the gate

The skill itself supports an explicit user-driven bypass ("skip the PHI check" / "bypass phi-vet"). When invoked that way, `/phi-vet` still writes the marker — but appends the rationale, so the bypass is auditable. **Never bypass silently** is a hard rule of the skill, not the hook.

There is no environment-variable bypass for the hook. If you genuinely need one (e.g., automated CI commit step that has its own data-governance review), open an issue rather than hacking around it; the right fix is a separate hook matcher pattern, not a back-door. Note the [machine gate](#machine-gate--fail-closed-phi-free-allowlist) is *not* a bypass: it disables the gate per-machine via a version-controlled allowlist (PHI-free machines only), not per-commit.

## Uninstallation

Remove the corresponding entry from your `~/.claude/settings.json`. The script remains in this repo; restoring the hook is just re-adding the JSON.

---

## Adding a new hook to this directory

1. Drop a `<name>.sh` here. Read Claude Code's PreToolUse / SessionStart / etc. JSON contract — Claude Code [documents the hook payload format](https://docs.claude.com/en/docs/claude-code/hooks) (consult the latest version; the wire format has evolved).
2. Add a row to the table at the top of this file.
3. Add a per-hook installation section below `phi-vet-gate.sh`'s.
4. Pair the hook with a complementary skill in `../commands/` where appropriate — hooks enforce, skills execute. Don't duplicate logic across the two; the skill's work is the workflow, the hook's work is the gate.
