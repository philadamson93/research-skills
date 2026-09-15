#!/usr/bin/env python3
"""Put a `Program:` line in every live plan doc's MOUNT copy, naming the brief it serves.

The mapping is not maintained by hand: it is read out of the briefs' own Stages tables, so a
plan only gets stamped if some brief actually claims it, and the stage numbers can never drift
from the brief that produced them.

Only the mount copies are touched. The git originals stay frozen and unstamped, which is why
this costs no PHI review -- stamping the 30 claimed plans in git would have meant a commit per
repo and a personal read of every staged markdown file.

ORDER MATTERS: run this AFTER scripts/copy-plans-to-mount.sh, never before. That script overwrites
each mount file from its git blob, which erases the `Program:` line this one adds. Safe to re-run at
any time -- it is idempotent and reports how many files were already correct.

Usage:  stamp-program-lines.py [--apply]
        default is a dry run
"""
import re, sys, pathlib

MOUNT = pathlib.Path('/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning')
PROGRAMS = MOUNT / 'programs'
APPLY = '--apply' in sys.argv


def stage_rows(text):
    in_table = False
    for line in text.splitlines():
        if line.startswith('## Stages'):
            in_table = True
            continue
        if in_table and line.startswith('## '):
            return
        if in_table and line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) < 5 or cells[0] == '#' or set(cells[0]) <= {'-'}:
                continue
            yield cells[0], cells[-1]


# brief -> total stages, and every plan it claims
claims = {}   # (repo, filename) -> [brief_slug, {stages}, total]
for brief in sorted(PROGRAMS.glob('*.md')):
    if brief.name.startswith('_') or brief.stem.endswith('research-findings'):
        continue
    text = brief.read_text()
    rows = list(stage_rows(text))
    if not rows:
        continue
    total = max(int(n) for n, _ in rows if n.isdigit())
    current = None   # the briefs write later rows as "same plan, phase 3" without repeating
                     # the path, so a bare "same plan" row belongs to the last one linked
    for num, cell in rows:
        toks = re.findall(r'`([^`]+?\.md)`', cell)
        if not toks and current and 'same plan' in cell.lower():
            toks = [current]
        elif toks:
            current = toks[0]
        for tok in toks:
            tok = tok.lstrip('~/').replace('code/', '', 1)
            parts = tok.split('/')
            if len(parts) < 3 or parts[1] != 'docs':
                continue
            repo, fname = parts[0], parts[-1]
            # research-skills is excluded from the mount copy on purpose -- its plans stay in
            # git, where they are the product, so its Program: line is committed there instead
            if repo == 'research-skills':
                continue
            # A plan often backs several stages of one brief -- stamping just the first would
            # read as "this work is at stage 3" when it actually spans 3 to 8. Collect them all
            # and emit a range, matching the `stages 1-6 of 6` form the plan template uses.
            key = (repo, fname)
            if key in claims:
                if claims[key][0] == brief.stem:
                    claims[key][1].add(num)
            else:
                claims[key] = [brief.stem, {num}, total]

stamped = skipped = missing = 0
for (repo, fname), (slug, stages, total) in sorted(claims.items()):
    nums = sorted(int(s) for s in stages if s.isdigit())
    # A hyphenated range would claim the plan spans every stage between the ends. That is true
    # for a phased plan and false for a document two scattered stages happen to cite, so only
    # collapse to a range when the stages are actually contiguous.
    if len(nums) == 1:
        stage, word = str(nums[0]), 'stage'
    elif nums == list(range(nums[0], nums[-1] + 1)):
        stage, word = f'{nums[0]}-{nums[-1]}', 'stages'
    else:
        stage, word = ', '.join(str(n) for n in nums), 'stages'
    dest = MOUNT / repo / fname
    if not dest.exists():
        print(f'  missing  {repo}/{fname}  (not copied to the mount yet)')
        missing += 1
        continue
    text = dest.read_text()
    line = f'Program: `{MOUNT}/programs/{slug}.md` — {word} {stage} of {total}'
    if re.search(r'^Program:', text, re.M):
        new = re.sub(r'^Program:.*$', line, text, count=1, flags=re.M)
        verb = 'update '
    elif re.search(r'^Reference:', text, re.M):
        new = re.sub(r'^(Reference:.*)$', r'\1\n' + line.replace('\\', r'\\'), text, count=1, flags=re.M)
        verb = 'stamp  '
    else:
        new = line + '\n' + text
        verb = 'prepend'
    if new == text:
        skipped += 1
        continue
    print(f'  {verb}  {repo}/{fname}  -> {slug} {word} {stage}/{total}')
    if APPLY:
        dest.write_text(new)
        # keep the manifest describing what is actually on the mount: a stamped file no longer
        # matches the git object it was copied from, and silently leaving a stale hash there
        # would make the copy script's own drift check meaningless
        mani = MOUNT / repo / '.manifest.tsv'
        if mani.exists():
            rows = []
            for row in mani.read_text().splitlines():
                cols = row.split('\t')
                if cols and cols[0] == fname and len(cols) >= 4:
                    ref = cols[1] if cols[1].endswith('+stamped') else cols[1] + '+stamped'
                    cols = [cols[0], ref, 'stamped-see-brief', str(dest.stat().st_size)]
                rows.append('\t'.join(cols))
            mani.write_text('\n'.join(rows) + '\n')
    stamped += 1

print(f'\n{stamped} to stamp, {skipped} already correct, {missing} not on the mount yet'
      f'  ({len(claims)} plans claimed by briefs)')
if not APPLY:
    print('dry run -- nothing written. re-run with --apply')
