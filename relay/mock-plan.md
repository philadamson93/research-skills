# Mock plan — drill-down relay speed test

> Synthetic plan doc. Built to exercise the explain-plan drill-down relay
> end-to-end with a small but realistic node graph. NOT a real change to any
> repo — every file path below is fictional.

## What you're building

A toy "weekly digest email" feature that reads aggregated metrics from a
sibling repo, formats them into an HTML email, and pushes to a transactional
mail provider. The shape of the change covers the kind-gating cases we care
about for the drill-down test:

- `added` — a new orchestrator + a new template + a new output table.
- `modified` — one existing aggregator gets a new column.
- `untouched` — the upstream metrics source isn't touched but is in the diagram.
- `external` — the mail provider is a sibling repo.
- `deferred` — a slice 2 dashboard is out of scope.

## Status

- **Status**: PENDING
- **Owner**: Phil
- **Branch**: `mock/weekly-digest`
- **Reviewed**: synthetic — never actually reviewed

## Knobs

| Knob | Type | Default | Notes |
|------|------|---------|-------|
| `digest_recipients` | List[str] | `[]` | Empty = no send (fail-closed) |
| `digest_lookback_days` | int | `7` | 7 or 30 are the supported values |
| `digest_dry_run` | bool | `True` | Default-safe; renders HTML but skips the send |

## Files you'll touch

| File | Action | Why |
|------|--------|-----|
| `src/digest/orchestrator.py` | NEW | Top-level orchestrator wiring metrics → template → send |
| `src/digest/template.py` | NEW | Jinja2 template for the email body |
| `src/metrics/aggregator.py` | MODIFY | Add `n_users_active` column to the weekly rollup |
| `outputs/digest_runs.parquet` | NEW | Output: one row per digest send (recipients, status, hash) |
| `tests/test_digest.py` | NEW | Coverage for orchestrator + template render |

## Implementation steps

### Step 1 — extend aggregator (SHIPPED)

Add `n_users_active` to `weekly_rollup` in `src/metrics/aggregator.py`. Count
distinct `user_id` in the lookback window. Verify with snapshot test.

### Step 2 — build template (PENDING)

Author `src/digest/template.py` rendering the rollup row into HTML. Plain
inline-style, no external CSS.

### Step 3 — orchestrator (PENDING)

`src/digest/orchestrator.py`: reads `weekly_rollup`, renders template per
recipient, writes one row per send to `outputs/digest_runs.parquet`, calls
the mail provider unless `dry_run`. Wire `digest_recipients` knob fail-closed
on empty.

### Step 4 — dashboard (DEFERRED to slice 2)

A status dashboard showing recent digest sends. Not in this PR.

## Gotchas

- **Fail-closed on empty recipients**: empty list = no send, no error. Don't
  raise — the daily cron should be idempotent on a no-op day.

## Open questions

### OQ1 — should `dry_run` default change after rollout?

We're shipping with `dry_run=True` to be safe. After two weeks of clean
metrics, flip to `False`?

### OQ2 — keep `digest_runs.parquet` or move to a real table?

Parquet is simpler for v1 but doesn't compose with our usual `task_*` tables.
Move to BigQuery in slice 2?

## Out of scope

- Bounce/unsubscribe handling — assume the mail provider handles it.
- Per-user opt-in — every recipient in `digest_recipients` gets the digest.
- Localization — English only for v1.
