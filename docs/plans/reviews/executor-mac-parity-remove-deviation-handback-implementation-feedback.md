Reference: claude_ops.md

# Implementation Feedback: Executor/Mac parity — retire the vm-handoff doc mechanism

## Verdict

Revise before commit. The core retirement is implemented: `claude_ops.md` now states parity, the two handoff files are deleted, `/review-plan`, `/review-implementation`, `/review-tests`, `/wrapup`, and most of `/land` were rewritten to remove the doc handoff flow, and the external VISTA CLAUDE files match Phase 2. Do not commit yet: the current operational `/land` frontmatter still says the green gate is "VM smoke", `docs/plans/README.md` still points at the deleted canonical spec as current, and the generated HTML companion for the superseded verification/handoff plan remains stale.

## Plan Coverage

| Phase | Status | Evidence: path:line | Notes |
| --- | --- | --- | --- |
| Phase 1 — `claude_ops.md` rewrite | Done | `claude_ops.md:31`, `claude_ops.md:83`, `claude_ops.md:132`, `claude_ops.md:176`, `claude_ops.md:219`, `claude_ops.md:354`, `claude_ops.md:375` | The Machine-Aware section is coherent: parity first, hardware-capacity exception second, standalone runner script + shared mount for no-Claude-Code compute. The new `## Verification` template reads standalone and no longer depends on the old `## Verification & VM handoff` template. |
| Phase 2 — `/Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.md` and `CLAUDE.vm.md` | Done | `/Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.md:11`, `/Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.md:13`, `/Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.vm.md:19`, `/Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.vm.md:56` | `CLAUDE.md` now says "GPU/high-throughput capacity routing (any Claude-Code machine otherwise has full parity)." `CLAUDE.vm.md` now says "Full parity with the Mac" and explicitly drops the "planning happens on the Mac" rule. Remaining `Executor` labels in `CLAUDE.vm.md:1`, `:11`, `:36` are hardware-capacity labels, not authority-split rules. |
| Phase 3 — delete `commands/vm-handoff.md`, delete `references/verification-and-handoff-design.md`, add superseded banner | Done | `git diff --name-status`: `D commands/vm-handoff.md`, `D references/verification-and-handoff-design.md`; `docs/plans/verification-and-handoff-design-agent.md:3`; `docs/plans/verification-and-handoff-design-agent.md:7` | Both deleted files are absent from the working tree. The local and remote branch `legacy/vm-handoff-doc-system-2026-08` exists, and `git show legacy/vm-handoff-doc-system-2026-08:commands/vm-handoff.md` plus `git show legacy/vm-handoff-doc-system-2026-08:references/verification-and-handoff-design.md` both print real pre-deletion content. |
| Phase 4 — `commands/review-plan.md` | Done | `commands/review-plan.md:3`, `commands/review-plan.md:49`, `commands/review-plan.md:82`, `commands/review-plan.md:118`, `commands/review-plan.md:142` | The description no longer lists verification/handoff-design, Phase 2c is gone, the Verification & Handoff Design output section is gone, and handoff-readiness points at the generic `Verification` section. |
| Phase 5 — `commands/review-implementation.md` and `commands/review-tests.md` | Done | `commands/review-implementation.md:3`, `commands/review-implementation.md:187`, `commands/review-implementation.md:195`, `commands/review-tests.md:3`, `commands/review-tests.md:233`, `commands/review-tests.md:241` | The YAML `description:` fields have dropped the "route to /vm-handoff" clause. Both files now hand off to `/commit-review` without the old exception block. |
| Phase 6 — `commands/land.md` | Partial | `commands/land.md:21`, `commands/land.md:38`, `commands/land.md:43`; drift at `commands/land.md:3` | The body matches the plan, but the frontmatter description still frames the freshness gate as "VM smoke." |
| Phase 7 — sweep files | Partial | `README.md:7`, `README.md:15`, `backlog.md:16`, `backlog.md:21`, `commands/wrapup.md:164`, `commands/wrapup.md:176`; misses at `docs/plans/README.md:15`, `docs/plans/verification-and-handoff-design-agent.html:138` | The named sweep files were mostly cleaned. The repo-wide sweep still leaves a stale plan-index row and a stale generated HTML companion that refer to the deleted mechanism as current. |

