Reference: claude_ops.md

# Feedback: Guardrail hooks: ask-before-danger + post-compact re-injection (Codex review)

## Verdict

Blocked. The hook protocol and machine-local wiring are basically sound, but both safety gates have realistic false-silent paths, including ordinary heredoc chaining and common supported CLI flag forms. The implementation and README also overstate protection relative to the actual whole-string matching behavior.

## Critical Gaps

- Critical | The heredoc “fix” discards executable shell after the first `<<` in both safety gates | A normal multiline Bash call such as `cat <<EOF ... EOF; rm -rf /mnt/x` or `cat <<EOF ... EOF; terraform apply` runs the trailing command but produces no prompt. Here-strings (`<<<`) and arithmetic shifts (`<<`) create the same blind spot. This is a deterministic false negative, not merely deliberate obfuscation; risk is **High** because Claude commonly emits multiline compound Bash. | Evidence: `hooks/mnt-delete-gate.sh:39`, `hooks/mnt-delete-gate.sh:45`, `hooks/provision-gate.sh:33`, `hooks/provision-gate.sh:36` | Required fix: remove the all-tail truncation or replace it with logic that removes only actual heredoc body ranges while preserving commands after each terminator; regression-test trailing commands and `<<<`.
- Critical | `provision-gate.sh` globally exempts any command string containing `--help` or `--dry-run` | `printf -- --help && terraform apply` and `echo --dry-run && gcloud compute instances start vm` both tested SILENT. A benign sibling subcommand can therefore suppress a real provision operation. | Evidence: `hooks/provision-gate.sh:38`, `hooks/provision-gate.sh:39` | Required fix: apply the exemption only to the same parsed provisioning subcommand, and only when that subcommand is genuinely help/dry-run; never return early based on a flag elsewhere in the tool call.
- High | Common, non-obfuscated forms of the planned provisioning commands are not recognized | Tested SILENT: `gcloud --project p compute instances create vm`, `gcloud beta compute instances create vm`, `gsutil -m mb gs://new-bucket`, and `terraform -chdir=infra apply`. These are normal supported invocations of the exact resource operations the plan says are gated. | Evidence: `docs/plans/guardrail-hooks-ask-before-danger.md:80`, `docs/plans/guardrail-hooks-ask-before-danger.md:86`, `hooks/provision-gate.sh:46`, `hooks/provision-gate.sh:59` | Required fix: define the supported grammar, account for relevant gcloud tracks/global flags, gsutil global options, and Terraform global options before the verb, then add each form to the landing gate.
- High | The `/mnt` gate does not associate a destructive verb with its target and does not implement or honestly list several planned destructive forms | The script merely requires `/mnt` somewhere and a destructive word somewhere. It tested ASK for `rm -rf /tmp/x && ls /mnt`, but SILENT for `rmdir /mnt/empty`, `mv /mnt/x /tmp/x`, and `: > /mnt/x`. The README nevertheless says it gates deletion/overwrite generally, while the plan requires `mv`/redirection to be implemented or disclosed as gaps. | Evidence: `docs/plans/guardrail-hooks-ask-before-danger.md:63`, `docs/plans/guardrail-hooks-ask-before-danger.md:70`, `hooks/mnt-delete-gate.sh:47`, `hooks/mnt-delete-gate.sh:60`, `hooks/README.md:10` | Required fix: bind path/destination analysis to each destructive subcommand; either cover move-out, redirection/overwrite, `rmdir`, and relative targets under a `/mnt` cwd, or narrow every claim and enumerate each omission.
- High | Known-limits text inaccurately says compound commands are matched per subcommand | Neither implementation splits or parses subcommands; both scan the whole pre-heredoc prefix. This causes cross-subcommand false positives and makes the broad help exemption a cross-subcommand false negative. Ordinary flag placement and heredoc chaining are also incorrectly collapsed into the “determined/obfuscated” caveat. | Evidence: `docs/plans/guardrail-hooks-ask-before-danger.md:204`, `docs/plans/guardrail-hooks-ask-before-danger.md:206`, `hooks/README.md:183`, `hooks/README.md:186` | Required fix: either implement per-subcommand analysis or state explicitly that matching is whole-string co-occurrence, with the resulting false-positive and false-negative classes.
- Medium | The optional PreCompact hook does not match the documented input and uses output the event discards | Claude Code documents PreCompact input as `.trigger` (`auto`/`manual`), but the script reads `.trigger_reason // .reason // .source`; a real `{ "trigger": "auto" }` is silent. Current hook documentation also says PreCompact discards `systemMessage`, so the kept implementation failed the plan’s own Step-0/drop-if-not-visible gate. | Evidence: `docs/plans/guardrail-hooks-ask-before-danger.md:114`, `docs/plans/guardrail-hooks-ask-before-danger.md:118`, `hooks/precompact-wrapup-nudge.sh:26`, `hooks/precompact-wrapup-nudge.sh:35`, `hooks/README.md:239` | Required fix: remove this optional hook until a supported visible channel is demonstrated, or use `.trigger` and document a verified output behavior for Claude Code 2.1.246.
- Medium | The scripts claim “exit 0 always,” but parse/dependency failures are fail-open hook errors | With `set -e`, malformed stdin or missing/failing `jq` exits nonzero before a decision is emitted. Claude Code reserves exit 2 for blocking; other nonzero command-hook exits are errors and the action proceeds. That contradicts the stated contract on an everywhere-active safety control. | Evidence: `hooks/mnt-delete-gate.sh:14`, `hooks/mnt-delete-gate.sh:27`, `hooks/mnt-delete-gate.sh:33`, `hooks/provision-gate.sh:17`, `hooks/provision-gate.sh:21`, `hooks/provision-gate.sh:27` | Required fix: make the dependency explicit for all guardrails and choose/document fail-closed behavior for parse failures (normally stderr + exit 2), with malformed/missing-field tests.

