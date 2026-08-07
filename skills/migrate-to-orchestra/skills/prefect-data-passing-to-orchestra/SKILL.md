---
name: prefect-data-passing-to-orchestra
description: "Use this skill when a Prefect flow passes data between tasks via return values (.result()), task.submit() futures, Prefect Artifacts, or .map() for fan-out. Triggers: any Prefect flow where a downstream task consumes the return value of an upstream task, any .map() usage, any Prefect Artifact that is read by a downstream step, or any conditional branch driven by a task's return value."
---

## Overview

Prefect passes data between tasks implicitly via Python return values — a downstream task simply receives the upstream return value as an argument. Orchestra has no implicit data passing: inter-task values must be explicitly captured with the Orchestra SDK's `set_output()` — called on an instantiated `OrchestraSDK` client, not a bare imported function — in the upstream task, and referenced with a template expression in the downstream task. Large objects (DataFrames, files) cannot cross task boundaries at all and must be staged in external storage.

## Parameter Mapping

| Prefect pattern | Orchestra equivalent | Notes |
|---|---|---|
| `result = task_a(); task_b(result)` (small scalar/string) | upstream: `set_outputs: true` + `client.set_output('key', val)`; downstream: `${{ ORCHESTRA.PIPELINE_RUN_TASKS['task_a_id'].OUTPUTS['key'] }}` | |
| `result = task_a.submit(); task_b(result.result())` | same as above | `.submit()` futures map 1-to-1 |
| Large DataFrame passed to next task | Stage in S3/Snowflake; pass only path/table name as output string | DataFrames cannot cross Orchestra task boundaries |
| `list_of_results = task.map(items)` | `matrix:` block on the task group | See matrix example below |
| Prefect Artifact (observability only) | Drop — Artifacts with no downstream consumer have no Orchestra equivalent | |
| Prefect Artifact read by downstream step | Capture with `client.set_output()` instead; Artifacts are not queryable by other Orchestra tasks | |
| Conditional branch driven by task return value | Upstream `client.set_output('flag', bool_val)` + downstream `condition: '${{ ORCHESTRA.PIPELINE_RUN_TASKS[...].OUTPUTS["flag"] == true }}'` | |

## Orchestra YAML Structure

### Scalar output capture (Python task)

```yaml
parameters:
  command: 'python scripts/get_row_count.py'
  python_version: '3.12'
  set_outputs: true   # required — without this, client.set_output() calls are silently ignored
```

Corresponding Python script — instantiate the `OrchestraSDK` client and call `.set_output()` on it; `ORCHESTRA_API_KEY` is auto-injected into every `PYTHON_EXECUTE_SCRIPT` task's environment, no connection/secret needed for this:

```python
# scripts/get_row_count.py
import os
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))

count = run_query("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
client.set_output("pending_count", count)
client.set_output("has_pending", count > 0)
```

Downstream task referencing the output. `environment_variables` is a single JSON string, not a nested YAML map:

```yaml
parameters:
  environment_variables: '{"PENDING_COUNT": "${{ ORCHESTRA.PIPELINE_RUN_TASKS[''get-row-count''].OUTPUTS[''pending_count''] }}"}'
```

### `.map()` → matrix fan-out

```yaml
inputs:
  items:
    type: list
    default: ["item_a", "item_b", "item_c"]

pipeline:
  stage-process:
    matrix:
      inputs:
        item: '${{ inputs.items }}'
      max_parallel: 5
    tasks:
      process-item:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: 'python scripts/process_item.py'
          python_version: '3.12'
          environment_variables: '{"ITEM": "${{ matrix.item }}"}'
        depends_on: []
```

### SQL task with auto-captured output

SQL tasks with `set_outputs: true` automatically capture the first column of the first row as the key `result`:

```yaml
integration: SNOWFLAKE
integration_job: SNOWFLAKE_RUN_QUERY
parameters:
  query: "SELECT COUNT(*) FROM orders WHERE status = 'pending'"
  set_outputs: true
```

Reference downstream: `${{ ORCHESTRA.PIPELINE_RUN_TASKS["count-pending"].OUTPUTS["result"] }}`

## Conversion Steps

