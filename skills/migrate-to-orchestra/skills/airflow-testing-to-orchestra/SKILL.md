---
name: airflow-testing-to-orchestra
description: "Use this skill when an Airflow DAG contains data quality or testing operators: SqlCheckOperator, SQLThresholdCheckOperator, GreatExpectationsOperator, SodaCheckOperator, DbtTestOperator, or any custom SQL assertion task. Triggers: any task with sql= parameter used for validation, any use of Great Expectations or Soda, any dbt test step."
---

# Airflow Testing Operators → Orchestra Test Jobs

## Overview

Airflow data quality checks are typically `SqlCheckOperator` (pass/fail based on SQL result), `SQLThresholdCheckOperator` (pass/fail with min/max bounds), or framework operators like `GreatExpectationsOperator` and `SodaCheckOperator`. Orchestra has native test job types for SQL-based checks across all major warehouses, with configurable error and warning thresholds.

For mapping the `conn_id=` on these check operators to the right Orchestra connection, see `airflow-connections-to-orchestra`.

---

## Test Job Pattern

All Orchestra test integrations follow the same parameter pattern:

```yaml
parameters:
  statement: "SELECT COUNT(*) FROM orders WHERE amount < 0"
  error_threshold_expression: "> 0"    # FAIL if any negative amounts
  warn_threshold_expression: "> 0"     # WARN at same threshold (or set looser)
```

The `statement` must return a **single numeric value** (count, sum, percentage). The result is compared against the threshold expressions. Both thresholds default to `"> 0"` — fail if any rows returned.

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

## Airflow Operator Mapping

### SqlCheckOperator → `*_RUN_TEST`

`SqlCheckOperator` passes if the SQL returns a truthy (non-zero, non-null) result; fails otherwise.

```python
# Airflow
check_no_nulls = SqlCheckOperator(
    task_id="check_no_nulls",
    conn_id="snowflake_prod",
    sql="SELECT COUNT(*) FROM orders WHERE customer_id IS NULL",
)
# Passes if COUNT = 0, fails if COUNT > 0
```

```yaml
# Orchestra — fails if any nulls found
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_TEST
  name: check_no_nulls
  connection: snowflake_prod_12345
  parameters:
    statement: 'SELECT COUNT(*) FROM orders WHERE customer_id IS NULL'
    error_threshold_expression: '> 0'
    warn_threshold_expression: '> 0'
  depends_on: []
  condition: null
  tags: []
```

### SQLThresholdCheckOperator → `*_RUN_TEST` with threshold expressions

```python
# Airflow
threshold_check = SQLThresholdCheckOperator(
    task_id="check_row_count",
    conn_id="snowflake_prod",
    sql="SELECT COUNT(*) FROM daily_orders",
    min_threshold=1000,
    max_threshold=50000,
)
```

```yaml
# Orchestra — warn if <1000, fail if >50000
# Note: Run two test tasks or use a single query that returns 0 within bounds
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_TEST
  name: check_row_count
  connection: snowflake_prod_12345
  parameters:
    statement: |
      SELECT CASE
        WHEN COUNT(*) < 1000 THEN 1
        WHEN COUNT(*) > 50000 THEN 1
        ELSE 0
      END FROM daily_orders
    error_threshold_expression: '> 0'
    warn_threshold_expression: '> 0'
  depends_on: []
```

### DbtTestOperator → DBT_CORE_EXECUTE

```python
# Airflow
dbt_test = DbtTestOperator(
    task_id="dbt_test",
    dir="/opt/dbt",
    dbt_bin="/usr/local/bin/dbt",
)
```

```yaml
# Orchestra — include test in commands string
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

Or chain with the dbt run:

```yaml
parameters:
  commands: 'dbt run; dbt test;'   # run then test in sequence
```

### GreatExpectationsOperator → PYTHON_EXECUTE_SCRIPT

No native GE integration exists. Run GE via Python:

```python
# scripts/run_ge_checkpoint.py
import os
import great_expectations as ge
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))

context = ge.get_context()
results = context.run_checkpoint(checkpoint_name="my_checkpoint")
passed = results.success
client.set_output("passed", passed)
client.set_output("failed_expectations", results.statistics.get("unsuccessful_expectations", 0))
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

### SodaCheckOperator → PYTHON_EXECUTE_SCRIPT

