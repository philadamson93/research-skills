#!/usr/bin/env bash
# Copy every repo's docs/plans tree (plans, reviews, rendered explainers) to the mount,
# non-destructively, and verify each file byte-for-byte against the git object it came from.
#
# Why it reads git objects instead of the working tree: most checkouts sit on stale feature
# branches, so a working-tree copy captures whatever branch a checkout is parked on. Measured
# 2026-09-15: rad-eval's checkout was missing 86 of main's plan docs, while crc-extraction-agent
# had 43 in its tree against 2 on main. Neither direction is right, so this walks every ref.
#
# When the same path exists on several refs with different content, main wins if main has the
# file at all; a branch version is used only for plans main does not carry. The manifest records
# which ref each file came from.
#
# It is deliberately NOT "whichever branch touched it most recently". Measured 2026-09-15: that
# rule handed 16 of vista-eval's plan docs to an unlanded bulk-rename branch last touched in
# August, so the mount would have shown terminology main does not use. 45 of 196 multi-version
# paths resolved to a branch that way.
#
# Nothing is written to any repo. No checkout, no fetch, no index change: `git cat-file` only.
#
# ORDER MATTERS: run this BEFORE scripts/stamp-program-lines.py, never after. This script
# overwrites each mount file from its git blob, which erases the `Program:` line the stamper adds.
# It warns when it is about to overwrite a file the manifest records as stamped.
#
# Usage:  copy-plans-to-mount.sh [--apply] [repo ...]
#         default is a dry run that prints what it would copy
set -euo pipefail

MOUNT=/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning
CODE="${CODE_ROOT:-$HOME/code}"
DEFAULT_REPOS=(vista-eval vista_bench vista-ct rad-eval paper-trail agentic-label-opt
               contrastive-3d-onc crc-extraction-agent femr-private vista-cohort)
# research-skills is excluded on purpose: its plans stay in git, where they are the product.

APPLY=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
REPOS=("${ARGS[@]:-${DEFAULT_REPOS[@]}}")

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
total_files=0 total_conflicts=0 total_bad=0 total_unc=0 total_extras=0 total_stamped=0