## Failure Modes

- Real command after a heredoc | `${cmd%%<<*}` keeps only text before the heredoc operator, although the shell resumes parsing after the terminator | Add `cat <<EOF ... EOF\nrm -rf /mnt/x` and the analogous `terraform apply` case; both must ask.
- Real command after a here-string | `<<<` contains `<<`, so `read x <<< y && rm -rf /mnt/x` tested SILENT | Add here-string and arithmetic-shift cases; neither may hide a later destructive command.
- Provision command plus unrelated help text | The global early exit runs before provisioning matching | Add `echo --help && terraform apply`, `gcloud ... start vm && echo --help`, and mixed multiline variants; dangerous siblings must ask.
- gcloud global flags or release tracks | Exact contiguous phrase matching requires `gcloud compute...` | Add `gcloud --project=p compute instances create`, `gcloud --quiet compute disks resize`, and `gcloud beta compute instances start/create` according to the intended supported scope.
- gsutil global options | Exact phrase matching requires adjacent `gsutil mb` | Add `gsutil -m mb` and `gsutil -o ... mb`.
- Terraform global options | Exact phrase matching requires adjacent `terraform apply|destroy` | Add `terraform -chdir=infra apply` and `terraform -chdir infra destroy` if that latter syntax/version is supported.
- Relative deletion while the hook cwd is under `/mnt` | The implementation ignores event `.cwd` and requires literal `/mnt` in the command | Add payload `cwd:/mnt/project` with `rm -rf results`; resolve relative targets conservatively or state this as an explicit false-negative limit.
- Indirect target from environment or command substitution | Literal-string matching cannot know that `rm -rf "$MOUNT_TARGET"` or `rm -rf "$(resolve_target)"` resolves under `/mnt` | Keep this limitation explicit and distinguish it from the fixable syntax gaps; OS/IAM/read-only mount remains the true boundary.
- `xargs rm` with a dynamically supplied path | A literal `/mnt` elsewhere happens to trigger today, but `printf ... "$MOUNT_TARGET" | xargs rm` is silent | Add a documented limitation or a conservative xargs policy; do not claim argument-level path analysis.
- Cross-subcommand false positive | `/mnt` and `rm` need not belong to the same command (`rm /tmp/x && ls /mnt` tested ASK) | Parse shell command units or clearly accept/document this nag rate.
- Benign quoted/commented provision phrase | Phrase matching is not command-position matching (`printf '%s\n' 'terraform apply'` and `echo ok # terraform apply` tested ASK) | Add quote/comment cases and implement actual command-position matching; the current plan explicitly promises it.
- Move, empty-directory removal, or shell overwrite | `mv`, `rmdir`, and redirection are absent despite the broader delete/overwrite wording | Decide exact protection scope, cover it, and test `mv /mnt/x /tmp`, `rmdir /mnt/x`, `> /mnt/x`, `tee`, and `dd` source-vs-destination direction.
- Malformed event or absent `jq` | `set -e` exits without an ask/deny decision | Add dependency and malformed-input tests with an explicit fail-closed expected result.

