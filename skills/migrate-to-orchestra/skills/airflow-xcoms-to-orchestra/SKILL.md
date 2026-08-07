---
name: airflow-xcoms-to-orchestra
description: "Use this skill when an Airflow DAG uses xcom_push, xcom_pull, or the TaskFlow API @task return values to pass data between tasks. Triggers: any DAG with ti.xcom_push(), context['ti'].xcom_pull(), @task decorated functions that return values, or BranchPythonOperator decisions driven by upstream XCom values."
---

# Airflow XComs → Orchestra Outputs

## Overview

Airflow XComs (cross-communications) let tasks share small values by pushing to and pulling from a key-value store. Orchestra replaces this with a typed **outputs system**: a task explicitly sets named outputs using the Orchestra SDK, and downstream tasks or conditions reference them via `${{ ORCHESTRA.PIPELINE_RUN_TASKS['task_id'].OUTPUTS['key'] }}`.

Key architectural difference: XComs are implicit (any task can pull from any other). Orchestra outputs are explicit — a task must opt in with `set_outputs: true` in its parameters and call the Orchestra SDK's `set_output()` **on an instantiated client**, not a bare imported function — see the code below.

---

## Pattern Mapping

| Airflow pattern | Orchestra equivalent |
|---|---|
| `ti.xcom_push(key='count', value=42)` | `OrchestraSDK` client's `client.set_output('count', 42)` — see setup below |
| `ti.xcom_pull(task_ids='my_task', key='count')` | `${{ ORCHESTRA.PIPELINE_RUN_TASKS['my-task'].OUTPUTS['count'] }}` |
| `@task` return value | `client.set_output('return_value', result)` |
| XCom-driven `BranchPythonOperator` | `condition:` expression on downstream stage |
| Passing large datasets via XCom | Restructure: write to S3/Snowflake, pass only the path/table name as output |

---

## Setting Outputs in a Python Task

The task script must instantiate the `OrchestraSDK` client and call `.set_output()` on it — there is no bare `set_output()` function to import. Enable output capture with `set_outputs: true` in parameters; Orchestra auto-injects `ORCHESTRA_API_KEY` into every `PYTHON_EXECUTE_SCRIPT` task's environment, so the script doesn't need a connection or secret for this.

```yaml
stage-extract:
  tasks:
    get-row-count:
      integration: PYTHON
      integration_job: PYTHON_EXECUTE_SCRIPT
      name: get_row_count
      connection: my_python_conn_12345
      parameters:
        command: 'python scripts/get_row_count.py'
        python_version: '3.12'
        set_outputs: true          # required — enables output capture
      depends_on: []
```

```python
# scripts/get_row_count.py
import os
import snowflake.connector
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))

conn = snowflake.connector.connect(...)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
count = cursor.fetchone()[0]

client.set_output("pending_count", count)   # string key, any JSON-serialisable value
client.set_output("has_pending", count > 0)
```

---

## Referencing Outputs Downstream

Use the `${{ }}` expression syntax in `condition:`, task `parameters:`, or `inputs:` defaults.

```yaml
stage-notify:
  tasks:
    notify:
      integration: SLACK
      integration_job: SEND_SLACK_MESSAGE
      name: notify_count
      connection: slack_prod_12345
      parameters:
        channel_name: '#data-team'
        text: "Pending orders: ${{ ORCHESTRA.PIPELINE_RUN_TASKS['get-row-count'].OUTPUTS['pending_count'] }}"
      depends_on: []
```

```yaml
# In a condition expression
stage-process:
  depends_on: [stage-extract]
  condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['get-row-count'].OUTPUTS['has_pending'] == True }}"
  tasks:
    process-orders:
      ...
```

---

## set_outputs: true — Which Integrations Support It

| Integration | `integration_job` | set_outputs field |
|---|---|---|
| `PYTHON` | `PYTHON_EXECUTE_SCRIPT` | `parameters.set_outputs: true` |
| `SNOWFLAKE` | `SNOWFLAKE_RUN_QUERY` | `parameters.set_outputs: true` |
| `GCP_BIG_QUERY` | `GCP_BQ_RUN_QUERY_JOB` | `parameters.set_outputs: true` |
| `DATABRICKS` | `DATABRICKS_RUN_WORKFLOW` | `parameters.set_outputs: true` |
| `DATABRICKS` | `DATABRICKS_EXECUTE_STATEMENT` | `parameters.set_outputs: true` |
| `HTTP` | `HTTP_REQUEST` | `parameters.set_outputs: true` |
| `AWS_LAMBDA` | `AWS_LAMBDA_EXECUTE_ASYNC_FUNCTION` | `parameters.set_outputs: true` |
| `MOTHERDUCK` | `MOTHERDUCK_EXECUTE_QUERY` | `parameters.set_outputs: true` |

