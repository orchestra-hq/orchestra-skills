---
name: databricks-cost-audit
description: >-
  Runs a daily, one-off Databricks cost-optimisation audit. Executes 10 checks
  against Databricks system tables (billing, compute, query history, lakeflow),
  writes ranked findings with estimated $ savings to a Delta table, and returns
  a summary highlighting what's new today vs. still-open. Use when the user asks
  to audit Databricks spend, find cost savings, run the daily cost check, or
  review compute/warehouse/storage waste. Triggers: "databricks cost audit",
  "check our databricks spend", "cost optimisation", "run the daily audit".
---

# Databricks Cost Audit

A scheduled (daily) cost-optimisation audit. It runs 10 checks against Databricks
**system tables**, accumulates findings in a Delta table so you can see trends,
and returns a dollar-ranked summary.

## Requirements

`databricks-sql-connector>=3.0.0` — the runner is `scripts/audit.py`, with check
definitions in `scripts/checks.py`.

## What it checks

| ID | Check | Signal |
|----|-------|--------|
| C01 | All-purpose compute running jobs | Interactive DBUs billed against a `job_id` (pay ~2x for job workloads) |
| C02 | Under-utilised clusters | Avg CPU below threshold over the lookback window |
| C03 | Risky cluster config | Auto-termination off/too long, or fixed oversized worker count |
| C04 | Photon review | High-cost non-Photon jobs (candidate) / paying Photon premium on light work |
| C05 | Expensive & repeated queries | Same query hash run many times, high total duration/bytes |
| C06 | Full-table scans | High `read_bytes` with `pruned_files = 0` → missing partitioning/clustering |
| C07 | SQL warehouse right-sizing | High cost but low busy-fraction → oversized or auto-stop too long |
| C08 | Storage sprawl | Managed tables not read in 90 days (candidate for archive/drop) |
| C09 | Job failures burning compute | Repeated failed runs that still billed compute |
| C10 | Instance / pricing leakage | On-demand where spot would do; join to cost for $ impact |

A bonus **C11 tag hygiene** check flags untagged spend (breaks attribution for
everything above). It is included in the script but off by default — enable via
`AUDIT_ENABLE_C11=1`.

## How to run it

1. **Confirm credentials are present** (env vars, see below). If missing, ask the
   user for them — do not guess.
2. Run the audit:
   ```bash
   python scripts/audit.py
   ```
   Useful flags: `--dry-run` (print SQL, run nothing), `--check C05` (single check),
   `--no-write` (compute + return findings but don't persist to the Delta table).
3. The script prints a JSON summary and a markdown report to stdout, and writes
   `report_<date>.md` in the skill directory.
4. **Present the result to the user**: lead with total estimated monthly saving and
   the count of findings that are **new today**, then the top ~10 findings by
   `est_monthly_saving_usd`. Note any checks that were skipped (usually a system
   table not enabled in that workspace) rather than silently dropping them.

## Configuration (environment variables)

Connection (required):
- `DATABRICKS_HOST` — e.g. `adb-1234.5.azuredatabricks.net` (no scheme)
- `DATABRICKS_HTTP_PATH` — SQL warehouse HTTP path, e.g. `/sql/1.0/warehouses/abc123`
- `DATABRICKS_TOKEN` — PAT or OAuth token with access to `system` catalog

Where to store findings (optional, sensible defaults):
- `AUDIT_CATALOG` (default `main`), `AUDIT_SCHEMA` (default `cost_audit`),
  `AUDIT_TABLE` (default `findings`)

Tuning (optional): `AUDIT_LOOKBACK_DAYS` (30), `AUDIT_MIN_COST_USD` (50),
`AUDIT_IDLE_CPU_PCT` (15), `AUDIT_MAX_AUTOTERM_MIN` (60), `AUDIT_BIG_WORKERS` (10),
`AUDIT_REPEAT_QUERY_RUNS` (20), `AUDIT_ENABLE_C11` (0).

## Running it daily

This is designed to be idempotent per day: it deletes any rows already written for
today's `run_date` before inserting, so a re-run replaces the day cleanly. Schedule
it with the `schedule` skill (a cloud routine) or as a Databricks job that shells out
to `scripts/audit.py`. The trend view (`<table>_summary`) computes `first_seen` /
`days_open` / `is_new` from the accumulated history — that's what powers "new today".

## Caveats

- System-table schemas differ slightly by cloud (AWS/Azure/GCP) and evolve over
  time; each check is wrapped so one failure never aborts the run. Skipped checks
  are reported. See `references/system-tables.md` for schema notes and enablement.
- Dollar figures are **estimates** from list prices and heuristic savings fractions —
  they rank opportunities, they are not a bill. Discounts/commitments aren't modelled.
