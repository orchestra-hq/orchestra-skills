---
name: dagster-io-managers-to-orchestra
description: "Use this skill when a Dagster project passes data between ops/assets via return values, Out/In wiring, IO managers, or context.add_output_metadata, and you need that data flow represented in Orchestra. Triggers: any op/asset that returns a value consumed downstream, any custom or built-in IOManager, any use of Output(value, metadata=...), AssetMaterialization metadata, or MetadataValue used to surface values to downstream logic."
---

# Dagster Data Passing (Outputs / IO Managers) -> Orchestra Outputs

## Overview

Dagster passes data between ops/assets implicitly: an op returns a value, an **IO manager** persists it, and the downstream op receives it as a typed input. This is one of Dagster's core abstractions.

Orchestra has no shared in-process object space and no IO-manager layer. It uses a typed **outputs system**: a task explicitly sets named outputs (with `set_outputs: true` and the Orchestra SDK's `set_output()` called on an instantiated `OrchestraSDK` client — not a bare imported function — or automatic capture for SQL tasks), and downstream tasks or conditions reference them via `${{ ORCHESTRA.PIPELINE_RUN_TASKS['task_id'].OUTPUTS['key'] }}`.

Key architectural difference: **Dagster data flow is implicit and can carry arbitrary objects; Orchestra outputs are explicit and small (IDs, counts, flags). Large data is staged externally and only the reference is passed.**

---

## Pattern Mapping

| Dagster pattern | Orchestra equivalent |
|---|---|
| `return value` consumed by downstream op | `client.set_output('return_value', value)` + downstream reference |
| Custom `IOManager` persisting to S3/warehouse | Explicit write in the script; pass the path/table as an output |
| `Output(value, metadata=...)` | `client.set_output('key', value)` (metadata is observability only) |
| IO-manager-loaded input | Downstream task reads from S3/warehouse, or via `${{ ...OUTPUTS... }}` for small values |
| Branch on a returned value | `condition:` expression on the downstream stage |
| Large DataFrame passed between ops | Stage in S3/Snowflake; pass only the path/table name |

---

## Setting Outputs in a Python Task

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
        set_outputs: true          # required
      depends_on: []
```

```python
# scripts/get_row_count.py
import os
import snowflake.connector
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))

conn = snowflake.connector.connect(...)
count = conn.cursor().execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]

client.set_output("pending_count", count)
client.set_output("has_pending", count > 0)
```

`ORCHESTRA_API_KEY` is auto-injected into every `PYTHON_EXECUTE_SCRIPT` task's environment — no connection or secret setup needed for this.

---

## Referencing Outputs Downstream

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
stage-process:
  depends_on: [stage-extract]
  condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['get-row-count'].OUTPUTS['has_pending'] == True }}"
  tasks:
    process-orders:
      ...
```

---

## set_outputs: true — Supported Integrations

| Integration | `integration_job` | Field |
|---|---|---|
| `PYTHON` | `PYTHON_EXECUTE_SCRIPT` | `parameters.set_outputs: true` |
| `SNOWFLAKE` | `SNOWFLAKE_RUN_QUERY` | `parameters.set_outputs: true` |
| `GCP_BIG_QUERY` | `GCP_BQ_RUN_QUERY_JOB` | `parameters.set_outputs: true` |
| `DATABRICKS` | `DATABRICKS_RUN_WORKFLOW` / `DATABRICKS_EXECUTE_STATEMENT` | `parameters.set_outputs: true` |
| `HTTP` | `HTTP_REQUEST` | `parameters.set_outputs: true` |
| `AWS_LAMBDA` | `AWS_LAMBDA_EXECUTE_ASYNC_FUNCTION` | `parameters.set_outputs: true` |
| `MOTHERDUCK` | `MOTHERDUCK_EXECUTE_QUERY` | `parameters.set_outputs: true` |

For SQL integrations, the first column of the first row is captured automatically as `result` — no SDK call needed.

---

## Before / After Example

### Dagster (before)

```python
from dagster import asset, Output, MetadataValue

@asset
def record_count(context) -> Output[int]:
    import snowflake.connector
    conn = snowflake.connector.connect(...)
    count = conn.cursor().execute("SELECT COUNT(*) FROM new_records").fetchone()[0]
    return Output(count, metadata={"count": MetadataValue.int(count)})

@asset
def processed(context, record_count: int):
    if record_count > 0:
        process_records()
    else:
        context.log.info("no new records")
```

### Orchestra YAML (after)

```yaml
version: v1
name: outputs-example

pipeline:
  stage-count:
    tasks:
      get-count:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        name: record_count
        connection: snowflake_prod_12345
        parameters:
          statement: 'SELECT COUNT(*) FROM new_records'
          set_outputs: true
        depends_on: []

  stage-process:
    depends_on: [stage-count]
    condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['get-count'].OUTPUTS['result'] > 0 }}"
    tasks:
      process-records:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: processed
        connection: my_python_conn_12345
        parameters:
          command: 'python scripts/process.py'
          python_version: '3.12'
        depends_on: []
```

---

## Gotchas

- **`set_outputs: true` is required** — without it, `client.set_output()` is silently ignored.
- **`set_output` is a method on an `OrchestraSDK` instance, not a bare function** — `from orchestra_sdk import set_output` doesn't exist. Import `from orchestra_sdk.orchestra import OrchestraSDK`, instantiate `client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))`, then call `client.set_output(...)`.
- **Return value -> explicit output** — no implicit capture; call `client.set_output('return_value', result)` (or use SQL auto-capture).
- **IO managers don't port** — replicate any persistence as explicit writes in the script.
- **In-memory objects can't cross tasks** — stage large data in S3/Snowflake; pass only the path/table name.
- **Key names are strings** — `.OUTPUTS['count']`, not `.OUTPUTS.count`.
- **SQL `set_outputs`** — first column of first row captured as `result`; write the query to return one meaningful value.
- **Task ID format** — hyphenated IDs must match exactly in `PIPELINE_RUN_TASKS`.
- **Asset metadata** — `MetadataValue` is observability only; re-expose as an explicit output if downstream logic needs it.
- **Quote-wrap a JSON-shaped `OUTPUTS` reference in triple-quotes, not single/double** — `${{ }}` substitution is raw text with no escaping. `json.loads("${{ ...OUTPUTS['key'] }}")` breaks the moment the substituted JSON contains a `"` (i.e. always, for anything but a bare number). Use `json.loads("""${{ ...OUTPUTS['key'] }}""")` instead — a triple-quoted string only ends on three consecutive matching quotes, so individual `"` from the JSON payload is safe.

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
- Dagster IO managers: https://docs.dagster.io/concepts/io-management/io-managers
- Dagster op outputs: https://docs.dagster.io/concepts/ops-jobs-graphs/ops#outputs