For SQL integrations with `set_outputs: true`, the query result is captured automatically — no SDK call needed.

---

## Before / After Example

### Airflow DAG (before)

```python
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.dates import days_ago

def get_record_count(ti, **context):
    import snowflake.connector
    conn = snowflake.connector.connect(...)
    count = conn.cursor().execute("SELECT COUNT(*) FROM new_records").fetchone()[0]
    ti.xcom_push(key="record_count", value=count)

def decide_branch(ti, **context):
    count = ti.xcom_pull(task_ids="get_count", key="record_count")
    return "process_records" if count > 0 else "skip_processing"

with DAG("xcom_example", schedule_interval="@daily", start_date=days_ago(1)) as dag:
    get_count = PythonOperator(task_id="get_count", python_callable=get_record_count)
    branch    = BranchPythonOperator(task_id="branch", python_callable=decide_branch)
    process   = PythonOperator(task_id="process_records", python_callable=lambda: print("processing"))
    skip      = PythonOperator(task_id="skip_processing", python_callable=lambda: print("skipping"))

    get_count >> branch >> [process, skip]
```

### Orchestra YAML (after)

```yaml
version: v1
name: xcom-example

schedule:
  - cron: '0 0 * * ? *'
    timezone: UTC

pipeline:
  stage-count:
    tasks:
      get-count:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        name: get_record_count
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT COUNT(*) FROM new_records'
          set_outputs: true      # result captured automatically
        depends_on: []

  stage-process:
    depends_on: [stage-count]
    condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['get-count'].OUTPUTS['result'] > 0 }}"
    tasks:
      process-records:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: process_records
        connection: my_python_conn_12345
        parameters:
          command: 'python scripts/process.py'
          python_version: '3.12'
        depends_on: []

  stage-skip:
    depends_on: [stage-count]
    condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['get-count'].OUTPUTS['result'] == 0 }}"
    tasks:
      log-skip:
        integration: SLACK
        integration_job: SEND_SLACK_MESSAGE
        name: log_skip
        connection: slack_prod_12345
        parameters:
          channel_name: '#data-team'
          text: 'No new records — processing skipped.'
        depends_on: []
```

---

## Gotchas

- **`set_outputs: true` is required** — without it, `client.set_output()` calls in the script are silently ignored.
- **`set_output` is a method on an `OrchestraSDK` instance, not a bare function** — `from orchestra_sdk import set_output` doesn't exist. Import `from orchestra_sdk.orchestra import OrchestraSDK`, instantiate `client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))`, then call `client.set_output(...)`.
- **Key names are strings** — `client.set_output("count", 42)` is referenced as `.OUTPUTS['count']`, not `.OUTPUTS.count`.
- **XCom size limits don't apply** — but keep outputs small (IDs, counts, flags). Large datasets should go to S3/Snowflake with only the reference path as an output.
- **Task ID format** — Orchestra task IDs in YAML (`get-count`) are typically hyphenated. The `PIPELINE_RUN_TASKS` reference must match exactly.
- **`@task` return values** — there's no implicit capture. Extract the function, call `client.set_output('return_value', result)` explicitly.
- **SQL `set_outputs`** — for Snowflake/BigQuery, the first column of the first row is captured as `result`. Write your query to return a single meaningful value.
- **XCom default key** — Airflow's `return_value` key (from `@task`) has no Orchestra equivalent. Always use explicit named keys.
- **Quote-wrap a JSON-shaped `OUTPUTS` reference in triple-quotes, not single/double** — `${{ }}` substitution is raw text with no escaping. `json.loads("${{ ...OUTPUTS['metrics'] }}")` breaks the moment the substituted JSON contains a `"` (i.e. always, for anything but a bare number). Use `json.loads("""${{ ...OUTPUTS['metrics'] }}""")` instead — a triple-quoted string only ends on three consecutive matching quotes, so individual `"` from the JSON payload is safe.

## Adding Alerts

```yaml
alerts:
  - name: on-failure
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
```

## References

- Orchestra outputs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema#taskmodel
- Orchestra SDK: https://docs.getorchestra.io/docs/integrations/python
