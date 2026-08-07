---
name: python-prefect-to-orchestra
description: "Use this skill when the user wants to convert a Prefect @task function containing arbitrary Python logic (computation, API calls, pandas, boto3, etc.) into an equivalent Orchestra Python pipeline task. Triggers: any mention of migrating or rewriting Prefect @task functions to Orchestra; Prefect flow code with @task decorators that are not a dedicated integration (not dbt/Airbyte/Fivetran); ShellOperation tasks running Python scripts."
---

## Overview

Converts Prefect `@task` functions into Orchestra `PYTHON_EXECUTE_SCRIPT` pipeline tasks. The function body already lives inline in the flow code, not in a separate repo checked out at runtime — so it maps directly to `source: INLINE` + `parameters.code`, with no Git repo or connection wiring needed unless the task genuinely needs credentials. Only use `source: GIT` + `parameters.command` when the task checks out and runs a script from an already-separate repo. Flow-level inputs become pipeline `inputs:` and are passed via `parameters.environment_variables` (a JSON string) or inlined as literals. Task decorators (`retries`, `timeout_seconds`, `tags`) map to `configuration:` and `tags:`.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `@task` function body | `parameters.code` (inline) | Copy the body verbatim — no extraction to a file/repo needed |
| top-level `import`s beyond the stdlib | `parameters.build_command` | e.g. `build_command: 'pip install pandas'` |
| Function arguments | inline literals in `code`, or `parameters.environment_variables` + pipeline `inputs:` | `environment_variables` is a single JSON string, e.g. `'{"START_DATE": "..."}'`, read with `os.environ["KEY"]` |
| `@task(retries=2, retry_delay_seconds=30)` | `configuration: {retries: 2, retry_delay: 1}` | Orchestra's `retry_delay` is MINUTES — convert seconds/60 (round up); cap at 120 |
| `@task(timeout_seconds=300)` | `configuration: {timeout: 300}` | Seconds |
| `@task(cache_key_fn=...)` | drop | No Orchestra equivalent |
| `@task(tags=["gpu"])` | `tags: [gpu]` | |
| Prefect blocks inside task (e.g. `SnowflakeConnector.load(...)`) | replace with `os.getenv()` | Credentials via an Orchestra connection's secrets — only wire `connection:` if this is actually needed |
| Return value consumed downstream | `set_outputs: true` + `client.set_output()` in `code` (instantiate `OrchestraSDK` first) | See `prefect-data-passing-to-orchestra` |
| `.submit()` / `wait_for=[task_a]` | `depends_on: [task-001]` | Model as explicit DAG dependency |
| `@flow` parameters | pipeline `inputs:` block | `type: string/integer/boolean`, optional `default:` |

## Orchestra YAML Structure

```yaml
version: v1
name: metrics-flow
inputs:
  start_date:
    type: string
    default: '2024-01-01'
  end_date:
    type: string
    default: '2024-01-02'
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: compute_metrics
        connection: null                          # usually null for INLINE — set only if the code needs a specific connection's secrets
        parameters:
          source: INLINE                           # default — code already lives in the @task, no Git repo involved
          code: |
            <task body, copied verbatim>
          build_command: 'pip install pandas'      # optional — only for non-stdlib imports
          python_version: '3.12'
          environment_variables: '{"START_DATE": "${{ inputs.start_date }}", "END_DATE": "${{ inputs.end_date }}"}'
        configuration:
          retries: 2
          retry_delay: 1
          timeout: 600
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

- [ ] Copy the `@task` function body verbatim into `parameters.code` — no extraction to a file, no Git commit
- [ ] List non-stdlib imports and set `parameters.build_command: 'pip install <package> ...'`
- [ ] Replace any Prefect block loads (`SnowflakeConnector.load(...)`, `S3Bucket.load(...)`, etc.) with `os.getenv()` calls — wire `connection:` only if credentials are genuinely needed
- [ ] Choose `parameters.python_version` (`'3.11'` or `'3.12'`)
- [ ] Map `@flow` parameters to pipeline `inputs:` with types and defaults
- [ ] Map function arguments into `parameters.environment_variables` as a JSON string referencing `${{ inputs.name }}`, or inline them as literals in `code`
- [ ] Map `retries`, `retry_delay_seconds` (convert to minutes), `timeout_seconds` to `configuration:`
- [ ] Map `tags` from `@task` decorator to `tags:`
- [ ] Drop `cache_key_fn` — no Orchestra equivalent
- [ ] Wire `depends_on:` for any `.submit()` / `wait_for=` dependencies
- [ ] If the return value is consumed downstream, add `set_outputs: true` and call `client.set_output()` in `code` (instantiate `OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))` first — that env var is auto-injected)
- [ ] Only reach for `source: GIT` + `parameters.command` if the task genuinely checks out and runs a script from an already-separate repo — then commit the script there and create/verify a Python connection pointing at it

## Before / After Example

### Prefect (before)

```python
from prefect import flow, task

