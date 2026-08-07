---
name: dagster-asset-checks-to-orchestra
description: "Use this skill when a Dagster project contains data quality / testing logic: @asset_check, asset checks with AssetCheckResult, build_metadata_bounds_checks, dbt tests run via dagster-dbt, dagster-pandera / dagstermill expectations, or ExpectationResult. Triggers: any @asset_check decorated function, any AssetCheckSpec, any SQL/threshold assertion run as a check, any use of ExpectationResult or great_expectations/pandera within an asset."
---

# Dagster Asset Checks -> Orchestra Test Jobs

## Overview

Dagster data quality is expressed via `@asset_check` functions that return `AssetCheckResult(passed=..., severity=...)`, built-in checks like `build_metadata_bounds_checks`, dbt tests surfaced through `dagster-dbt`, and `ExpectationResult`. Orchestra has native test job types for SQL-based checks across all major warehouses, with configurable error and warning thresholds.

---

## Test Job Pattern

```yaml
parameters:
  statement: "SELECT COUNT(*) FROM orders WHERE amount < 0"
  error_threshold_expression: "> 0"    # FAIL if any negative amounts
  warn_threshold_expression: "> 0"     # WARN at same threshold (or looser)
```

The `statement` must return a **single numeric value**. The result is compared against the threshold expressions. Both default to `"> 0"` — fail if any rows match.

---

## Available Test Integration Jobs

| Integration | `integration_job` | Warehouse |
|---|---|---|
| `SNOWFLAKE` | `SNOWFLAKE_RUN_TEST` | Snowflake |
| `GCP_BIG_QUERY` | `GCP_BQ_RUN_TEST` | BigQuery |
| `POSTGRES` | `POSTGRES_RUN_TEST` | PostgreSQL |
| `DATABRICKS` | `DATABRICKS_RUN_TEST` | Databricks SQL |
| `FABRIC_SYNAPSE` | `FABRIC_SYNAPSE_RUN_DQ_TEST` | Microsoft Fabric |
| `SNOWFLAKE` | `SNOWFLAKE_SCHEMA_VALIDATION` | Column type/constraint checks |
| `SNOWFLAKE` | `SNOWFLAKE_ANOMALY_DETECTION` | ML-based anomaly detection |
| `DBT_CORE` | `DBT_CORE_EXECUTE` with `dbt test;` | dbt test framework |

---

## Dagster Pattern Mapping

### `@asset_check` returning `AssetCheckResult` -> `*_RUN_TEST`

A Dagster check passes when `passed=True`. Orchestra's test **fails when the SQL result matches the threshold** — so invert the logic.

```python
# Dagster
@asset_check(asset=orders)
def no_null_order_ids(snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        nulls = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE order_id IS NULL").fetchone()[0]
    return AssetCheckResult(passed=nulls == 0, metadata={"null_count": nulls})
```

```yaml
# Orchestra — fails if any nulls found
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_TEST
  name: no_null_order_ids
  connection: snowflake_prod_12345
  parameters:
    statement: 'SELECT COUNT(*) FROM orders WHERE order_id IS NULL'
    error_threshold_expression: '> 0'
    warn_threshold_expression: '> 0'
  depends_on: []
  condition: null
  tags: []
```

### `AssetCheckSeverity.WARN` -> `warn_threshold_expression` / `treat_failure_as_warning`

A WARN-severity check that should not halt the run:

```yaml
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_TEST
  name: soft_row_count_check
  connection: snowflake_prod_12345
  treat_failure_as_warning: true    # FAILED -> WARNING; pipeline continues
  parameters:
    statement: 'SELECT COUNT(*) FROM orders WHERE created_at < CURRENT_DATE - 7'
    error_threshold_expression: '> 0'
    warn_threshold_expression: '> 0'
  depends_on: []
```

### dbt tests via `dagster-dbt` -> `DBT_CORE_EXECUTE`

Do not reimplement dbt tests as SQL — run them through the dbt task:

```yaml
task-001:
  integration: DBT_CORE
  integration_job: DBT_CORE_EXECUTE
  name: dbt_test
  connection: dbt_core_conn_12345
  parameters:
    commands: 'dbt test;'
    package_manager: PIP
    python_version: '3.12'
  depends_on: []
```

