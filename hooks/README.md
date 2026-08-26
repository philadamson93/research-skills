# hooks/

Claude Code **hooks** that compose with the slash-command skills in `../commands/`. Unlike skills (which Claude *chooses* to invoke based on intent), hooks fire at fixed lifecycle events the harness recognises — `SessionStart`, `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`. They run as shell commands and can either **inject context** into Claude's view or **block** a tool call entirely.

## What lives here

| Hook | Lifecycle | Purpose |
|---|---|---|
| [`phi-vet-gate.sh`](phi-vet-gate.sh) | `PreToolUse` (Bash) | Hard-gates `git commit` in medical-data research repos until [`/phi-vet`](../commands/phi-vet.md) has signed off on the current staged tree. Forces both a PHI scan **and** explicit per-doc read-acknowledgement **from the human user** (Claude having read the file during the scan does NOT count — the user's own eyes on every staged doc are the load-bearing check) before any commit lands. Self-gates by machine via [`lib/is-phi-free-machine.sh`](#machine-gate--fail-closed-phi-free-allowlist) — inert on PHI-free machines. |
| [`mnt-delete-gate.sh`](mnt-delete-gate.sh) | `PreToolUse` (Bash) | Asks for **human approval** before any Bash command deletes / overwrites / moves data under `/mnt` (the shared bucket mount — irreplaceable results/data): `rm`/`rmdir`/`unlink`/`shred`/`truncate`, `mv`, `dd of=`, `rsync --delete`, `find -delete`, and truncating redirects (`> /mnt/…`). Keyed on `/mnt` **only** by design; recursive `rm` elsewhere is not gated. Returns `permissionDecision:"ask"`. |
| [`provision-gate.sh`](provision-gate.sh) | `PreToolUse` (Bash) | Asks for **human approval** before expensive / irreversible cloud provisioning — `gcloud compute instances create/start`, `disks create/resize`, bucket create, `terraform apply/destroy`. Tolerates normal flag placement (`gcloud beta …`, `gcloud --project p …`, `gsutil -m mb`, `terraform -chdir=… apply`). Motivated by a real post-auto-compact incident (a VM + 1.5TB disk created with no approval). Returns `permissionDecision:"ask"`. |
| [`post-compact-reinject.sh`](post-compact-reinject.sh) | `SessionStart` (`compact`) | Re-injects the `claude_ops` **non-negotiables** (plan-before-code, ask-before-destructive, PHI discipline, executor lane) into a fresh context after a compact, since the docs don't guarantee `CLAUDE.md` survives one. Fires on the `compact` start reason (which covers **both** an automatic compact and a manual `/compact`). |
| [`precompact-wrapup-nudge.sh`](precompact-wrapup-nudge.sh) | `PreCompact` (`auto`) | *Best-effort* nudge toward `/wrapup` just before an automatic compaction (reads the documented `.trigger` field). Never blocks (blocking a full context risks an overflow wall). Drop it if your version doesn't surface its message — the load-bearing piece is `post-compact-reinject.sh`. |
| [`lib/shell-scan.sh`](lib/shell-scan.sh) | *(sourced)* | Shared helpers for the two Bash gates: `strip_heredoc_bodies` (removes heredoc bodies but preserves post-terminator commands) and `emit_ask` (fail-closed "ask" JSON). Not a hook itself. |
| [`tests/gate_tests.sh`](tests/gate_tests.sh) | *(test)* | Table-driven regression suite for all four hooks (`bash hooks/tests/gate_tests.sh`). Part of the landing gate. |

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

If you already have a `PreToolUse` block, append this hook entry to the array of matchers (you can have many). Matching hooks may run **in parallel**, and the effective decision follows Claude Code's precedence (`deny` > `ask` > `allow`) — not textual order — so each hook must be self-contained and order-independent.

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

## Guardrail gates — `mnt-delete-gate.sh`, `provision-gate.sh` (ask-before-danger)

These two `PreToolUse`→Bash hooks turn the *advisory* `claude_ops` rules "ask before
deleting /mnt data" and "ask before provisioning expensive infra" into *enforced*
human-approval prompts. They exist because advisory rules live **in context**, and an
auto-compact can drop them — a real session lost `claude_ops` after a compact and then
started a VM + created a 1.5TB disk with no approval. A hook fires regardless of what the
model has (or hasn't) read.

**Mechanism.** On a match, each hook returns, on stdout with exit 0:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"…why…"}}
```

`permissionDecision:"ask"` makes the harness prompt the **human** (Y/N) — the human decides
in the moment. This is deliberately different from `phi-vet-gate.sh`'s legacy
`{"decision":"block"}` form (which instructs *Claude*). Verified honored on Claude Code
**2.1.246**. **Fallback:** if a future/older version doesn't honor `"ask"`, switch the
scripts to `"deny"` (still stops the call; the human re-issues after approving) or the
legacy `{"decision":"block"}` — see the live sanity check below to confirm which your
version honors.

**Active everywhere — no machine gate.** Unlike `phi-vet-gate.sh`, these are about
destructive/expensive ops, not PHI, so there's no PHI-free allowlist short-circuit.

**Fail-closed.** Both gates require `jq` on `$PATH`. If `jq` is missing, or the hook event
can't be parsed, the gate emits `"ask"` (via `emit_ask` in [`lib/shell-scan.sh`](lib/shell-scan.sh))
rather than silently allowing — a guardrail that fails open is worse than a spurious prompt.

**Heredoc handling.** Before matching, both gates strip heredoc **bodies** (data fed to
another program, e.g. a review prompt piped to `codex exec`, must not trip a gate by merely
*mentioning* `/mnt` / `terraform apply`) while **preserving** the opener line and any command
after the terminator (so `cat <<EOF … EOF; rm -rf /mnt/x` still asks). See
`strip_heredoc_bodies` in [`lib/shell-scan.sh`](lib/shell-scan.sh).

### Wire-up (`~/.claude/settings.json`)

Append the two gates to the existing `PreToolUse` → `Bash` matcher block, alongside
`phi-vet-gate.sh`. Each is silent on non-matches and self-contained; matching hooks may run
in parallel and the harness resolves them by precedence (`deny` > `ask` > `allow`), so their
relative order does not matter:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {"type": "command", "command": "/ABS/PATH/research-skills/hooks/phi-vet-gate.sh"},
          {"type": "command", "command": "/ABS/PATH/research-skills/hooks/mnt-delete-gate.sh"},
          {"type": "command", "command": "/ABS/PATH/research-skills/hooks/provision-gate.sh"}
        ]
      }
    ]
  }
}
```

