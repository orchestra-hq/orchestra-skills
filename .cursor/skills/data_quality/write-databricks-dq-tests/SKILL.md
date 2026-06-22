---
name: write-databricks-dq-tests
description: Profile Databricks data, design data-quality tests appropriate to what each column actually is, then build and deploy a Databricks DQ testing pipeline to Orchestra.
---

Goal: inspect real Databricks data, **design tests that fit what each column means** (not a generic null check on everything), deploy them as an Orchestra pipeline, run it, and report what's actually wrong. A test that **fails** because the data is bad is the skill working correctly — do **not** tune thresholds until everything is green.

Flow: **profile → design tests → write pipeline YAML → branch (or create pipeline if no git) → register → run → report.**

> Engine specifics: Orchestra integration `DATABRICKS`, job `DATABRICKS_RUN_TEST`. The test runs against a **SQL warehouse**, so every test task needs a `warehouse_id` parameter alongside `statement` and the thresholds. SQL is **Databricks SQL (Spark SQL)**: `current_timestamp()`, `year(col)`, `col rlike '…'`, `stddev()`, `count(*)`, tables are qualified `catalog.schema.table` (Unity Catalog; `hive_metastore.schema.table` for legacy). Connection ref: `${{ ENV.DATABRICKS_CONNECTION }}`.

---

# 1. Profile the data first — never test blind

Take the user's tables (or pick the relevant ones) and **profile every candidate column** using the Databricks credentials in the environment (SQL warehouse — typically `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`, optionally `DATABRICKS_CATALOG`/`DATABRICKS_SCHEMA`; probe for the exact names). Use the `databricks-sql-connector` Python client (or the Databricks SQL CLI). Profiling tells you which tests are worth writing and what the thresholds should be.

Get structure, then profile:
```sql
-- structure (Unity Catalog)
select column_name, data_type, is_nullable
from <CATALOG>.information_schema.columns
where table_schema = '<SCHEMA>' and table_name = '<TABLE>'
order by ordinal_position;
-- or: describe table <CATALOG>.<SCHEMA>.<TABLE>;

-- per-column profile (adapt per type)
select
  count(*)                                              as rows,
  count(<col>)                                          as non_null,
  count(*) - count(<col>)                              as nulls,
  round(100.0*(count(*)-count(<col>))/nullif(count(*),0),1) as null_pct,
  count(distinct <col>)                               as distinct_vals,
  min(<col>) as min_val, max(<col>) as max_val
from <CATALOG>.<SCHEMA>.<TABLE>;
```
For timestamps also count `<col> > current_timestamp()` (future) and `year(<col>) < 2000`. For strings, profile `length(<col>)`, blanks, and `select distinct <col> … limit 50` to eyeball junk values. For numerics, get `avg`, `stddev`, and `percentile(<col>, array(0.01,0.5,0.99))`.

**Classify each column** into a semantic type (id, foreign key, timestamp, measure, category/enum, free text, email/format, boolean, percent, geo, …). The semantic type — not just the SQL data type — drives which tests you write. A `STRING` holding a status code and a `STRING` holding a free-text note need completely different tests.

Record findings: for each column, its semantic type, what looks healthy, and **what looks broken** (these become failing tests).

---

# 2. Test catalogue — choose tests by what the column *is*

Each test is a SQL `SELECT` that **returns the violating rows**; Orchestra counts those rows and compares to the thresholds (§3). Write the query so a non-empty result means "this is wrong."