Or chain: `commands: 'dbt run; dbt test;'`.

### Python-based checks (pandera / great_expectations) -> `PYTHON_EXECUTE_SCRIPT`

No native GE/pandera integration. Run via Python and expose pass/fail as an output:

```python
# scripts/run_ge_checkpoint.py
import os
import great_expectations as ge
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))

context = ge.get_context()
results = context.run_checkpoint(checkpoint_name="my_checkpoint")
client.set_output("passed", results.success)
```

```yaml
task-001:
  integration: PYTHON
  integration_job: PYTHON_EXECUTE_SCRIPT
  name: run_ge_checkpoint
  connection: my_python_conn_12345
  parameters:
    command: 'python scripts/run_ge_checkpoint.py'
    python_version: '3.12'
    set_outputs: true
  depends_on: []
```

---

## Schema Validation (Snowflake)

Dagster `build_metadata_bounds_checks` / type constraints map to a dedicated schema validation job:

```yaml
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_SCHEMA_VALIDATION
  name: validate_schema
  connection: snowflake_prod_12345
  parameters:
    table_name: orders
    column_name: order_id
    expected_type: NUMBER
    is_nullable: false
    is_primary_key: true
    is_unique: true
  depends_on: []
```

---

## Before / After Example

### Dagster (before)

```python
from dagster import asset, asset_check, AssetCheckResult, Definitions
from dagster_snowflake import SnowflakeResource

@asset
def orders(snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        conn.cursor().execute("INSERT INTO orders SELECT * FROM orders_staging")

@asset_check(asset=orders)
def no_null_order_ids(snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        nulls = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE order_id IS NULL").fetchone()[0]
    return AssetCheckResult(passed=nulls == 0, metadata={"null_count": nulls})

defs = Definitions(assets=[orders], asset_checks=[no_null_order_ids],
                   resources={"snowflake": SnowflakeResource(...)})
```

### Orchestra YAML (after)

```yaml
version: v1
name: quality-pipeline

pipeline:
  stage-load:
    tasks:
      load-data:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        name: orders
        connection: snowflake_prod_12345
        parameters:
          statement: 'INSERT INTO orders SELECT * FROM orders_staging'
        depends_on: []
        condition: null
        tags: []
    depends_on: []

  stage-quality:
    tasks:
      check-no-nulls:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        name: no_null_order_ids
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT COUNT(*) FROM orders WHERE order_id IS NULL'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        condition: null
        tags: []
    depends_on: [stage-load]
```

---

## Gotchas

- **SQL must return a single number** — wrap complex checks in a subquery returning one COUNT/SUM.
- **`AssetCheckResult(passed=...)` semantics inversion** — Dagster passes when `passed=True`; Orchestra fails when the result matches the threshold. Invert the logic.
- **`AssetCheckSeverity.WARN`** — maps to `warn_threshold_expression` (looser than error) or `treat_failure_as_warning: true`.
- **dbt tests via `dagster-dbt`** — run through `DBT_CORE_EXECUTE` (`dbt test;`), don't reimplement as SQL.
- **Python checks (pandera/GE)** — use `PYTHON_EXECUTE_SCRIPT` + `set_outputs: true`.
- **error vs warn thresholds** — set warn looser; if equal, the task goes straight to FAILED with no WARNING.
- **Threshold syntax** — a single-character comparator followed by a non-negative integer: `> 0`, `= 0`, `>= 100`, `< 0.05`, `!= 0`. **Confirmed live against Orchestra's `/pipelines/schema` validator: `== 0` (Python-style double-equals) is rejected** ("Invalid threshold expression format") — use single `=`, not `==`, for equality.

## Adding Alerts

```yaml
alerts:
  - name: quality-check-failed
    statuses: [FAILED, WARNING]
    destinations:
      - integration: SLACK
        destination: '#data-quality'
    custom_message: 'Data quality check failed — review before proceeding.'
```

## References

- Orchestra test jobs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Snowflake schema validation: https://docs.getorchestra.io/docs/integrations/snowflake
- Dagster asset checks: https://docs.dagster.io/concepts/assets/asset-checks
- Dagster dbt tests: https://docs.dagster.io/integrations/libraries/dbt
