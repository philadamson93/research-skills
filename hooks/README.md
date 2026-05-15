# hooks/

Claude Code **hooks** that compose with the slash-command skills in `../commands/`. Unlike skills (which Claude *chooses* to invoke based on intent), hooks fire at fixed lifecycle events the harness recognises — `SessionStart`, `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`. They run as shell commands and can either **inject context** into Claude's view or **block** a tool call entirely.

## What lives here

| Hook | Lifecycle | Purpose |
|---|---|---|
| [`phi-vet-gate.sh`](phi-vet-gate.sh) | `PreToolUse` (Bash) | Hard-gates `git commit` in medical-data research repos until [`/phi-vet`](../commands/phi-vet.md) has signed off on the current staged tree. Forces both a PHI scan **and** explicit per-doc read-acknowledgement before any commit lands. |

---

## phi-vet-gate.sh — installation

This hook makes `/phi-vet` non-optional in medical-data repos. Without it, a coding session under context pressure can drift past the skill and commit unreviewed content; with it, the harness refuses to let `git commit` run until the skill's marker file exists.

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

Open a fresh Claude Code session in any medical-data repo (`vista-eval`, `vista-ct`, `vista_bench`, `path-extract`, …) and ask Claude to make a trivial commit. The hook should block with output like:

> PHI gate: this commit lands in a medical-data research repo (`vista-eval`), and the staged tree `5336…` has not been signed off by `/phi-vet`. Required: invoke `/phi-vet` to (a) scan the staged content … (b) surface every doc file in the commit and require the user to explicitly acknowledge they have read it, (c) on full approval, write a sign-off marker at `.git/phi-vet/5336….signed-off`. Once the marker exists, re-attempting `git commit` will pass this gate.

Claude should then invoke `/phi-vet`, run the PHI scan, walk you through per-doc read-acknowledgement, write the marker, and re-attempt the commit.

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

## What counts as a "medical-data research repo"?

The hook trips its gate when **any** of the following is true for the target repo:

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

There is no environment-variable bypass for the hook. If you genuinely need one (e.g., automated CI commit step that has its own data-governance review), open an issue rather than hacking around it; the right fix is a separate hook matcher pattern, not a back-door.

## Uninstallation

Remove the corresponding entry from your `~/.claude/settings.json`. The script remains in this repo; restoring the hook is just re-adding the JSON.

---

## Adding a new hook to this directory

1. Drop a `<name>.sh` here. Read Claude Code's PreToolUse / SessionStart / etc. JSON contract — Claude Code [documents the hook payload format](https://docs.claude.com/en/docs/claude-code/hooks) (consult the latest version; the wire format has evolved).
2. Add a row to the table at the top of this file.
3. Add a per-hook installation section below `phi-vet-gate.sh`'s.
4. Pair the hook with a complementary skill in `../commands/` where appropriate — hooks enforce, skills execute. Don't duplicate logic across the two; the skill's work is the workflow, the hook's work is the gate.