| Column kind | Tests to write | Violating-row SQL (Databricks SQL) |
|---|---|---|
| **Primary key / surrogate id** | not null; unique | `where id is null` · `select id from t group by id having count(*) > 1` |
| **Foreign key** | referential integrity; not null if mandatory | `select c.fk from child c left anti join parent p on c.fk=p.id where c.fk is not null` |
| **Timestamp / date** | not null (if expected); **not in the future**; not absurdly old; freshness; ordering | `where ts > current_timestamp()` · `where year(ts) < 2000` · `where created_at > updated_at` · freshness: `having max(ts) < current_timestamp() - interval <lag> hours` |
| **Numeric measure** (amount, qty, count) | non-negative where it must be; plausible range; outliers | `where amount < 0` · `where x not between <lo> and <hi>` · outliers: `where abs(x-(select avg(x) from t)) > 3*(select stddev(x) from t)` |
| **Category / status / enum** | values within the allowed set; cardinality sane | `where status not in ('NEW','OPEN','CLOSED')` · `where status is null` |
| **Free text / string** | not blank; length bounds; placeholder junk; stray whitespace | `where coalesce(trim(col),'')=''` · `where length(col) > <max>` · `where lower(col) in ('n/a','na','null','none','test','-','unknown')` · `where col <> trim(col)` |
| **Email / phone / code / UUID** | format via regex | `where not (email rlike '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')` |
| **Boolean** | only true/false/null | `where bool_col is not null and bool_col not in (true,false)` |
| **Percent / ratio** | within 0–100 (or 0–1) | `where pct not between 0 and 100` |
| **Geo lat/lon** | bounds | `where lat not between -90 and 90 or lon not between -180 and 180` |
| **Volume / whole table** | row count > 0; not a sudden drop vs history | `select 1 having (select count(*) from t) = 0` |
| **Cross-column consistency** | logical relationships hold | `where end_date < start_date` · `where total <> line1 + line2` |
| **Composite natural key** | unique together | `select k1,k2 from t group by k1,k2 having count(*) > 1` |

Rules of thumb:
- **Keys** → always not-null + unique. **Money/quantities** → sign + range. **Anything time** → future-date + freshness. **Enums** → accepted-values. **Free text** → blank + junk. **Anything ingested from an API** → format + volume.
- Prefer a few **meaningful** tests per column over a blanket null check on all of them.
- Don't only test for the obvious — test for what your profile in §1 actually showed.

---

# 3. Thresholds — and why tests are *meant* to fail sometimes

Tests run via `DATABRICKS_RUN_TEST`. The `statement` returns violating rows; Orchestra compares the **row count** to:
- `error_threshold_expression` — if met, task is **FAILED**.
- `warn_threshold_expression` — if met (but not error), task is **WARNING**.
- Zero rows → success. Error takes precedence over warn.

So `error_threshold_expression: '> 0'` means "fail if there is even one bad row." For tolerated noise, raise the error bar and warn earlier, e.g. `warn '> 0'`, `error '> 100'`.

**The point of this skill is to catch bad data, not to produce a green pipeline.** If profiling shows, say, a timestamp column that's ~70% valid dates with some values in the future, you write the future-date test with `error '> 0'` so it **fails** and surfaces the problem — you do **not** widen the year bounds or set the threshold to swallow the future dates. A failing test here is the correct, desired outcome. When you report, call these out as real data issues (see §7), don't hide them.

Set thresholds from the profile: if a column is genuinely allowed some nulls, set the error threshold to the count you'd consider unacceptable; if zero nulls are acceptable, use `> 0`.

---

# 4. Write the pipeline YAML

Use a `matrix` so one task definition fans out over many table/column targets, and group tests by kind (one task group per test type). Put failure alerts on the pipeline. Each task needs a `warehouse_id` — keep it constant across a group, or push it into the matrix if different tables live on different warehouses.

**Every test task group must be gated on the upstream load completing** so the tests actually run. Set `depends_on` to the load group and add a `condition` that runs the group once the loads have **completed** — including when a load *failed*, because that's exactly when you most want DQ to run and catch the damage. Use the "run on any status" trigger plus:
```yaml
condition: ${{ task_groups['airbyte-loads'].all().status == 'COMPLETED' }}
```
(Apply the same pattern when one test group depends on another — reference the upstream group it waits on. In a standalone, schedule-triggered DQ pipeline with no upstream loads, the first group has no `depends_on`/`condition`; downstream test groups still chain with the condition.)