- [ ] List every inter-task data dependency in the Prefect flow (task A return value → task B argument)
- [ ] Classify each value as: scalar/string (can use `client.set_output`), large object (must stage externally), or observability-only Artifact (drop)
- [ ] For each small value: add `set_outputs: true` to upstream task parameters; instantiate `OrchestraSDK` and call `client.set_output("key", value)` in the script
- [ ] For each large object (DataFrame, file): add staging logic to the upstream script (write to S3/Snowflake), capture the path/table name as the output
- [ ] Replace each downstream Python argument reference with the `ORCHESTRA.PIPELINE_RUN_TASKS[...].OUTPUTS[...]` template expression
- [ ] For `.map()` calls: convert to a `matrix:` block; pass the iterable via `inputs:` and reference each item with `${{ matrix.item }}`
- [ ] For runtime-computed lists in `.map()`: capture the list with `client.set_output("items", [...])` from the upstream task; reference it in `matrix.inputs`
- [ ] For conditional branches: use `client.set_output` for the flag and a `condition:` expression on the downstream task/stage

## Before / After Example

### Prefect (before)

```python
from prefect import task, flow

@task
def get_pending_count() -> int:
    return run_query("SELECT COUNT(*) FROM orders WHERE status = 'pending'")

@task
def notify_if_pending(count: int):
    if count > 0:
        send_slack_message(f"{count} pending orders found")

@flow
def orders_flow():
    count = get_pending_count()
    notify_if_pending(count)
```

### Orchestra YAML (after)

```yaml
pipeline:
  stage-count:
    tasks:
      get-pending-count:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        connection: snowflake_prod_12345
        parameters:
          query: "SELECT COUNT(*) FROM orders WHERE status = 'pending'"
          set_outputs: true
        depends_on: []

  stage-notify:
    tasks:
      notify-if-pending:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        connection: null
        parameters:
          source: INLINE
          code: |
            if count > 0:
                send_slack_message(f"{count} pending orders found")
          environment_variables: '{"PENDING_COUNT": "${{ ORCHESTRA.PIPELINE_RUN_TASKS[''get-pending-count''].OUTPUTS[''result''] }}"}'
        condition: '${{ ORCHESTRA.PIPELINE_RUN_TASKS["get-pending-count"].OUTPUTS["result"] | int > 0 }}'
        depends_on:
          - get-pending-count
```

## Gotchas

- `set_outputs: true` is **REQUIRED** on the task — without it, `client.set_output()` calls inside the script are silently ignored and outputs will be empty
- **`set_output` is a method on an `OrchestraSDK` instance, not a bare function** — `from orchestra_sdk import set_output` doesn't exist. Import `from orchestra_sdk.orchestra import OrchestraSDK`, instantiate `client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))` (that env var is auto-injected, no connection/secret needed), then call `client.set_output(...)`.
- Prefect return values are implicit; Orchestra outputs are explicit opt-in — every inter-task value must be named
- `.map()` with a runtime-computed list also works: capture the list with `client.set_output` upstream, then reference it in `matrix.inputs` as a template expression
- Large DataFrames and binary objects cannot cross Orchestra task boundaries — always stage in S3, Snowflake, or another warehouse and pass only the location string
- SQL tasks with `set_outputs: true` auto-capture the first column of the first row as `'result'` — no Python script needed for simple scalar queries
- Prefect Artifacts are observability features (logged to the Prefect UI) — they do not expose a queryable value to downstream tasks; replace with `client.set_output()` if the value is needed downstream, otherwise drop entirely
- `environment_variables` is a single JSON string, not a nested YAML map — and it can itself contain a `${{ }}` expression as a literal substring, so long as it's within the outer string. This is only safe for substitutions that resolve to a *plain* value (a date, an id, a flag) — if the `OUTPUTS`/`inputs` value could itself be JSON-shaped (contains `"`), don't route it through `environment_variables`; there's no escaping mechanism there and the substituted quotes will break the JSON. Substitute it directly in `code:` instead (see the next gotcha).
- **Quote-wrap a JSON-shaped `OUTPUTS` reference in triple-quotes, not single/double** — `${{ }}` substitution is raw text with no escaping. `json.loads("${{ ...OUTPUTS['key'] }}")` breaks the moment the substituted JSON contains a `"` (i.e. always, for anything but a bare number). Use `json.loads("""${{ ...OUTPUTS['key'] }}""")` instead — a triple-quoted string only ends on three consecutive matching quotes, so individual `"` from the JSON payload is safe.

## References

- https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- https://docs.prefect.io/v3/develop/write-tasks
- See `prefect-alerts-to-orchestra` for all notification patterns.

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
