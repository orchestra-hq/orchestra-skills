# DQ tests on ClickHouse

Engine specifics: Orchestra integration `CLICKHOUSE`, job `CLICKHOUSE_RUN_TEST` (currently
**beta** — confirm it's enabled on the account). SQL is **ClickHouse SQL**: `now()`, `toYear()`,
`match(col,'re')`, `count()` (no `*`), `stddevPop()`, tables qualified as `database.table`.
Connection ref: `${{ ENV.CLICKHOUSE_CONNECTION }}`.

## 1. Profile the data first — never test blind

Take the user's tables (or pick the relevant ones) and **profile every candidate column** using
the ClickHouse credentials in the environment (HTTP/native client — typically `CLICKHOUSE_HOST`,
`CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE`; probe for the exact names).
Profiling tells you which tests are worth writing and what the thresholds should be.

Get structure, then profile:
```sql
-- structure
select name, type, position
from system.columns
where database = '<DB>' and table = '<TABLE>'
order by position;

-- per-column profile (adapt per type)
select
  count()                                       as rows,
  count(<col>)                                  as non_null,
  count() - count(<col>)                        as nulls,
  round(100.0*(count()-count(<col>))/nullif(count(),0),1) as null_pct,
  uniqExact(<col>)                              as distinct_vals,
  min(<col>) as min_val, max(<col>) as max_val
from <DB>.<TABLE>;
```
For timestamps also count `<col> > now()` (future) and `toYear(<col>) < 2000`. For strings,
profile `length(<col>)`, blanks, and `select distinct <col> ... limit 50` to eyeball junk. For
numerics, get `avg`, `stddevPop`, quantiles. Note ClickHouse uses `Nullable(T)` — a non-`Nullable`
column can't hold NULLs, so null tests only matter on `Nullable` columns.

**Classify each column** into a semantic type (id, foreign key, timestamp, measure,
category/enum, free text, email/format, boolean, percent, geo, …). The semantic type — not just
the data type — drives which tests you write.

Record findings: for each column, its semantic type, what looks healthy, and **what looks
broken** (these become failing tests).

## 2. Test catalogue — choose tests by what the column *is*

Each test is a SQL `SELECT` that **returns the violating rows**; Orchestra counts those rows and
compares to the thresholds. Write the query so a non-empty result means "this is wrong."

| Column kind | Tests to write | Violating-row SQL (ClickHouse) |
|---|---|---|
| **Primary key / id** | not null; unique | `where id is null` · `select id from t group by id having count() > 1` |
| **Foreign key** | referential integrity; not null if mandatory | `select c.fk from child c left anti join parent p on c.fk = p.id where c.fk is not null` |
| **Timestamp / date** | not null (if expected); **not in the future**; not absurdly old; freshness; ordering | `where ts > now()` · `where toYear(ts) < 2000` · `where created_at > updated_at` · freshness: `having max(ts) < now() - interval <lag> hour` |
| **Numeric measure** | non-negative where it must be; plausible range; outliers | `where amount < 0` · `where x not between <lo> and <hi>` · outliers: `where abs(x - (select avg(x) from t)) > 3*(select stddevPop(x) from t)` |
| **Category / status / enum** | values within the allowed set | `where status not in ('NEW','OPEN','CLOSED')` · `where status is null` |
| **Free text / string** | not blank; length bounds; placeholder junk; stray whitespace | `where empty(trimBoth(col))` · `where length(col) > <max>` · `where lower(col) in ('n/a','na','null','none','test','-','unknown')` · `where col != trimBoth(col)` |
| **Email / code / UUID** | format via regex | `where not match(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')` |
| **Boolean (UInt8 0/1)** | only 0/1 | `where bool_col not in (0,1)` |
| **Percent / ratio** | within 0–100 (or 0–1) | `where pct not between 0 and 100` |
| **Geo lat/lon** | bounds | `where lat not between -90 and 90 or lon not between -180 and 180` |
| **Volume / whole table** | row count > 0 | `select 1 having (select count() from t) = 0` |
| **Cross-column consistency** | logical relationships hold | `where end_date < start_date` · `where total != line1 + line2` |
| **Composite natural key** | unique together | `select k1,k2 from t group by k1,k2 having count() > 1` |

Rules of thumb: keys → not-null + unique; money/quantities → sign + range; anything time →
future-date + freshness; enums → accepted-values; free text → blank + junk; API-ingested → format
+ volume. Prefer a few **meaningful** tests per column over a blanket null check — and test for
what your profile above actually showed.

## 3. Write the pipeline YAML

See `workflow.md` for the matrix/gating pattern this YAML follows.

```yaml
version: v1
name: 'ClickHouse Data Quality Tests #clickhouse #dataquality'
pipeline:
  timestamp_tests:
    tasks:
      check_timestamp_future:
        integration: CLICKHOUSE
        integration_job: CLICKHOUSE_RUN_TEST
        parameters:
          statement: 'select * from ${{ MATRIX.dq_inputs[''database''] }}.${{ MATRIX.dq_inputs[''table''] }}
            where ${{ MATRIX.dq_inputs[''column''] }} > now() limit 100'
          error_threshold_expression: '> 0'     # any future timestamp is a real defect → FAIL
          warn_threshold_expression: '> 0'
          database: ${{ MATRIX.dq_inputs['database'] }}
        depends_on: []
        name: Timestamp Not In Future
        connection: ${{ ENV.CLICKHOUSE_CONNECTION }}
    depends_on:
    - airbyte-loads                              # the upstream load task group
    condition: ${{ task_groups['airbyte-loads'].all().status == 'COMPLETED' }}
    name: Timestamp Tests
    matrix:
      inputs:
        dq_inputs:
        - { database: default, table: orders, column: ordered_at }
        - { database: default, table: events, column: created_at }
  key_tests:
    tasks:
      check_pk_unique:
        integration: CLICKHOUSE
        integration_job: CLICKHOUSE_RUN_TEST
        parameters:
          statement: 'select ${{ MATRIX.dq_inputs[''column''] }} from ${{ MATRIX.dq_inputs[''database''] }}.${{ MATRIX.dq_inputs[''table''] }}
            group by ${{ MATRIX.dq_inputs[''column''] }} having count() > 1 limit 100'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
          database: ${{ MATRIX.dq_inputs['database'] }}
        depends_on: []
        name: Primary Key Unique
        connection: ${{ ENV.CLICKHOUSE_CONNECTION }}
    depends_on:
    - timestamp_tests
    condition: ${{ task_groups['timestamp_tests'].all().status == 'COMPLETED' }}
    name: Key Tests
    matrix:
      inputs:
        dq_inputs:
        - { database: default, table: orders, column: order_id }
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
Add one task group per test kind you selected in §2, each fanned out over its relevant targets
via the matrix, each gated with the `condition`. Connections must use
`${{ ENV.CLICKHOUSE_CONNECTION }}` — never hardcode credentials. Probe env var names if unsure:
```powershell
[Environment]::GetEnvironmentVariables('User').Keys | Where-Object { $_ -match 'clickhouse|CLICKHOUSE' }
```

## 4. Interpreting results — ClickHouse specifics

- Qualified name for reporting: `database.table.column`.
- Common pipeline-error causes (not data findings): SQL syntax error, wrong column/table name,
  bad connection, or `CLICKHOUSE_RUN_TEST` not enabled (beta). Check names against
  `system.columns`, matrix quoting, or `${{ ENV.CLICKHOUSE_CONNECTION }}` not set.
