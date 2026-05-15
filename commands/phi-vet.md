---
description: Hard pre-commit gate scanning files for PHI (Protected Health Information) leakage in medical-data research repos — patient identifiers, DICOM UIDs, accession numbers, clinical dates, sample row data, free-text report excerpts, embedded images. ALSO surfaces every doc file in the commit and requires the user to explicitly acknowledge they have read each before sign-off. TRIGGER before committing in any repo where work touches BigQuery / OMOP / NeuralFrame / DICOM / EHR data (cues: project CLAUDE.md mentions PHI/PHI-handling; recent commits reference task tables, image_occurrence, person_id, NeuralFrame, OMOP releases; presence of BQ credential usage; an explicit memory note about PHI safeguards). ALSO TRIGGER when the user says "PHI vet", "PHI scan", "check for patient data", "scrub for PHI", or "vet this commit". When a companion PreToolUse hook (`hooks/phi-vet-gate.sh`) is installed, that hook will BLOCK `git commit` in medical-data repos until this skill has written a sign-off marker for the current staged tree — this skill is the only path through the gate. The commit-review skill ESCALATES to this skill when working in a medical-data repo. SKIP only if the user explicitly says "skip the PHI check" — never skip silently; if skipped, still write the marker (with the rationale appended) so the user's override is auditable.
---

You are running the **`/phi-vet`** command. Hard pre-commit gate that catches PHI (patient/encounter/study identifiers, sample row data, free-text excerpts, image files) in files about to be committed from a medical-data research repo.

This skill exists because PHI leakage from BigQuery output, materialized DataFrame previews, or hand-pasted query results is the single most consequential commit mistake in this class of work. It is a serious data governance violation. Do not commit on a "probably fine."

---

## Step 1 — Identify files to review

If the user passed a path or glob as an argument, use that.

Otherwise, get what's about to be committed:
```bash
git diff --cached --name-only
```

If nothing is staged, fall back to recently modified + untracked:
```bash
git status --short
```

Also include:
- Untracked files in the working tree that look like commit candidates (`.md`, `.csv`, `.tsv`, `.json`, `.html`, `.png`, `.jpg`, `.parquet`, `.pkl`).
- Files modified in the last commit if it has not been pushed (`git log --name-only origin/HEAD..HEAD` or equivalent), in case the user wants to retroactively vet.

Show the user the list of files you'll review and confirm. If the list is short and obvious (≤3 files, all `.md`), you can proceed without confirming. If it's larger, ambiguous, or includes unexpected file types, surface it via `AskUserQuestion` before proceeding.

---

## Step 2 — Threat catalog (what to look for)

**Read every in-scope file in full with the Read tool before evaluating.** Pattern-grep alone is not sufficient — several PHI categories below (narrative re-identification where placeholder + unique clinical features re-identify, sample-row composition across multiple OMOP columns, sentence-length free-text dictation excerpts, indirect cancer-pair / treatment-interval narratives) won't surface through regex. Use grep as a supplementary check *after* the Read pass, never as a substitute for it. This applies to every file regardless of size — tiny CLAUDE.md tweaks and 50-line bash scripts included.

For each file, evaluate against the following PHI categories. **In medical-data repos (OMOP/NeuralFrame/EHR/DICOM context), the priors are HIGH** — assume any concrete data value is suspect until proven safe.

### PHI categories — flag if present