for repo in "${REPOS[@]}"; do
  d="$CODE/$repo"
  [ -d "$d/.git" ] || { echo "skip $repo (not a git repo at $d)"; continue; }

  # path -> one line per ref holding it: "<path>\t<blobsha>\t<ref>"
  : > "$work/index"
  while read -r ref; do
    git -C "$d" ls-tree -r "$ref" -- docs/plans 2>/dev/null \
      | awk -v r="$ref" '$2=="blob" && ($4 ~ /\.md$/ || $4 ~ /\.html$/) {print $4"\t"$3"\t"r}'
  done < <(git -C "$d" for-each-ref --format='%(refname)' refs/heads refs/remotes) >> "$work/index"

  [ -s "$work/index" ] || { echo "skip $repo (no plan docs on any ref)"; continue; }

  cut -f1 "$work/index" | sort -u > "$work/paths"
  n_paths=$(wc -l < "$work/paths")
  conflicts=0 copied=0 bad=0
  dest_root="$MOUNT/$repo"
  prev_manifest=""; stamped_clobbered=0
  [ -f "$dest_root/.manifest.tsv" ] && prev_manifest=$(cat "$dest_root/.manifest.tsv")
  [ "$APPLY" -eq 1 ] && { mkdir -p "$dest_root"; : > "$dest_root/.manifest.tsv"; }

  while read -r path; do
    # distinct CONTENT for this path, not distinct refs: the same blob listed on main,
    # origin/main and origin/HEAD is one version, not three
    mapfile -t shas < <(awk -F'\t' -v p="$path" '$1==p {print $2}' "$work/index" | sort -u)
    if [ "${#shas[@]}" -eq 1 ]; then
      sha=${shas[0]}
      ref=$(awk -F'\t' -v p="$path" '$1==p {print $3; exit}' "$work/index")
    else
      # genuinely different content for one path. main is authoritative when it has the file;
      # otherwise fall back to whichever branch touched it last.
      msha=$(git -C "$d" rev-parse -q --verify "origin/main:$path" 2>/dev/null || true)
      if [ -n "$msha" ]; then
        sha=$msha; ref=origin/main
      else
        best_ts=-1; sha=""; ref=""
        for s in "${shas[@]}"; do
          r=$(awk -F'\t' -v p="$path" -v s="$s" '$1==p && $2==s {print $3; exit}' "$work/index")
          ts=$(git -C "$d" log -1 --format=%ct "$r" -- "$path" 2>/dev/null || echo 0)
          if [ "${ts:-0}" -gt "$best_ts" ]; then best_ts=$ts; sha=$s; ref=$r; fi
        done
      fi
      conflicts=$((conflicts+1))
    fi

    dest="$dest_root/${path#docs/plans/}"
    if [ "$APPLY" -eq 1 ]; then
      # a stamped file carries a `Program:` line this copy is about to erase -- say so rather than
      # silently reverting it, since the stamps are only recoverable by re-running the stamper
      if [ -n "$prev_manifest" ] && grep -qF "${path#docs/plans/}"$'\t' <<< "$prev_manifest" \
         && grep -F "${path#docs/plans/}"$'\t' <<< "$prev_manifest" | grep -q '+stamped'; then
        echo "  note: overwriting a stamped file, re-run stamp-program-lines.py after this: ${path#docs/plans/}"
        stamped_clobbered=$((stamped_clobbered+1))
      fi
      mkdir -p "$(dirname "$dest")"
      git -C "$d" cat-file blob "$sha" > "$dest"
      # verify: re-hash what actually landed on the mount and compare to the source object
      got=$(git -C "$d" hash-object "$dest")
      if [ "$got" != "$sha" ]; then
        echo "  MISMATCH $repo/${path#docs/plans/}  want=$sha got=$got"; bad=$((bad+1))
      fi
      printf '%s\t%s\t%s\t%s\n' "${path#docs/plans/}" "$ref" "$sha" "$(stat -c %s "$dest")" \
        >> "$dest_root/.manifest.tsv"
    fi
    copied=$((copied+1))
  done < "$work/paths"

  # Second pass: plan docs that were never committed. These are invisible to everything above,
  # and they are the most fragile documents in the system -- an uncommitted file in a shared
  # checkout has no saved copy if a reset or a worktree removal takes it. Copy one only when no
  # committed version of that path exists, so a stale untracked draft can never overwrite the
  # landed version on the mount.
  unc=0 unc_skip=0
  while read -r path; do
    [ -z "$path" ] && continue
    case "$path" in *.md|*.html) ;; *) continue ;; esac
    if grep -qP "^\Q$path\E\t" "$work/index" 2>/dev/null; then
      unc_skip=$((unc_skip+1)); continue
    fi
    dest="$dest_root/${path#docs/plans/}"
    if [ "$APPLY" -eq 1 ]; then
      mkdir -p "$(dirname "$dest")"
      src_hash=$(git -C "$d" hash-object "$d/$path")
      cp "$d/$path" "$dest"
      dst_hash=$(git -C "$d" hash-object "$dest")
      # verify an uncommitted copy the same way a committed one is verified: hash BOTH sides.
      # recording only the destination hash proves nothing -- it would match whatever landed.
      if [ "$src_hash" != "$dst_hash" ]; then
        echo "  MISMATCH (uncommitted) $repo/${path#docs/plans/}  src=$src_hash dst=$dst_hash"
        bad=$((bad+1))
      fi
      br=$(git -C "$d" branch --show-current 2>/dev/null || echo detached)
      printf '%s\t%s\t%s\t%s\n' "${path#docs/plans/}" "uncommitted:${br:-detached}" \
        "$src_hash" "$(stat -c %s "$dest")" >> "$dest_root/.manifest.tsv"
    fi
    unc=$((unc+1))
  done < <(git -C "$d" ls-files --others --exclude-standard -- docs/plans 2>/dev/null)

  # Count what is actually on the mount against what we just wrote. The copy is additive and never
  # deletes, so a file the source set no longer selects stays behind -- worth reporting, because
  # otherwise the mount silently accumulates plans that no longer exist anywhere in git.
  extras=0
  if [ "$APPLY" -eq 1 ] && [ -f "$dest_root/.manifest.tsv" ]; then
    dest_n=$(find "$dest_root" -type f ! -name '.manifest.tsv' 2>/dev/null | wc -l)
    mani_n=$(grep -c . "$dest_root/.manifest.tsv" 2>/dev/null || echo 0)
    extras=$(( dest_n - mani_n ))
    if [ "$extras" -gt 0 ]; then
      echo "  note: $extras file(s) on the mount are not in this run's manifest (left in place, never deleted):"
      cut -f1 "$dest_root/.manifest.tsv" | sort -u > "$work/mani_paths"
      ( cd "$dest_root" && find . -type f ! -name '.manifest.tsv' | sed 's|^\./||' | sort -u ) > "$work/dest_paths"
      comm -13 "$work/mani_paths" "$work/dest_paths" | head -10 | sed 's/^/        /'
    fi
  fi

  printf '%-24s %5s files  %3s multi-version paths  %2s uncommitted (+%s skipped)  %s%s\n' \
    "$repo" "$n_paths" "$conflicts" "$unc" "$unc_skip" \
    "$([ "$APPLY" -eq 1 ] && echo "copied, $bad mismatches" || echo 'dry run')" \
    "$([ "$stamped_clobbered" -gt 0 ] && echo ", $stamped_clobbered stamps to re-apply" || echo '')"
  total_unc=$((total_unc+unc)); total_extras=$((total_extras+extras)); total_stamped=$((total_stamped+stamped_clobbered))
  total_files=$((total_files+copied)); total_conflicts=$((total_conflicts+conflicts)); total_bad=$((total_bad+bad))
done

echo
echo "total: $total_files committed files (+$total_unc never-committed), $total_conflicts paths that existed in more than one version, $total_bad checksum mismatches"
[ "$total_extras" -gt 0 ] && echo "$total_extras file(s) on the mount not in any manifest — left in place; nothing is ever deleted"
[ "$total_stamped" -gt 0 ] && echo "RE-RUN scripts/stamp-program-lines.py --apply: $total_stamped stamped file(s) were overwritten"
[ "$APPLY" -eq 1 ] || echo "dry run — nothing written. re-run with --apply"
exit $(( total_bad > 0 ? 1 : 0 ))
