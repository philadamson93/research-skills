# User-Level Claude Code Settings

These apply to all repos. For full operating standards, see `docs/claude_ops.md` in the current repo.

## Environment

- Code execution is allowed on this machine.

## Interaction style

- **Multi-choice questions → `AskUserQuestion` tool, not inline prose.** Whenever you'd otherwise present me with one or more multiple-choice questions in a single turn (numbered options, "(a) / (b) / (c)", "Option 1 / Option 2", or "should I do X or Y?"), use the `AskUserQuestion` tool instead. Easier to parse and lets me answer one question at a time. Applies even when you're recommending a default — surface the recommendation as the first option. If you'd otherwise stack 3+ questions in one reply, this is the format. Free-form / open-ended questions ("what would you like to do next?") are fine inline.
