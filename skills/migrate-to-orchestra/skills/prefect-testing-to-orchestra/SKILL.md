---
name: prefect-testing-to-orchestra
description: "Use this skill when a Prefect flow contains data quality or testing logic: @task functions that run SQL assertions, Great Expectations checkpoints called from a @task, Soda check tasks, or threshold checks that raise exceptions on failure. Triggers: any Prefect @task that queries a database to validate data, any use of great-expectations or soda-core inside a Prefect flow, any task that checks row counts, null counts, or data bounds."
---

## Overview

Prefect data quality tests are typically `@task` functions that query a database and assert on the result, raising exceptions on failure. Orchestra provides native test integration jobs (`*_RUN_TEST`) that run SQL and evaluate threshold expressions. The critical difference: **Prefect tests PASS when the assertion is TRUE; Orchestra `*_RUN_TEST` FAILS when the SQL result MATCHES the threshold expression.** Always invert the condition.

Great Expectations and Soda have no native Orchestra integration jobs — wrap them in `PYTHON_EXECUTE_SCRIPT` tasks.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `@task` running SQL check via SnowflakeConnector | `integration_job: SNOWFLAKE_RUN_TEST` | invert assertion |
| `@task` running BigQuery check | `integration_job: GCP_BQ_RUN_TEST` | invert assertion |
| `@task` running Postgres check | `integration_job: POSTGRES_RUN_TEST` | invert assertion |
| `@task` running Databricks SQL check | `integration_job: DATABRICKS_RUN_TEST` | invert assertion |
| `@task` running SQL Server check | `integration_job: SQL_SERVER_RUN_QUERY` | for testing via SQL Server |
| `assert count == 0` (nulls check) | `error_threshold_expression: '> 0'` | inverted: fail when count IS > 0 |
| `assert count >= 1000` (min rows) | `error_threshold_expression: '< 1000'` | inverted: fail when count IS < 1000 |
| `raise ValueError(...)` on failure | `error_threshold_expression` matching failing condition | |
| `log.warning(...)` soft failure | `treat_failure_as_warning: true` | pipeline continues with WARNING status |
| Snowflake schema/column type check | `integration_job: SNOWFLAKE_SCHEMA_VALIDATION` | no SQL needed |
| Great Expectations checkpoint | `integration_job: PYTHON_EXECUTE_SCRIPT` | no native GE integration |
| Soda checks | `integration_job: PYTHON_EXECUTE_SCRIPT` | no native Soda integration |

Valid test integration_jobs: `SNOWFLAKE_RUN_TEST`, `GCP_BQ_RUN_TEST`, `POSTGRES_RUN_TEST`, `DATABRICKS_RUN_TEST`, `SQL_SERVER_RUN_QUERY`

**Semantic inversion rule:**

| Prefect assertion | Orchestra threshold expression |
|---|---|
| `assert count == 0` | `error_threshold_expression: '> 0'` |
| `assert count >= 1000` | `error_threshold_expression: '< 1000'` |
| `assert count < 100` | `error_threshold_expression: '>= 100'` |
| `assert value is not None` | `error_threshold_expression: '= 0'` (count nulls) |
| `if count < 1000: raise` | `error_threshold_expression: '< 1000'` |

## Orchestra YAML Structure

```yaml
<task-key>:
  integration: SNOWFLAKE          # or GCP_BIG_QUERY, POSTGRES, DATABRICKS, SQL_SERVER
  integration_job: SNOWFLAKE_RUN_TEST
  name: <human-readable name>
  connection: <connection_name>
  parameters:
    statement: '<SQL that returns a single number>'
    error_threshold_expression: '<Python comparison operator> <value>'
    warn_threshold_expression: '<Python comparison operator> <value>'   # optional soft failure
  treat_failure_as_warning: false   # set true for soft/warning-only failures
  depends_on: []
```

## Conversion Steps

