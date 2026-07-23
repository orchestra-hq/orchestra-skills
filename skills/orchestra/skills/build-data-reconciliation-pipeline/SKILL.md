---
name: build-data-reconciliation-pipeline
description: >
  Builds Orchestra pipeline YAML using the native Data Reconciliation tasks
  (DATA_RECONCILIATION_MANUAL_QUERY, DATA_RECONCILIATION_CURSOR_FIELD) to prove two data
  stores match — the "did the migration land correctly" check between a source and
  destination integration (SNOWFLAKE, SQL_SERVER, DATABRICKS, any pairing). Use whenever the
  user wants to compare, validate, or reconcile data across two systems for a migration,
  replatform, cutover, or CDC/replication setup — phrases like "make sure the migration
  matches", "reconcile Snowflake and Databricks", "validate the cutover", "did we lose any
  rows moving to the new warehouse", "set up drift monitoring", or any mention of Data
  Reconciliation / DataRec. Produces a one-off full-match validation pipeline plus,
  optionally, an ongoing cursor-field drift monitor. Don't use create-orchestra-pipeline for
  this — Data Reconciliation tasks have sharp edges (single-scalar results, thresholds that
  silently no-op if omitted) covered in this skill's references.
---

# Build Data Reconciliation Pipeline

Generate an Orchestra pipeline that uses the platform's built-in Data Reconciliation task
types to confirm two systems match, rather than hand-rolling comparison SQL in a generic
task. Orchestra ships two flavors, and the right migration story usually uses both, one
after the other:

- **`DATA_RECONCILIATION_MANUAL_QUERY`** — runs one query against each side and diffs the
  result. This is the full, one-off "prove the migration landed" check on cutover day: every
  table, row counts plus content-level aggregates.
- **`DATA_RECONCILIATION_CURSOR_FIELD`** — compares row count and/or max value of one
  monotonic column (an id or `updated_at`), using a cache so it only scans new rows each run.
  This is the cheap, ongoing drift monitor you schedule *after* the cutover has already been
  validated — it's not meant to replace the full check, it's meant to catch future drift
  without re-scanning everything every time.

Both are restricted to `SNOWFLAKE`, `SQL_SERVER`, and `DATABRICKS` as source/destination —
if the user names a different system (Postgres, BigQuery, ...), say so up front; there's no
native DataRec task for that pair, and the fallback (independent query tasks plus a Python
task doing the diff by hand) is a materially different, more manual pipeline — don't build
it silently as if it were the same thing. See `references/unsupported-engine-fallback.md` for
the pattern and a worked example.

## References

- `references/unsupported-engine-fallback.md` — read this first whenever either system isn't
  SNOWFLAKE/SQL_SERVER/DATABRICKS. The hand-rolled fallback pattern (independent query tasks +
  a Python diff task) with a worked Postgres↔Snowflake example, validated against the live API.
- `references/query-templates.md` — **read before writing any query.** Per-engine SQL for
  row counts, column-level aggregates, identifier qualification, and — importantly — why
  timestamps need converting to epoch-seconds and why every task needs an explicit
  threshold (the single most common way this silently does nothing).
- `references/pipeline-patterns.md` — the matrix-over-checks authoring pattern (one task
  group per check *kind*, fanned out over tables/columns via `${{ MATRIX.x['key'] }}`), full
  example YAML for both the validation and monitor pipelines, and how to handle scope that's
  a schema/database rather than a fixed table list.
- `../../references/orchestra/pipeline/yaml-authoring.md` — base pipeline schema, variable
  syntax, validation workflow.
- `../../references/orchestra/mcp/tools-quick-ref.md` — MCP tool names for validating and
  registering the pipeline.

## Workflow

### Step 1 — Scope the comparison

Nail down, by asking rather than assuming whatever is ambiguous:

- **Source and destination**: integration (must each be `SNOWFLAKE`/`SQL_SERVER`/
  `DATABRICKS`), connection, and database/schema for each side.
- **Table scope**: an explicit list of tables, or a whole schema/database to cover. Table
  and column *names* may differ between the two sides (renames are common mid-migration) —
  ask for the mapping rather than assuming identical names once the two systems are
  different engines.
