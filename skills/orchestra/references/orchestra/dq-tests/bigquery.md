# DQ tests on BigQuery

Engine specifics: Orchestra integration `GCP_BIG_QUERY`, job `GCP_BQ_RUN_TEST`. The SQL parameter
is **`query`** (not `statement`), and the job also takes `enable_drive_scope` (required) and
`location` (optional region, e.g. `US`/`EU`/`europe-west2`). SQL is **GoogleSQL (standard SQL)**:
`current_timestamp()`, `extract(year from col)`, `regexp_contains(col, r'…')`,
`stddev()`/`stddev_pop()`, `count(*)`, `safe_divide(a,b)`. Tables are qualified
`` `project.dataset.table` `` (backticks; the project may be omitted to use the connection
default). Connection ref: `${{ ENV.GCP_BIG_QUERY_CONNECTION }}`.

## 1. Profile the data first — never test blind

Take the user's tables (or pick the relevant ones) and **profile every candidate column** using
the BigQuery credentials in the environment (service-account JSON — typically
`GOOGLE_APPLICATION_CREDENTIALS` or `GCP_SERVICE_ACCOUNT_JSON`, plus a default
`GCP_PROJECT`/`location`; probe for the exact names). Use the `bq` CLI or the
`google-cloud-bigquery` Python client. Profiling tells you which tests are worth writing and what
the thresholds should be.

Get structure, then profile:
```sql
-- structure
select column_name, data_type, is_nullable
from `<PROJECT>.<DATASET>`.INFORMATION_SCHEMA.COLUMNS
where table_name = '<TABLE>'
order by ordinal_position;

-- per-column profile (adapt per type)
select
  count(*)                                              as rows,
  count(<col>)                                          as non_null,
  count(*) - count(<col>)                              as nulls,
  round(100.0*(count(*)-count(<col>))/nullif(count(*),0),1) as null_pct,
  count(distinct <col>)                               as distinct_vals,
  min(<col>) as min_val, max(<col>) as max_val
from `<PROJECT>.<DATASET>.<TABLE>`;
```
For timestamps also count `<col> > current_timestamp()` (future) and
`extract(year from <col>) < 2000`. For strings, profile `length(<col>)`, blanks, and
`select distinct <col> … limit 50` to eyeball junk values. For numerics, get `avg`, `stddev`, and
`approx_quantiles(<col>, 100)`.

**Classify each column** into a semantic type (id, foreign key, timestamp, measure,
category/enum, free text, email/format, boolean, percent, geo, …). The semantic type — not just
the SQL data type — drives which tests you write. A `STRING` holding a status code and a `STRING`
holding a free-text note need completely different tests.

Record findings: for each column, its semantic type, what looks healthy, and **what looks
broken** (these become failing tests).

## 2. Test catalogue — choose tests by what the column *is*

Each test is a SQL `SELECT` that **returns the violating rows**; Orchestra counts those rows and
compares to the thresholds. Write the query so a non-empty result means "this is wrong."

| Column kind | Tests to write | Violating-row SQL (GoogleSQL) |
|---|---|---|
| **Primary key / surrogate id** | not null; unique | `where id is null` · `select id from t group by id having count(*) > 1` |
| **Foreign key** | referential integrity; not null if mandatory | `select c.fk from child c left join parent p on c.fk=p.id where c.fk is not null and p.id is null` |
| **Timestamp / date** | not null (if expected); **not in the future**; not absurdly old; freshness; ordering | `where ts > current_timestamp()` · `where extract(year from ts) < 2000` · `where created_at > updated_at` · freshness: `having max(ts) < timestamp_sub(current_timestamp(), interval <lag> hour)` |
| **Numeric measure** (amount, qty, count) | non-negative where it must be; plausible range; outliers | `where amount < 0` · `where x not between <lo> and <hi>` · outliers: `where abs(x-(select avg(x) from t)) > 3*(select stddev(x) from t)` |
| **Category / status / enum** | values within the allowed set; cardinality sane | `where status not in ('NEW','OPEN','CLOSED')` · `where status is null` |
| **Free text / string** | not blank; length bounds; placeholder junk; stray whitespace | `where coalesce(trim(col),'')=''` · `where length(col) > <max>` · `where lower(col) in ('n/a','na','null','none','test','-','unknown')` · `where col <> trim(col)` |
| **Email / phone / code / UUID** | format via regex | `where not regexp_contains(email, r'^[^@\s]+@[^@\s]+\.[^@\s]+$')` |
| **Boolean** | only true/false/null | `where bool_col is not null and bool_col not in (true,false)` |
| **Percent / ratio** | within 0–100 (or 0–1) | `where pct not between 0 and 100` |
| **Geo lat/lon** | bounds | `where lat not between -90 and 90 or lon not between -180 and 180` |
| **Volume / whole table** | row count > 0; not a sudden drop vs history | `select 1 having (select count(*) from t) = 0` |
| **Cross-column consistency** | logical relationships hold | `where end_date < start_date` · `where total <> line1 + line2` |
| **Composite natural key** | unique together | `select k1,k2 from t group by k1,k2 having count(*) > 1` |