## Critical Drift

- Severity: Critical | Plan says: `"Green-gate freshness" bullet: "the branch's VM gate" → "the branch's tests/verification"` (`docs/plans/executor-mac-parity-remove-deviation-handback.md:109`) and `"VM gate outstanding?" bullet → "GPU / high-throughput step outstanding?"` (`docs/plans/executor-mac-parity-remove-deviation-handback.md:111`). Code still says: `green-gate freshness (is the branch's VM smoke still valid after main moved under it?)` in the live `/land` YAML description. | Evidence: `commands/land.md:3` | Required fix: rewrite the frontmatter clause to generic verification wording, e.g. `green-gate freshness (does the branch's verification still describe the tree after main moved under it?)`.

## Missing Pieces

- Plan item | Where it should land | Why it matters | Suggested code change
- Phase 7 repo-wide sweep did not update the plan index row for the deleted canonical spec | `docs/plans/README.md:15` | It currently says `Verification & VM-Handoff Design capability — canonical spec now at references/verification-and-handoff-design.md`, but that file is now deleted. A reader following the index hits a dead current-state pointer. | Change the row to `Completed — superseded` and say the vm-status-doc handoff mechanism and canonical spec were retired by `executor-mac-parity-remove-deviation-handback.md`.
- Phase 3 superseded banner was added only to the markdown plan, not its generated HTML companion | `docs/plans/verification-and-handoff-design-agent.html:113`, `:138`, `:141`, `:155`, `:228`, `:333`, `:401` | The HTML is tracked and still presents the old mechanism as active/generated design content without the markdown file's superseded warning. | Regenerate the HTML from the superseded markdown or add an equivalent top-of-page superseded banner / retire the HTML if generated companions are no longer maintained.
- Diff scope contains a modified target plan not listed in the user-provided diff scope or the plan's Files to Modify | `git diff --name-status`: `M docs/plans/executor-mac-parity-remove-deviation-handback.md`; plan Files to Modify at `docs/plans/executor-mac-parity-remove-deviation-handback.md:124` | The implementation diff includes a large rewrite of the governing plan itself. That may be intentional plan evolution, but it is outside the stated implementation file list and should not be silently bundled as implementation drift. | Either explicitly include the plan-doc rewrite in the diff scope / commit message, or separate it from the implementation commit if the plan was supposed to be the fixed review target.

## Residual References Sweep

