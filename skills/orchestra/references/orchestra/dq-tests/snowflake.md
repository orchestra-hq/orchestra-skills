# DQ tests on Snowflake

Engine specifics: Orchestra integration `SNOWFLAKE`, job `SNOWFLAKE_RUN_TEST`. The SQL parameter
is `statement`. SQL is standard Snowflake SQL: `current_timestamp()`, `year(col)`,
`regexp_like(col, '…')`, `stddev()`, `count(*)`. Tables are qualified `<DB>.<SCHEMA>.<TABLE>`.
Connection ref: `${{ ENV.SNOWFLAKE_CONNECTION }}`.

## 1. Profile the data first — never test blind

Take the user's tables (or pick the relevant ones) and **profile every candidate column** using
the Snowflake credentials in the environment. Profiling tells you which tests are worth writing
and what the thresholds should be.

Get structure, then profile:
```sql
-- structure
select table_name, column_name, data_type, is_nullable
from <DB>.INFORMATION_SCHEMA.COLUMNS
where table_schema = '<SCHEMA>' and table_name = '<TABLE>'
order by ordinal_position;

-- per-column profile (adapt per type)
select
  count(*)                                   as rows,
  count(<col>)                               as non_null,
  count(*) - count(<col>)                    as nulls,
  round(100.0*(count(*)-count(<col>))/nullif(count(*),0),1) as null_pct,
  count(distinct <col>)                      as distinct_vals,
  min(<col>) as min_val, max(<col>) as max_val
from <DB>.<SCHEMA>.<TABLE>;
```
For timestamps also count `<col> > current_timestamp()` (future) and `year(<col>) < 2000`. For
strings, profile `length`, blanks, and a `select distinct <col> ... limit 50` to eyeball junk
values. For numerics, get `avg`, `stddev`, and percentiles.

**Classify each column** into a semantic type (id, foreign key, timestamp, measure,
category/enum, free text, email/format, boolean, percent, geo, …). The semantic type — not just
the SQL data type — drives which tests you write. A `VARCHAR` holding a status code and a
`VARCHAR` holding a free-text note need completely different tests.

Record findings: for each column, its semantic type, what looks healthy, and **what looks
broken** (these become failing tests).

## 2. Test catalogue — choose tests by what the column *is*

Each test is a SQL `SELECT` that **returns the violating rows**; Orchestra counts those rows and
compares to the thresholds. Write the query so a non-empty result means "this is wrong."

| Column kind | Tests to write | Violating-row SQL (returns bad rows) |
|---|---|---|
| **Primary key / surrogate id** | not null; unique | `where id is null` · `select id from t group by id having count(*) > 1` |
| **Foreign key** | referential integrity; not null if mandatory | `select c.fk from child c left join parent p on c.fk=p.id where c.fk is not null and p.id is null` |
| **Timestamp / date** | not null (if expected); **not in the future**; not absurdly old; freshness; ordering | `where ts > current_timestamp()` · `where year(ts) < 2000` · `where created_at > updated_at` · freshness: `having max(ts) < dateadd('hour',-<lag>,current_timestamp())` |
| **Numeric measure** (amount, qty, count) | non-negative where it must be; plausible range; outliers | `where amount < 0` · `where x not between <lo> and <hi>` · outliers: `where abs(x-(select avg(x) from t)) > 3*(select stddev(x) from t)` |
| **Category / status / enum** | values within the allowed set; cardinality sane | `where status not in ('NEW','OPEN','CLOSED')` · `where status is null` |
| **Free text / string** | not blank; length bounds; placeholder junk; stray whitespace | `where coalesce(trim(col),'')=''` · `where length(col) > <max>` · `where lower(col) in ('n/a','na','null','none','test','-','unknown')` · `where col <> trim(col)` |
| **Email / phone / code / UUID** | format via regex | `where not regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')` |
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
name: 'Snowflake Data Quality Tests #snowflake #dataquality'
pipeline:
  timestamp_tests:
    tasks:
      check_timestamp_future:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        parameters:
          statement: 'select * from <DB>.${{ MATRIX.dq_inputs[''schema''] }}.${{ MATRIX.dq_inputs[''table''] }}
            where ${{ MATRIX.dq_inputs[''column''] }} > current_timestamp() limit 100'
          error_threshold_expression: '> 0'     # any future timestamp is a real defect → FAIL
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Timestamp Not In Future
        connection: ${{ ENV.SNOWFLAKE_CONNECTION }}
    depends_on:
    - airbyte-loads                              # the upstream load task group
    condition: ${{ task_groups['airbyte-loads'].all().status == 'COMPLETED' }}
    name: Timestamp Tests
    matrix:
      inputs:
        dq_inputs:
        - { schema: PUBLIC, table: ISSUES, column: CREATED_AT }
        - { schema: PUBLIC, table: ORDERS, column: ORDERED_AT }
  key_tests:
    tasks:
      check_pk_unique:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        parameters:
          statement: 'select ${{ MATRIX.dq_inputs[''column''] }} from <DB>.${{ MATRIX.dq_inputs[''schema''] }}.${{ MATRIX.dq_inputs[''table''] }}
            group by ${{ MATRIX.dq_inputs[''column''] }} having count(*) > 1 limit 100'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Primary Key Unique
        connection: ${{ ENV.SNOWFLAKE_CONNECTION }}
    depends_on:
    - timestamp_tests
    condition: ${{ task_groups['timestamp_tests'].all().status == 'COMPLETED' }}
    name: Key Tests
    matrix:
      inputs:
        dq_inputs:
        - { schema: PUBLIC, table: ORDERS, column: ORDER_ID }
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
gated with the `condition`.

Connections must use `${{ ENV.SNOWFLAKE_CONNECTION }}` — never hardcode credentials. Probe env
var names if unsure:
```powershell
[Environment]::GetEnvironmentVariables('User').Keys | Where-Object { $_ -match 'snowflake|SNOWFLAKE' }
```

## 4. Interpreting results — Snowflake specifics

- Qualified name for reporting: `<db>.<schema>.<table>.<column>`.
- Common pipeline-error causes (not data findings): column/table name typo (check against
  `INFORMATION_SCHEMA`), matrix quoting, or `${{ ENV.SNOWFLAKE_CONNECTION }}` not set.