- [ ] Find every `@task` that queries a DB and asserts or raises based on the result
- [ ] Identify the database type → map to the correct `*_RUN_TEST` integration_job
- [ ] Extract the SQL query — it must return a single numeric value
- [ ] Invert the Prefect assertion → `error_threshold_expression` (see table above)
- [ ] If Prefect uses `log.warning` (soft failure): set `treat_failure_as_warning: true`
- [ ] If multiple thresholds (warn + error): set both `warn_threshold_expression` and `error_threshold_expression`
- [ ] For Great Expectations: replace checkpoint call with `PYTHON_EXECUTE_SCRIPT` task running `great_expectations checkpoint run <name>`
- [ ] For Soda: replace `scan.execute()` with `PYTHON_EXECUTE_SCRIPT` task running `soda scan`
- [ ] For Snowflake schema validation: use `SNOWFLAKE_SCHEMA_VALIDATION` instead of a custom SQL check
- [ ] Ensure SQL returns exactly one number — wrap in `SELECT COUNT(*)` or `SELECT SUM(...)` if needed
- [ ] Set `depends_on:` to enforce ordering relative to the load task being validated

## Before / After Example

### Prefect (before)

```python
@task
def check_no_nulls():
    connector = SnowflakeConnector.load("sf-prod")
    with connector.get_connection() as conn:
        nulls = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE order_id IS NULL"
        ).fetchone()[0]
    assert nulls == 0, f"Found {nulls} null order IDs"

@task
def check_row_count():
    connector = SnowflakeConnector.load("sf-prod")
    with connector.get_connection() as conn:
        count = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE load_date = CURRENT_DATE"
        ).fetchone()[0]
    if count < 1000:
        raise ValueError(f"Only {count} rows loaded — expected at least 1000")

@task
def check_stale_data():
    # Soft failure — just warn
    connector = SnowflakeConnector.load("sf-prod")
    with connector.get_connection() as conn:
        hours = conn.cursor().execute(
            "SELECT DATEDIFF('hour', MAX(updated_at), CURRENT_TIMESTAMP) FROM orders"
        ).fetchone()[0]
    if hours > 24:
        logger.warning(f"Data is {hours} hours old")

@flow
def quality_flow():
    check_no_nulls()
    check_row_count()
    check_stale_data()
```

### Orchestra YAML (after)

```yaml
version: v1
name: quality-flow

pipeline:
  stage-quality:
    tasks:
      check-no-nulls:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        name: check_no_nulls
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT COUNT(*) FROM orders WHERE order_id IS NULL'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []

      check-row-count:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        name: check_row_count
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT COUNT(*) FROM orders WHERE load_date = CURRENT_DATE'
          error_threshold_expression: '< 1000'
          warn_threshold_expression: '< 1000'
        depends_on: []

      check-stale-data:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        name: check_stale_data
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT DATEDIFF(''hour'', MAX(updated_at), CURRENT_TIMESTAMP) FROM orders'
          warn_threshold_expression: '> 24'
        treat_failure_as_warning: true
        depends_on: []
```

## Gotchas

- **Semantic inversion is the #1 mistake:** Prefect tests PASS when the condition is TRUE; Orchestra FAILS when the threshold expression IS MET. Always flip the operator.
- SQL must return a **single number** — multi-column or multi-row results will error
- `assert X == 0` → `error_threshold_expression: '> 0'` (fail when count is greater than zero)
- `assert X >= 1000` → `error_threshold_expression: '< 1000'` (fail when count is less than 1000)
- Great Expectations and Soda have **no native Orchestra integration** — use `PYTHON_EXECUTE_SCRIPT`
- Threshold expression syntax is a single-character comparator followed by a non-negative integer: `> 0`, `= 0`, `>= 100`, `< 1000`, `!= 0`. **Confirmed live against Orchestra's `/pipelines/schema` validator: `== 0` (Python-style double-equals) is rejected** ("Invalid threshold expression format") — use single `=`, not `==`, for equality, even though Prefect's own assertions use `==`.
- `treat_failure_as_warning: true` makes the pipeline continue with WARNING status instead of failing hard
- For SQL Server test tasks, use `SQL_SERVER_RUN_QUERY` (not a `_RUN_TEST` suffix variant)
- Single-quotes inside SQL strings must be escaped as `''` in YAML block scalars
- `depends_on:` should reference the load/transform task that produces the data being tested

## References

- https://docs.prefect.io/v3/develop/write-tasks
- https://docs.getorchestra.io/docs/core-concepts/pipelines/schema

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