```python
# scripts/run_soda_checks.py
import os
from soda.scan import Scan
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))

scan = Scan()
scan.set_data_source_name("snowflake_prod")
scan.add_configuration_yaml_file(file_path="soda_config.yml")
scan.add_sodacl_yaml_file(file_path="checks/orders.yml")
scan.execute()

client.set_output("passed", scan.get_error_logs_text() == "")
client.set_output("errors", len(scan.get_error_logs()))
```

```yaml
task-001:
  integration: PYTHON
  integration_job: PYTHON_EXECUTE_SCRIPT
  name: run_soda_checks
  connection: my_python_conn_12345
  parameters:
    command: 'python scripts/run_soda_checks.py'
    python_version: '3.12'
    set_outputs: true
  depends_on: []
```

---

## Schema Validation (Snowflake)

Orchestra has a dedicated schema validation job for Snowflake column type checks:

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

## Non-Blocking Tests with `treat_failure_as_warning`

For quality checks that shouldn't halt the pipeline:

```yaml
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_TEST
  name: soft_row_count_check
  connection: snowflake_prod_12345
  treat_failure_as_warning: true    # FAILED → WARNING; pipeline continues
  parameters:
    statement: 'SELECT COUNT(*) FROM orders WHERE created_at < CURRENT_DATE - 7'
    error_threshold_expression: '> 0'
    warn_threshold_expression: '> 0'
  depends_on: []
```

---

## Before / After Example

### Airflow DAG (before)

```python
from airflow.providers.common.sql.operators.sql import SQLCheckOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator

with DAG("quality_pipeline") as dag:
    load = SnowflakeOperator(
        task_id="load_data",
        snowflake_conn_id="snowflake_prod",
        sql="INSERT INTO orders SELECT * FROM orders_staging",
    )
    check_count = SQLCheckOperator(
        task_id="check_row_count",
        conn_id="snowflake_prod",
        sql="SELECT COUNT(*) > 0 FROM orders WHERE load_date = CURRENT_DATE",
    )
    check_nulls = SQLCheckOperator(
        task_id="check_no_nulls",
        conn_id="snowflake_prod",
        sql="SELECT COUNT(*) = 0 FROM orders WHERE order_id IS NULL",
    )
    load >> check_count >> check_nulls
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
        name: load_data
        connection: snowflake_prod_12345
        parameters:
          statement: 'INSERT INTO orders SELECT * FROM orders_staging'
        depends_on: []
        condition: null
        tags: []
    depends_on: []

  stage-quality:
    tasks:
      check-row-count:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        name: check_row_count
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT COUNT(*) FROM orders WHERE load_date = CURRENT_DATE'
          error_threshold_expression: '= 0'    # fail if zero rows
          warn_threshold_expression: '= 0'
        depends_on: []
        condition: null
        tags: []

      check-no-nulls:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        name: check_no_nulls
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT COUNT(*) FROM orders WHERE order_id IS NULL'
          error_threshold_expression: '> 0'    # fail if any nulls
          warn_threshold_expression: '> 0'
        depends_on: []
        condition: null
        tags: []
    depends_on: [stage-load]
```

---

## Gotchas

- **SQL must return a single number** — test queries must resolve to one row, one column. Wrap complex queries in a subquery with a COUNT or SUM.
- **Threshold expression syntax** — a single-character comparator followed by a non-negative integer: `"> 0"`, `"= 0"`, `">= 100"`, `"< 0.05"`, `"!= 0"`, `"<= 0"`. **Confirmed live against Orchestra's `/pipelines/schema` validator: `"== 0"` (Python-style double-equals) is rejected** with "Invalid threshold expression format" — use a single `=`, not `==`, for equality. This is an easy mistake since `==` reads naturally and looks like a comparator.
- **`error_threshold_expression` vs `warn_threshold_expression`** — set warn looser than error (e.g. error `> 10`, warn `> 5`). If both are the same, the task goes directly to FAILED with no WARNING state.
- **SqlCheckOperator semantics inversion** — Airflow's `SqlCheckOperator` passes when the SQL returns truthy. Orchestra's test fails when the result matches the threshold. Invert your SQL: Airflow `SELECT COUNT(*) > 0 FROM ...` becomes Orchestra `SELECT COUNT(*) FROM ...` with `error_threshold_expression: '= 0'` (single `=`, not `==`).
- **GreatExpectations / Soda** — no native integration. Use `PYTHON_EXECUTE_SCRIPT` with `set_outputs: true` to expose pass/fail to downstream conditions.
- **`treat_failure_as_warning: true`** — use this for non-blocking quality checks. The pipeline continues even if the test fails, but the run gets a WARNING status and alerts fire.

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