Use an **absolute** path (`~` is not expanded in hook command paths). This wiring is
machine-local and **not committed** — replicate it on each machine (e.g. the Mac
counterpart per the parallel-`CLAUDE.md` convention).

### Offline tests (no real deletes / no cloud calls)

The canonical, table-driven suite covers real-destructive → ask, benign → silent, the
false-negative bypasses Codex flagged (heredoc-then-command, `gcloud beta`, help-decoy),
the accepted conservative nags, fail-closed on malformed input, and the lifecycle hooks.
Run it as a file (never paste the payloads onto a command line, or the **live** gates trip):

```bash
bash ~/code/research-skills/hooks/tests/gate_tests.sh   # exit 0 iff all pass
```

Ad-hoc single checks (JSON on stdin; `"ask"` JSON on stdout, or silent):

```bash
MNT=~/code/research-skills/hooks/mnt-delete-gate.sh
PROV=~/code/research-skills/hooks/provision-gate.sh

echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /mnt/su-vista/x"}}' | "$MNT"          # ASK
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf ~/code/scratch"}}' | "$MNT"           # silent (/mnt-only)
echo '{"tool_name":"Bash","tool_input":{"command":"gcloud beta compute instances create v"}}' | "$PROV"  # ASK
echo '{"tool_name":"Bash","tool_input":{"command":"gcloud compute disks create --help"}}' | "$PROV"      # silent (scoped)
```

### Live sanity check (confirms your version honors `"ask"`)

In a **fresh** session (settings/hooks load at session start), ask Claude to run this
deliberately-harmless probe — a `/mnt` path that does not exist, deleted with `rm -f` (which
is a silent no-op on a missing path), chosen only to trip the gate without risking any data:

```
rm -f /mnt/__nonexistent_gate_probe__
```

You should see an approval prompt citing the `/mnt delete gate` reason. Because the path
doesn't exist and `-f` no-ops, approving or denying is equally safe. If **no** prompt appears
and the command just runs, your version isn't honoring `permissionDecision:"ask"` from this
hook — switch the scripts to the `"deny"` / legacy `block` fallback above. (This mechanism was
confirmed working on 2.1.246 — the gate fired live during development.)

### Known limits (important — this is a guardrail, not a sandbox)

Detection is **whole-string co-occurrence** on the heredoc-body-stripped command — the gate
checks that a destructive/provisioning token and its target/operation both appear. It is
**not** a shell parser: it does not bind a verb to its exact argument, does not split on
`&&` / `;` / `|`, and does not resolve indirection. The limits below separate what is
**inherently** unresolvable by string matching from the **conservative nags** we accept.

**Inherent (cannot be fixed without a real shell parser / runtime) — the true backstop is
OS/IAM least-privilege on the mount:**

1. **Indirection is invisible.** `eval`, `$(…)`, backticks, shell variables, `xargs` with a
   dynamically-supplied path, and symlinks are **not** expanded. `rm -rf "$MNT_TARGET"` (where
   the var resolves under `/mnt`) will not fire. A determined or obfuscated delete can slip
   past. The real backstop is **least-privilege on the mount** (a service account without
   object-delete, or a read-only mount) — outside Claude Code, and the right follow-up if
   accidental-deletion protection isn't enough.
2. **`.cwd` is not consulted.** A relative `rm -rf results` issued while the tool's cwd is
   under `/mnt` has no literal `/mnt` token and will not fire.