Rules of thumb:
- **Keys** → always not-null + unique. **Money/quantities** → sign + range. **Anything time** →
  future-date + freshness. **Enums** → accepted-values. **Free text** → blank + junk. **Anything
  ingested from an API** → format + volume.
- Prefer a few **meaningful** tests per column over a blanket null check on all of them.
- Don't only test for the obvious — test for what your profile above actually showed.

## 3. Write the pipeline YAML

See `workflow.md` for the matrix/gating pattern this YAML follows.

```yaml
version: v1
name: 'BigQuery Data Quality Tests #bigquery #dataquality'
pipeline:
  timestamp_tests:
    tasks:
      check_timestamp_future:
        integration: GCP_BIG_QUERY
        integration_job: GCP_BQ_RUN_TEST
        parameters:
          query: 'select * from `<PROJECT>.${{ MATRIX.dq_inputs[''dataset''] }}.${{ MATRIX.dq_inputs[''table''] }}`
            where ${{ MATRIX.dq_inputs[''column''] }} > current_timestamp() limit 100'
          enable_drive_scope: false
          location: '<LOCATION>'                 # e.g. US, EU, europe-west2
          error_threshold_expression: '> 0'      # any future timestamp is a real defect → FAIL
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Timestamp Not In Future
        connection: ${{ ENV.GCP_BIG_QUERY_CONNECTION }}
    depends_on:
    - airbyte-loads                              # the upstream load task group
    condition: ${{ task_groups['airbyte-loads'].all().status == 'COMPLETED' }}
    name: Timestamp Tests
    matrix:
      inputs:
        dq_inputs:
        - { dataset: analytics, table: issues, column: created_at }
        - { dataset: analytics, table: orders, column: ordered_at }
  key_tests:
    tasks:
      check_pk_unique:
        integration: GCP_BIG_QUERY
        integration_job: GCP_BQ_RUN_TEST
        parameters:
          query: 'select ${{ MATRIX.dq_inputs[''column''] }} from `<PROJECT>.${{ MATRIX.dq_inputs[''dataset''] }}.${{ MATRIX.dq_inputs[''table''] }}`
            group by ${{ MATRIX.dq_inputs[''column''] }} having count(*) > 1 limit 100'
          enable_drive_scope: false
          location: '<LOCATION>'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Primary Key Unique
        connection: ${{ ENV.GCP_BIG_QUERY_CONNECTION }}
    depends_on:
    - timestamp_tests
    condition: ${{ task_groups['timestamp_tests'].all().status == 'COMPLETED' }}
    name: Key Tests
    matrix:
      inputs:
        dq_inputs:
        - { dataset: analytics, table: orders, column: order_id }
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
Add one task group per test kind you selected in §2 (numeric range, accepted-values, freshness,
junk-string, format-regex, …), each fanned out over its relevant targets via the matrix, each
gated with the `condition`. Connections must use `${{ ENV.GCP_BIG_QUERY_CONNECTION }}` — never
hardcode credentials. Probe env var names if unsure:
```powershell
[Environment]::GetEnvironmentVariables('User').Keys | Where-Object { $_ -match 'gcp|bigquery|google|GCP_BIG_QUERY' }
```

## 4. Interpreting results — BigQuery specifics

- Qualified name for reporting: `project.dataset.table.column`.
- Common pipeline-error causes (not data findings): SQL syntax error, wrong column/table name,
  bad location, or bad connection. Check names against `INFORMATION_SCHEMA.COLUMNS`, confirm
  backticks around `` `project.dataset.table` ``, confirm `location`, matrix quoting, or
  `${{ ENV.GCP_BIG_QUERY_CONNECTION }}` not set.