@task(retries=2, retry_delay_seconds=60, timeout_seconds=600)
def compute_metrics(start_date: str, end_date: str) -> dict:
    import pandas as pd
    df = pd.read_csv("s3://my-bucket/data.csv")
    df.to_parquet("s3://my-bucket/output.parquet")
    return {"rows": len(df)}

@flow
def metrics_flow(start_date: str = "2024-01-01", end_date: str = "2024-01-02"):
    compute_metrics(start_date=start_date, end_date=end_date)
```

### Orchestra YAML (after)

The task body moves into `parameters.code` as-is — no separate script file, no Git repo, no connection needed here since nothing credentialed is involved:

```yaml
version: v1
name: metrics-flow
inputs:
  start_date:
    type: string
    default: '2024-01-01'
  end_date:
    type: string
    default: '2024-01-02'
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: compute_metrics
        connection: null
        parameters:
          source: INLINE
          code: |
            import os
            import pandas as pd

            start_date = os.environ["START_DATE"]
            end_date = os.environ["END_DATE"]

            df = pd.read_csv("s3://my-bucket/data.csv")
            df.to_parquet("s3://my-bucket/output.parquet")
            print(f"Processed {len(df)} rows")
          build_command: 'pip install pandas'
          python_version: '3.12'
          environment_variables: '{"START_DATE": "${{ inputs.start_date }}", "END_DATE": "${{ inputs.end_date }}"}'
        configuration:
          retries: 2
          retry_delay: 1
          timeout: 600
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Default to `source: INLINE`, not `GIT`** — the `@task` body already lives in the flow code; pasting it into `parameters.code` is a direct match. Reach for `GIT` only when the task genuinely runs a script from an already-separate repo.
- Prefect blocks inside `@task` (e.g. `SnowflakeConnector.load(...)`) must be **replaced with `os.environ` reads** — credentials live on an Orchestra connection's secrets, not in YAML; only wire `connection:` if this is actually needed
- Return values don't auto-pass between tasks — use `set_outputs: true` on the task and call `client.set_output("key", value)` in `code`, where `client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))` (`set_output` is a method on the client, not a bare importable function); see `prefect-data-passing-to-orchestra`
- **Consuming a JSON-shaped upstream output in `code`?** Wrap the `${{ ...OUTPUTS[...] }}` substitution in Python triple-quotes for `json.loads()`, not single/double — see `prefect-data-passing-to-orchestra`'s Gotchas for why (raw text substitution, no escaping).
- `cache_key_fn` has no Orchestra equivalent — drop it
- `retry_delay_seconds` in Prefect becomes `retry_delay` in Orchestra `configuration:` — **the unit changes, not just the key name**: Orchestra's `retry_delay` is integer MINUTES, so divide by 60 (round up). Capped at 120 (minutes); the API rejects anything higher with "Delay between retries cannot be greater than 120 minutes."
- `timeout_seconds` becomes `timeout` (seconds) in `configuration:`
- **`environment_variables` is a single JSON string, not a nested map** — e.g. `'{"KEY": "value"}'`, not a YAML mapping under that key
- Secrets and API keys go on an Orchestra connection's environment, never hardcoded in YAML or `code`
- **No specific connection mapped** — `connection: null` is the norm for `INLINE` tasks with no external credentials. Never invent a placeholder like `${{ ENV.PYTHON_CONNECTION }}` just to fill the field
- **`source: GIT` still exists for real Git-backed scripts** — if the task checks out and runs a script from a separate repo, commit it there and reference by relative path via `command:`, with a Python connection pointing at that repo

## References

- https://docs.getorchestra.io/docs/integrations/python
- https://docs.prefect.io/v3/develop/write-tasks

## Before converting: check it isn't actually a Slack task

A `@task` whose entire body posts a message to Slack — even a plain one that imports `slack_sdk` directly and calls `WebClient(...).chat_postMessage(...)`, with no `prefect_slack` import at all — is **not** generic Python. It belongs on `integration: SLACK` / `integration_job: SEND_SLACK_MESSAGE`, not `PYTHON_EXECUTE_SCRIPT`. See `slack-prefect-to-orchestra` before converting any task that formats and sends a Slack (or Teams/PagerDuty) message as its main job, even if called as a normal step in the `@flow` body rather than an `on_failure=`/`on_completion=` hook.

## Adding Alerts

If the Prefect code sends notifications via `on_failure=`/`on_completion=` hooks or Prefect Automations, replace those with an `alerts:` block instead of converting the hook function as a task — see `prefect-alerts-to-orchestra` for all notification patterns.