```yaml
version: v1
name: 'Databricks Data Quality Tests #databricks #dataquality'
pipeline:
  timestamp_tests:
    tasks:
      check_timestamp_future:
        integration: DATABRICKS
        integration_job: DATABRICKS_RUN_TEST
        parameters:
          warehouse_id: ${{ ENV.DATABRICKS_WAREHOUSE_ID }}
          statement: 'select * from <CATALOG>.${{ MATRIX.dq_inputs[''schema''] }}.${{ MATRIX.dq_inputs[''table''] }}
            where ${{ MATRIX.dq_inputs[''column''] }} > current_timestamp() limit 100'
          error_threshold_expression: '> 0'      # any future timestamp is a real defect → FAIL
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Timestamp Not In Future
        connection: ${{ ENV.DATABRICKS_CONNECTION }}
    depends_on:
    - airbyte-loads                              # the upstream load task group
    condition: ${{ task_groups['airbyte-loads'].all().status == 'COMPLETED' }}
    name: Timestamp Tests
    matrix:
      inputs:
        dq_inputs:
        - { schema: analytics, table: issues, column: created_at }
        - { schema: analytics, table: orders, column: ordered_at }
  key_tests:
    tasks:
      check_pk_unique:
        integration: DATABRICKS
        integration_job: DATABRICKS_RUN_TEST
        parameters:
          warehouse_id: ${{ ENV.DATABRICKS_WAREHOUSE_ID }}
          statement: 'select ${{ MATRIX.dq_inputs[''column''] }} from <CATALOG>.${{ MATRIX.dq_inputs[''schema''] }}.${{ MATRIX.dq_inputs[''table''] }}
            group by ${{ MATRIX.dq_inputs[''column''] }} having count(*) > 1 limit 100'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Primary Key Unique
        connection: ${{ ENV.DATABRICKS_CONNECTION }}
    depends_on:
    - timestamp_tests
    condition: ${{ task_groups['timestamp_tests'].all().status == 'COMPLETED' }}
    name: Key Tests
    matrix:
      inputs:
        dq_inputs:
        - { schema: analytics, table: orders, column: order_id }
schedule:
- name: Daily at 8am
  cron: 0 8 ? * MON-FRI *
  timezone: Europe/London
webhook:
  enabled: false
alerts:
- name: Failures
  statuses: [FAILED, WARNING]
  destinations:
  - integration: SLACK
    destination: alert-testing
```
Add one task group per test kind you selected in §2 (numeric range, accepted-values, freshness, junk-string, format-regex, …), each fanned out over its relevant targets via the matrix, each gated with the `condition`. Connections must use `${{ ENV.DATABRICKS_CONNECTION }}` and the warehouse id should come from an env var (e.g. `${{ ENV.DATABRICKS_WAREHOUSE_ID }}`) — never hardcode credentials or ids. Probe env var names if unsure:
```powershell
[Environment]::GetEnvironmentVariables('User').Keys | Where-Object { $_ -match 'databricks|DATABRICKS' }
```

---

# 5. Branch the repo (or create the pipeline if there's no git)

If the Orchestra pipelines are git-backed: create a new feature branch and commit the YAML under `orchestra/<name>.yml`. If the account is **not** git-backed, recommend connecting git first; otherwise create the pipeline directly in Orchestra (Orchestra-backed) so the user still has something runnable, and note it should be moved to git.

---

# 6. Register the pipeline with Orchestra

Commit and push the branch, then register via the Orchestra MCP:
```
mcp__orchestramcp__import_pipeline(yaml="<contents of orchestra/<name>.yml>")
```
This returns the pipeline UUID — save it. If the alias already exists, this updates it in place. Validate first with `validate_pipeline` if available.

---

# 7. Trigger on the branch, poll, and report honestly

```
mcp__orchestramcp__start_pipeline(alias="<pipeline-uuid>", branch="<feature-branch>")
mcp__orchestramcp__get_pipeline_run_status(pipeline_run_id="<run-uuid>")
```
Poll until the status is terminal (not `RUNNING`/`CREATED`). Surface the UI link: `https://app.getorchestra.io/pipeline-runs/<run-uuid>/lineage`.

**Interpreting results — a failed test is often the right answer:**
- **Test FAILED / WARNING** → the data has the problem you tested for. This is a *finding*, not a pipeline bug. Pull the failing task's offending rows (`download_task_run_log` / re-run the SELECT) and report the issue: which `catalog.schema.table.column`, how many bad rows, example values. Do **not** loosen the threshold to make it pass.
- **Pipeline error (not a test result)** — e.g. SQL syntax error, wrong column/table name, missing/invalid `warehouse_id`, insufficient Unity Catalog privileges, or bad connection → that *is* yours to fix. Correct the YAML/SQL and re-trigger. Common causes: column/table name typo (check against `information_schema.columns` or `describe table`), wrong/stopped warehouse id, matrix quoting, or `${{ ENV.DATABRICKS_CONNECTION }}` not set.
- **All green** → either the data is clean or your tests are too lax. Sanity-check against the §1 profile; if you saw issues there, your tests should have caught them.

Final report: the pipeline link, the tests deployed (by table/column/kind), and a clear list of **data-quality findings** (the failing/warning tests) with counts and examples, separated from any pipeline fixes you applied.
