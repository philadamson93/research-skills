#!/usr/bin/env bash
# Repair the docs/plans symlink in every checkout on this machine.
#
# Run this after pulling a migration commit. When docs/plans is untracked on main, git DELETES
# the real files in every other checkout of that repo, so each one needs its link recreated —
# there are about 50 of them here, including separate clones (vista_bench_fresh, the two
# *-mcp-runtime clones) that update on their own schedule rather than with their worktree siblings.
#
# Safe to run any time, as often as you like. A checkout still sitting on a pre-migration branch
# is reported "not yet" and left completely alone: its real files are correct for the commit it has.
#
#   bash scripts/plans_doctor.sh            # dry run — says what it would do
#   bash scripts/plans_doctor.sh --apply    # make the links
#   bash scripts/plans_doctor.sh --apply vista_bench    # one repo only
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
exec uv run --script "$here/plans_offgit.py" doctor "$@"