- **What's actually wanted**: the one-off cutover validation, the ongoing scheduled monitor,
  or both. "Full check initially, then incremental on a schedule" is the common real-world
  shape — build the validation pipeline first, then the monitor, rather than picking one.
- **Tolerance**: is an exact match expected (typical for a cutover), or is some lag
  acceptable (reconciling against a still-live source, or a replica with known latency)? This
  determines every threshold expression downstream — see `query-templates.md`.

### Step 2 — Resolve the table & column list

See `references/pipeline-patterns.md` for the full reasoning. Short version: if the user
gave you specific tables, use them; ask which columns matter for the aggregate checks rather
than enumerating every column of a wide table. If they only named a schema/database, ask
whether to (a) get the table/column list pasted in, and build a static pipeline from it, or
(b) build a self-discovering pipeline that queries `information_schema` at runtime — worth
the extra complexity only when the table set will keep changing. Never invent a table or
column name.

### Step 3 — Build the migration-validation pipeline (manual query)

One task group for row counts, matrixed over every table in scope; one task group for
column-level aggregates, matrixed over every table+column+metric check. Use
`query-templates.md` for the actual SQL per engine, and set an explicit
`error_threshold_expression` on **every** task — omitting it means the task always succeeds
regardless of the actual difference, which defeats the entire point of the pipeline. Default
to `!= 0` (exact match) unless the user has told you some tolerance is legitimate.

Don't try to cram a whole table's comparison into one task: a `DATA_RECONCILIATION_MANUAL_QUERY`
task's queries must each return a single scalar, so "compare table X" is really "one row-count
task plus one task per column-metric," fanned out via matrix, not one task per table.

### Step 4 — Build the ongoing drift monitor (cursor field), if wanted

One task group, matrixed over tables, each entry naming the source/destination cursor column
for that table. Confirm the cursor column is genuinely monotonic (an identity/auto-increment
id, or an `updated_at` that only ever increases) — ask rather than guess, since a column that
isn't truly monotonic produces false drift alerts. Add a schedule (cron) rather than a
webhook/manual trigger — this pipeline exists to run repeatedly on its own.

### Step 5 — Validate

```bash
orchestra-cli validate <path/to/pipeline.yml>
```

Or MCP `validate_pipeline` if the CLI isn't available. Fix and re-validate until clean —
common misses here are a missing `error_threshold_expression`, a query that returns more
than one column/row, a matrix key referenced with the wrong quoting
(`${{ MATRIX.x['key'] }}`, not `${{ MATRIX.x.key }}`), or a threshold expression templated
from the matrix instead of hardcoded per task group — see the "threshold policy" note in
`pipeline-patterns.md`, that one only surfaces at validation time.

### Step 6 — Report

Summarize concisely:

1. File path(s) — validation pipeline, and monitor pipeline if built.
2. What's checked: table count, which columns/metrics per table, and **anything excluded
   and why** (a wide table where you only checked a subset of columns, a table skipped for
   lack of a usable cursor field, etc.) — don't let a silent gap read as full coverage.
3. Thresholds chosen and why (exact-match vs tolerance).
4. Connections/env vars the user still needs to configure, and any placeholder values.

## Notes

- `DATA_RECONCILIATION_MANUAL_QUERY` cannot join across the two systems — it runs one query
  per side, independently. Choose aggregates that would almost certainly change if the data
  actually drifted (counts, sums, min/max, distinct counts, a row checksum where the engine
  supports one) rather than expecting row-level set-difference semantics.
- `DATA_RECONCILIATION_CURSOR_FIELD`'s cache means a table's very first run scans everything;
  `cursor_field_cache_override` exists to seed a known-good starting point when that first
  scan would otherwise misreport a pre-existing backlog as new drift.
- Match `create-orchestra-pipeline`'s conventions for everything not specific to
  reconciliation: Git-backed vs Orchestra-backed handling, omitting empty `tags`, failure
  alerts, connection env-var references — this skill only covers what's different about the
  Data Reconciliation task types themselves.