1. **Direct patient identifiers** — names, MRNs, dates of birth, phone numbers, addresses, SSNs, email, any free-text that looks like demographic detail tied to one person.
2. **`person_id` values** — in OMOP cohorts, typically 8–10-digit integers (synthetic example shape: `1XXXXXXXX`). Aggregate counts of person_ids are FINE; literal values are PHI.
3. **DICOM identifiers** — `image_study_uid` / `image_series_uid` / `study_instance_uid` / `series_instance_uid`. Recognizable by dot-separated numeric strings starting with `1.2.840.*` or similar OID format, typically 30–60 chars. Per data governance, these are PHI.
4. **Accession numbers** — `ct_accession_number`, `path_accession_number`, etc. Often 16-character hex strings (synthetic example shape: 16 chars matching `[0-9A-F]{16}`) or institution-specific encodings. Treat as PHI.
5. **Encounter / visit identifiers** — `visit_occurrence_id`, `note_id`, `image_occurrence_id`, `condition_occurrence_id`, anything ending in `_id` that's a row-level FK from OMOP/NeuralFrame.
6. **Specific clinical dates tied to a person** — admission dates, scan dates, treatment dates, diagnosis dates, dates of death. Workflow timestamps (today's date, commit dates, OMOP release labels like `feb2026` / `aug2025`) are FINE. The test: does the date appear next to or in a row with anything patient-specific?
7. **Sample row data** — even when individual columns aren't obviously PHI, a few rows with multiple OMOP columns can re-identify. Always flag a sample table that includes `(person_id, date, …)` or `(image_study_uid, image_series_uid, …)`. Quote the exact rows in the FLAGGED report.
8. **Free-text excerpts** — any snippet of `_series_description`, `_study_description`, `ct_note_text`, `path_note_text`, radiology/pathology report content longer than ~50 chars OR containing phrases that look like dictation. Generic protocol/kernel labels (e.g., `1.25MM CHEST`, `B45f`, `THORAX 1.0`) and study type strings (e.g., `CT Chest Abdomen and Pelvis with Contrast`) are vendor/protocol-level — FINE.
9. **Image files** — PNG/JPEG/PDF that could be screenshots of EHR, DICOM viewers, scanned reports, or rendered radiology images. Flag any image file whose source isn't obviously aggregate (e.g., a matplotlib bar chart of finding-frequencies is fine; a DICOM screenshot is not).
10. **Small cell counts with quasi-identifiers** — n < 5 with two or more quasi-identifiers (age + diagnosis + date, ZIP + procedure + sex). The HIPAA Safe Harbor de-identification standard takes this seriously.
11. **Credentials / API keys** — service account JSON, BQ credentials, OAuth tokens, OpenAI/Anthropic keys. Always flag.

### Safe by design — do NOT flag

- **Aggregate counts and percentages** (e.g., `374,000 rows`, `79% newly admitted`, `0/241 rows fired`).
- **Schema descriptions** — column names, SQL projections, regex patterns, `BASE_TEMPLATE_VARS` content.
- **SQL templates without literal patient values** — `WHERE person_id = ?` placeholders are fine; `WHERE person_id = <literal>` is not.
- **Vendor/protocol-level free-text** — Siemens reconstruction kernels (`B45f`, `I70f`, `B31s`), study protocol names (`CT Chest Abdomen and Pelvis with Contrast`), DICOM modality codes (`CT`, `MR`, `PT`), OMOP vocabulary values (`CHEST`, `ABDOMEN`, `CHEST ABDOMEN PE`).
- **Workflow / config metadata** — commit SHAs, branch names, OMOP release labels, dataset names (`vista_bench_v1_3`, `som-nero-plevriti-deidbdf`), file paths, vista-ct version pins, today's date.
- **Code, regex, configuration files**, plot images of aggregate distributions.

### When in doubt → FLAG

A false flag costs the user 30 seconds; a missed PHI commit can be a multi-month cleanup involving institutional data governance.

---

## Step 3 — Optional sub-agent escalation for ambiguity

If the file is large (>500 lines), or contains many sample tables / heterogeneous content where a careful reading would benefit from fresh context, spawn a `general-purpose` sub-agent to do the audit. Pass it:

- The full file path
- The threat catalog above (as the audit checklist)
- Explicit "do not run code, read-only" instruction
- Required output format: per-line VERDICT (SAFE / FLAGGED / BORDERLINE) with file:line and exact-quoted content for any flag, plus a summary recommendation

Sub-agent escalation is OPTIONAL; for short obvious files (a 50-line bash script, a CLAUDE.md tweak), inline Read+evaluate by the running Claude is fine. **What is never fine: skipping the Read pass and relying on regex/grep alone** — even tiny files get a full Read per Step 2, since the threat catalog includes narrative re-id risks that grep won't catch.

---

## Step 4 — Report

Per file:

```
[SAFE / FLAGGED / BORDERLINE] path/to/file.ext
Reason: <one sentence>
[For FLAGGED] Exact content: file:line: <quoted excerpt>
[For FLAGGED] Suggested disposition: redact / replace with aggregate / exclude file from commit / keep (user override)
```

If any file is **FLAGGED**:
- DO NOT commit.
- Show the exact flagged content per file (file:line + quote).
- Surface a multi-choice via `AskUserQuestion` per the global "Multi-choice → AskUserQuestion" preference: options like **Redact** / **Replace with aggregate** / **Exclude file from commit** / **Keep (override — log reason)**. Apply the user's chosen disposition before re-running the vet.

If any file is **BORDERLINE**:
- Show the borderline content and the specific concern.
- Surface a yes/no via `AskUserQuestion` ("Treat as SAFE" / "Escalate to FLAGGED").

If all files are **SAFE**:
- Print: `All files passed PHI scan (N files reviewed).`
- Proceed to Step 5 (doc-read sign-off + marker) before declaring the commit safe.

---

## Step 5 — Doc-read sign-off + sign-off marker

This step is what turns a passing PHI scan into a *committable* state. Two parts:

### 5a. Doc-read sign-off

PHI scan catches data leakage; it does not catch editorialization, private working-group content, or prose the user wouldn't want committed unread. So before declaring SAFE-to-commit, enumerate every doc file in the staged tree and require the user to explicitly acknowledge they've read each one.

Doc files = anything in: `*.md`, `*.markdown`, `*.rst`, `*.txt`, `*.html`. Get the list:

```bash
git diff --cached --name-only -- '*.md' '*.markdown' '*.rst' '*.txt' '*.html'
```

If the list is empty, skip to 5b.

Otherwise, surface ALL doc paths via `AskUserQuestion` — per the global "Multi-choice → AskUserQuestion" preference. Batch up to 4 questions per call (the tool's max), one question per doc. Phrasing per question:

> *"Have you personally read `path/to/doc.md` and confirm it's appropriate to commit?"*
> Options: **Yes, I read it** / **No, open it for me first** / **Skip — I trust the change** (escape hatch with rationale logged)

If the user picks **No, open it for me first**, hand off to `/read-plan` for that path, then re-ask the question. If they pick **Skip — I trust the change**, log the file + rationale in the conversation, treat as ack.

Multiple docs → multiple AskUserQuestion rounds. Don't compress into one "have you read all of these?" question — the per-file surface is the value.

### 5b. Write the sign-off marker

Once Step 4 is SAFE and Step 5a is complete (every doc acknowledged or explicitly skipped-with-rationale), write the marker that the `phi-vet-gate.sh` hook checks for:

```bash
git_root="$(git rev-parse --show-toplevel)"
tree_sha="$(git -C "$git_root" write-tree)"
mkdir -p "$git_root/.git/phi-vet"
{
  echo "Signed off: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Tree:       $tree_sha"
  echo "Reviewer:   $(git -C "$git_root" config user.name || whoami)"
  echo "Skill:      /phi-vet"
  echo "PHI scan:   PASS (N files)"
  echo "Doc-read:   K docs acknowledged ($M skipped-with-rationale)"
  # If user invoked the skip path ("skip the PHI check") for the whole vet,
  # append the rationale line here instead of the above PASS lines.
} > "$git_root/.git/phi-vet/${tree_sha}.signed-off"
```

The marker is keyed on the staged tree's SHA. If the user adds, removes, or modifies a staged file after this marker is written, `git write-tree` produces a different SHA and the hook will require re-vetting. This is intentional.

Then print:

```
✓ Signed off PHI vet for staged tree <short-sha>. Commit gate cleared.
```

Hand off to the calling skill (commit-review) or to the user.

---

## Notes

- This skill is the depth-pass for the PHI sweep that `commit-review` does inline. `commit-review` should ESCALATE to `/phi-vet` whenever it detects medical-data context — don't duplicate the catalog there; just call this.
- If you find a memory note about PHI safeguards in the project's auto-memory (e.g., `feedback_phi_commit_safeguard.md` or similar), the user has flagged this repo as high-PHI-risk. Treat the threshold for FLAGGING as more conservative.
- For sample tables that contain mostly NULL fields (e.g., showing that v1_3 had no CT for these persons), the NULLs themselves aren't PHI — but the surrounding row context (e.g., the person_id column even with a NULL date) still might be. Apply the row-data rule (#7) regardless of NULL density.
- Override discipline: when the user chooses "Keep (override)", note their reason in the conversation log so it's traceable. The override is theirs to make; the skill's job is to surface the concern, not to relitigate.