- `commands/land.md:3` — residual — needs fixing. Current operational frontmatter still says `VM smoke`, preserving the retired VM-gate framing.
- `commands/land.md:75` — legitimate — filesystem fact, not authority. `planner-Mac only` is about the git-ignored `vista-pm/personal/` tree being absent on the VM.
- `commands/phi-vet.md:33` — legitimate — PHI-free-machine hook behavior; `planner machine` means a machine with no PHI access, not the retired Mac/VM authority split.
- `commands/wrapup.md:76` — legitimate — filesystem fact, not authority. The personal in-flight index exists only on the Mac.
- `backlog.md:21` — legitimate — historical pointer to a now-retired agent.
- `backlog.md:24`, `backlog.md:26`, `backlog.md:29` — legitimate — headless VM / browser-access follow-up, not authority split.
- `claude_ops.md:34`, `claude_ops.md:35` — legitimate — explicit negation of the planner/executor authority split.
- `claude_ops.md:61`, `claude_ops.md:226` — legitimate — says outputs do not go into rendered/readback handoff docs.
- `hooks/phi-vet-gate.sh:27`, `hooks/README.md:95`, `hooks/lib/is-phi-free-machine.sh:7`, `hooks/lib/phi-free-machines.example:5`, `hooks/lib/phi-free-machines.example:8`, `hooks/lib/phi-free-machines.example:20` — legitimate — PHI-free allowlist examples; not the retired Claude-Code authority split.
- `docs/plans/README.md:14` — legitimate historical completed-plan row for the prior PHI-posture retirement.
- `docs/plans/README.md:15` — residual — needs fixing. Points at deleted `references/verification-and-handoff-design.md` as current canonical spec.
- `docs/plans/README.md:16` — legitimate historical/superseded hook row.
- `docs/plans/executor-mac-parity-remove-deviation-handback.md:3`, `:9`, `:16`, `:17`, `:19`, `:20`, `:50`, `:56`, `:63`, `:64`, `:65`, `:70`, `:77`, `:80`, `:81`, `:100`, `:101`, `:103`, `:107`, `:112`, `:116`, `:117`, `:118`, `:119`, `:128`, `:129`, `:130`, `:153`, `:155`, `:158`, `:159`, `:165` — legitimate — this is the active plan describing what is being retired.
- `docs/plans/verification-and-handoff-design-agent.md:3`, `:4`, `:5`, `:7` — legitimate — new superseded banner.
- `docs/plans/verification-and-handoff-design-agent.md:13`, `:23`, `:38`, `:71`, `:84`, `:89`, `:90`, `:96`, `:98`, `:102`, `:103`, `:117`, `:129`, `:138`, `:146`, `:151`, `:155`, `:161`, `:165`, `:167`, `:169`, `:171`, `:175`, `:203`, `:216`, `:220`, `:225`, `:234`, `:239` — legitimate only because the file is now explicitly superseded at `:3-7`; without that banner these would be residual active-policy statements.
- `docs/plans/verification-and-handoff-design-agent.html:93`, `:113`, `:124`, `:138`, `:141`, `:146`, `:155`, `:193`, `:228`, `:231`, `:266`, `:271`, `:279`, `:291`, `:296`, `:309`, `:323`, `:333`, `:335`, `:339`, `:341`, `:342`, `:352`, `:355`, `:398`, `:401`, `:418`, `:428` — residual — needs fixing. This tracked generated HTML companion has no superseded banner and still presents the retired canonical spec / `vm-handoff` flow as active.
- `docs/plans/vm-shell-guard-hook.md:6`, `:25`, `:51`, `:59`, `:124`, `:126`, `:127`, `:131`, `:134`, `:139`, `:145`, `:151`, `:153`, `:155`, `:175`, `:181`, `:220`, `:221`, `:230` — legitimate — historical content under an existing superseded banner.
- `docs/plans/retire-planner-mac-phi-vm-split.md:3`, `:7`, `:14`, `:15`, `:22`, `:67`, `:81`, `:82`, `:149`, `:159`, `:160`, `:161`, `:199`, `:207`, `:211`, `:216`, `:223`, `:233`, `:235`, `:265`, `:270`, `:272`, `:296`, `:299`, `:334`, `:375`, `:378`, `:416`, `:418` — legitimate — prior completed plan/historical context; several statements were the old intermediate state that this plan supersedes.
- `docs/plans/retire-planner-mac-phi-vm-split.html:7`, `:99`, `:104`, `:105`, `:111`, `:126`, `:132`, `:234`, `:342`, `:367`, `:389`, `:390`, `:409`, `:412`, `:457`, `:461`, `:482`, `:483`, `:484`, `:506` — legitimate historical generated companion for the prior completed plan.
- `docs/plans/reviews/retire-planner-mac-phi-vm-split-feedback-claude.md:3`, `:13`, `:21`, `:43`, `:51`, `:52`, `:76`, `:77`, `:78`, `:79`, `:80`, `:81`, `:84`, `:85`, `:86`, `:87`, `:88`, `:89`, `:90`, `:91`, `:92`, `:93` — legitimate historical review artifact.
- `docs/plans/reviews/retire-planner-mac-phi-vm-split-implementation-feedback.md:3`, `:7`, `:17`, `:18`, `:24`, `:26`, `:30`, `:38`, `:51`, `:55`, `:56`, `:57`, `:69`, `:71` — legitimate historical review artifact.
- `docs/plans/reviews/verification-and-handoff-design-agent-feedback.md:9`, `:10`, `:11`, `:15`, `:20`, `:21`, `:22`, `:23`, `:27`, `:28`, `:32`, `:33`, `:34`, `:35`, `:42`, `:48`, `:54`, `:56` — legitimate historical review artifact for the now-superseded capability.
- `docs/plans/reviews/verification-and-handoff-design-agent-implementation-feedback.md:11`, `:17`, `:30`, `:31`, `:34`, `:43`, `:44`, `:45`, `:46`, `:53`, `:54`, `:56`, `:61` — legitimate historical review artifact for the now-superseded capability.
- `/Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.vm.md:1`, `:11`, `:36` — legitimate — "Executor" is explicitly scoped to GPU/high-throughput capacity.
- `/Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.vm.md:57` — legitimate — explicitly negates the old authority rule: `there's no "planning happens on the Mac" rule anymore`.