**Deliberate scope choices:**

3. **`/mnt`-only deletion scope:** recursive `rm` of code dirs, worktrees, or scratch is
   **not** gated — keeps routine cleanup quiet.
4. **Provision verb set:** only Compute-Engine instances/disks, buckets, and terraform
   apply/destroy are gated (the incident class). Other cost-creating resources (GKE clusters,
   Cloud SQL, managed instance groups, …) are **not** gated — add them to `provision-gate.sh`
   if needed.
5. **Bucket-URL deletes** (`gsutil rm gs://…` that never touch the `/mnt` mount) are out of
   scope — the deletion gate keys on `/mnt`.

**Accepted conservative nags (safe-direction false positives — we ask when unsure):**

6. **Cross-subcommand / quoted / commented mentions** may prompt: `rm -rf /tmp/x && ls /mnt`
   asks (both tokens co-occur), and an executed-looking `# terraform apply` comment asks.
   Without a shell parse we cannot tell a mention from an execution, so we err toward asking.
7. **`mv` into `/mnt`** (adding data, harmless) also prompts — the gate can't cheaply tell
   move-in from move-out, and asks on either.

**Other:**

8. **Bypass mode.** `--dangerously-skip-permissions` / `bypassPermissions` may skip scoped
   hooks. A future `permissions.disableBypassPermissionsMode: "disable"` would close that.

---

## Post-compact re-injection — `post-compact-reinject.sh` (+ `precompact-wrapup-nudge.sh`)

The Claude Code docs do **not** guarantee `CLAUDE.md` / project instructions survive (or are
re-injected after) an auto-compact. `post-compact-reinject.sh` is a `SessionStart` hook that
re-states the `claude_ops` non-negotiables into the fresh context whenever a session resumes
from a **compact** (it self-filters on the start reason; a normal startup already loads
`CLAUDE.md`, so it stays silent there). It's a *pointer*, not a copy of `claude_ops`.

`precompact-wrapup-nudge.sh` is an optional `PreCompact` (`auto`) hook that emits a
"consider `/wrapup`" message before an automatic compaction. It never blocks. It's
best-effort — if your version doesn't surface its message, drop it; the re-inject is the
load-bearing piece.

### Wire-up (`~/.claude/settings.json`)

Neither needs a `matcher` — the scripts filter on the start/trigger reason themselves:

```json
{
  "hooks": {
    "SessionStart": [
      {"hooks": [{"type": "command", "command": "/ABS/PATH/research-skills/hooks/post-compact-reinject.sh"}]}
    ],
    "PreCompact": [
      {"hooks": [{"type": "command", "command": "/ABS/PATH/research-skills/hooks/precompact-wrapup-nudge.sh"}]}
    ]
  }
}
```

### Tests

Covered by the suite (`bash hooks/tests/gate_tests.sh`); the payloads use the **documented**
lifecycle fields — `SessionStart` carries `.source` (value `compact`), `PreCompact` carries
`.trigger` (`auto` / `manual`):

```bash
REINJ=~/code/research-skills/hooks/post-compact-reinject.sh
# source=compact → prints the 4-rule re-anchor; startup → silent
echo '{"source":"compact"}' | "$REINJ"
echo '{"source":"startup"}' | "$REINJ"; echo "exit=$?"

NUDGE=~/code/research-skills/hooks/precompact-wrapup-nudge.sh
echo '{"trigger":"auto"}'   | "$NUDGE"   # emits systemMessage JSON
echo '{"trigger":"manual"}' | "$NUDGE"; echo "exit=$?"
```

Note `SessionStart` `source:compact` fires after **both** an automatic compact and a manual
`/compact` — the value doesn't distinguish them, so the re-anchor also shows after `/compact`
(harmless: re-stating the non-negotiables is never wrong).

**Live check (largely confirmed):** the re-anchor text was observed in a resumed context
after a real compact on 2.1.246 (plain `SessionStart` stdout is the injection channel). If a
future version needs `hookSpecificOutput.additionalContext` instead, switch the script's final
block to that shape. `precompact-wrapup-nudge.sh` remains best-effort — if its message doesn't
surface on your version, drop it; the re-inject is the load-bearing piece.

---

## Machine gate — fail-closed PHI-FREE allowlist

PHI-free is a narrow, explicit exemption — a machine with no data mount and no BigQuery credentials at all — not the default state of a VISTA/rad-eval planner Mac. Claude Code for Education covers Phil's Mac and his project VMs alike, so code execution and data access are allowed on both, gated by the same `phi-vet` discipline. The gate below stays *fail-closed*: active everywhere except the specific machines listed on the allowlist. The hook consults [`lib/is-phi-free-machine.sh`](lib/is-phi-free-machine.sh) **before anything else** and exits silently (allow) if this machine is on the PHI-FREE allowlist.

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

On a machine that genuinely has no data mount and no BigQuery credentials at all, copy the template and add this host's **stable** identifier:

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