## Contract Checks

The modern PreToolUse output is correct for Claude Code 2.1.246: exit 0 plus `hookSpecificOutput.hookEventName:"PreToolUse"`, `permissionDecision:"ask"`, and a reason. `ask` is the right semantic choice for the user’s ask-before-danger requirement; `deny` would change the workflow from approval-in-place to cancellation/reissue. It also correctly differs from `phi-vet-gate.sh`’s deprecated-but-supported top-level block response (`hooks/phi-vet-gate.sh:10`, `hooks/phi-vet-gate.sh:123`). The official [Claude Code hooks reference](https://code.claude.com/docs/en/hooks) confirms `allow|deny|ask|defer`, deny-first precedence across multiple hooks, plain SessionStart stdout context injection, and `SessionStart.source == "compact"` after either auto or manual compaction.

`post-compact-reinject.sh` reads the right authoritative field first: `.source`, with harmless compatibility fallbacks (`hooks/post-compact-reinject.sh:15`, `hooks/post-compact-reinject.sh:26`). Its plain stdout on source `compact` is a valid SessionStart injection channel in 2.1.246. The plan’s wording should say this also fires after manual `/compact`, because the source value does not distinguish manual from automatic compaction.

The settings shape in the plan/README is valid: event arrays containing matcher groups and command-hook arrays. The actual user settings on this VM contain all four absolute paths under the intended `PreToolUse`, `SessionStart`, and `PreCompact` events, and no settings JSON is tracked in this repository. One documentation correction is needed: matching hooks may run in parallel; do not promise they “fire in order” (`docs/plans/guardrail-hooks-ask-before-danger.md:92`, `hooks/README.md:125`). Decision precedence, not textual ordering, is the relevant contract.

## Modularity vs. YAGNI

Two ask-gate scripts are justified: their domains, reasons, test matrices, and operational toggles are distinct, and each remains small. Combining them would not solve the core parsing problem. A small shared shell-command scanner could become justified only if it is the tested mechanism that fixes subcommand/heredoc parsing for both; otherwise it would add abstraction without safety.

The optional PreCompact nudge is currently overbuilt relative to its verified value: it reads the wrong field and emits a discarded field. Per the plan’s own YAGNI gate, drop it unless a 2.1.246 live check proves a supported visible output. The post-compact re-anchor is independently useful and appropriately compact.

## Verification Gaps

- The plan’s offline matrix covers only happy-path literal commands. It omits every false-negative and false-positive case listed above.
- There is no committed automated regression harness; the README contains only manual `echo` probes. Safety-critical regex changes need table-driven fixtures asserting tool name, command, cwd, stdout decision, reason, and exit status.
- Tests should cover compound separators (`&&`, `||`, `;`, pipes, newline), quotes/comments, multiline heredocs with trailing commands, `<<<`, multiple heredocs, and benign heredoc bodies.
- `/mnt` tests should distinguish source from destination for `dd`, rsync, move, copy/overwrite, shell redirection, and commands run with `.cwd` below `/mnt`.
- Provision tests should cover global flags/tracks, option ordering, `terraform -chdir`, gsutil options, multiple dangerous siblings, and help on the same versus another subcommand.
- Add malformed JSON, missing `tool_name`, missing command, null fields, and missing-`jq`/hook-error expectations so the declared exit contract is verified.
- Feed the documented real lifecycle payloads: `{"source":"compact"}` for SessionStart and `{"trigger":"auto"}` for PreCompact. The current README’s fabricated `trigger_reason` test masks the PreCompact bug (`hooks/README.md:232`, `hooks/README.md:239`).
- Record evidence for Step 0 and the live Step 2 prompt checks. README says `ask` was verified, but the branch contains no durable result demonstrating those landing gates ran.

## Handoff Readiness

The branch is correctly named `feat/dangerous-ops-and-compact-hooks` and exists at the current checkout. The single-branch `/land` sequence, branch/worktree pruning, Completed status update, and cross-machine settings replication are clearly specified (`docs/plans/guardrail-hooks-ask-before-danger.md:191`). Machine-local wiring is correctly excluded from the committed file list, uses absolute paths, and is already present on this VM.

The landing gate is not ready. Besides the failed safety cases, its statement that `research-skills` needs no `/phi-vet` conflicts with the precedent hook’s executable heuristic: any `docs/` match for `PHI` activates the gate, and this repository has such files (`docs/plans/guardrail-hooks-ask-before-danger.md:195`, `hooks/phi-vet-gate.sh:87`). On this VM the PHI-free helper reports the gate active, so the planned commit will be gated in practice. Amend the landing gate to follow the actual `/commit-review`/`phi-vet` result rather than asserting exemption.

The commit plan also omits the approved plan document itself even though `claude_ops.md` requires an approved plan to be committed. Include the plan with the documentation milestone after sign-off. Do not mark the plan Completed or prune the branch until the revised tests and live gates pass.

## Suggested Revisions

- Replace the heredoc tail truncation design with a tested body-only removal strategy, or conservatively scan the full command until correct shell-aware handling exists.
- Define a subcommand-level detection model and use it consistently for verb/target pairing and help/dry-run scoping.
- Expand provisioning grammar to normal gcloud global flags/tracks, gsutil global options, and Terraform `-chdir`; explicitly list genuinely out-of-scope provisioners/resources.
- Decide the `/mnt` destructive surface: implement move-out, rmdir, overwrite/redirection, cwd-relative targets, and destination direction, or enumerate each as a known gap and narrow README claims.
- Rewrite Known limits to separate inherent literal-resolution limits (variables/eval/symlinks) from currently fixable parser gaps; remove the false “per-subcommand” statement.
- Change PreCompact parsing to `.trigger` and remove `systemMessage` reliance, or drop the optional hook as the plan permits.
- State a fail-closed dependency/parse-error contract and add installation checks for `jq` to the guardrail section.
- Add a table-driven offline regression suite with all scenarios in this review and make it part of the landing gate.
- Correct lifecycle wording: SessionStart `source:compact` covers manual and auto compact; hook execution ordering is not guaranteed.
- Update Landing & cleanup to include the plan doc in the documentation commit and to honor the actual phi-vet gate result.

## Questions For The Author

- Is the intended `/mnt` promise limited to file-removal verbs, or should “deletes/overwrites data” truly include move-out, truncating redirection, `tee`/copy overwrite, and relative commands issued from a `/mnt` cwd?
- Should “infra provisioning” mean only the enumerated Compute Engine/Terraform/bucket operations, or all cost-creating gcloud resources (for example clusters, SQL instances, and managed instance groups)? The README currently reads broader than the matcher set.
- Is conservative nagging acceptable for shell constructs that cannot be parsed safely, or must benign heredoc prompt bodies remain silent even if preserving that UX requires a real shell parser?

## Audit Trail

- `claude_ops.md`
- `docs/plans/guardrail-hooks-ask-before-danger.md`
- `hooks/mnt-delete-gate.sh`
- `hooks/provision-gate.sh`
- `hooks/post-compact-reinject.sh`
- `hooks/precompact-wrapup-nudge.sh`
- `hooks/README.md`
- `hooks/phi-vet-gate.sh`
- `/home/philadamson/.claude/settings.json`