## Defensible Deviations

- The plan literal in Phase 3 only required a superseded banner on `docs/plans/verification-and-handoff-design-agent.md`, not a rewrite of that old plan body. Keeping the old body intact under a clear banner is defensible preservation of design history.
- `CLAUDE.vm.md` keeps `Executor` in the title and machine-posture heading. Given the surrounding wording limits it to GPU/high-throughput capacity and `CLAUDE.vm.md:56-60` grants full planning/re-planning parity, this is not an authority split.
- `backlog.md:24-31` keeps "VM-side plan/HTML viewing" because it describes headless-browser / bucket-bridge logistics, not a Mac planner vs VM executor authority model.

## Suggested Code Edits

- `commands/land.md:3` — change `green-gate freshness (is the branch's VM smoke still valid after main moved under it?)` to `green-gate freshness (does the branch's verification still describe the tree after main moved under it?)`.
- `docs/plans/README.md:15` — change the row from current canonical-spec wording to a superseded row, e.g. `Completed — superseded | Yes | Verification & VM-Handoff Design capability; vm-status-doc mechanism and canonical spec retired by executor-mac-parity-remove-deviation-handback.md; history preserved on legacy/vm-handoff-doc-system-2026-08.`
- `docs/plans/verification-and-handoff-design-agent.html:113` and top-of-page area — regenerate from the superseded markdown or add a visible superseded banner equivalent to `docs/plans/verification-and-handoff-design-agent.md:3-7`.
- `docs/plans/executor-mac-parity-remove-deviation-handback.md` — decide whether this plan rewrite belongs in the implementation commit. If yes, include it explicitly in the implementation diff scope / commit message; if no, separate it from the implementation diff.

## Questions For The Author

- Should generated plan HTML companions be treated as historical artifacts that may stay stale, or should every superseded markdown plan with a tracked `.html` companion get the same superseded banner/regeneration before commit?
- Is the large uncommitted rewrite of `docs/plans/executor-mac-parity-remove-deviation-handback.md` intended to ship with this implementation, despite not being listed in the user-provided diff scope?

## Audit Trail

- claude_ops.md
- docs/lessons.md
- docs/plans/executor-mac-parity-remove-deviation-handback.md
- README.md
- backlog.md
- commands/land.md
- commands/review-implementation.md
- commands/review-plan.md
- commands/review-tests.md
- commands/wrapup.md
- commands/vm-handoff.md (deleted diff; legacy branch copy)
- references/verification-and-handoff-design.md (deleted diff; legacy branch copy)
- docs/plans/verification-and-handoff-design-agent.md
- docs/plans/verification-and-handoff-design-agent.html
- docs/plans/README.md
- docs/plans/vm-shell-guard-hook.md
- docs/plans/retire-planner-mac-phi-vm-split.md
- docs/plans/retire-planner-mac-phi-vm-split.html
- docs/plans/reviews/retire-planner-mac-phi-vm-split-feedback-claude.md
- docs/plans/reviews/retire-planner-mac-phi-vm-split-implementation-feedback.md
- docs/plans/reviews/verification-and-handoff-design-agent-feedback.md
- docs/plans/reviews/verification-and-handoff-design-agent-implementation-feedback.md
- hooks/phi-vet-gate.sh
- hooks/README.md
- hooks/lib/is-phi-free-machine.sh
- hooks/lib/phi-free-machines.example
- /Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.md
- /Users/philadamson/Documents/Stanford/VISTA/code/CLAUDE.vm.md
