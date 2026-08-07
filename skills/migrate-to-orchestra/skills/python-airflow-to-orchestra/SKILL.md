---
name: python-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that uses PythonOperator or PythonVirtualenvOperator into an equivalent Orchestra Python pipeline task. Triggers: any mention of migrating or rewriting PythonOperator tasks to Orchestra; Airflow DAG code using PythonOperator, PythonVirtualenvOperator, ExternalPythonOperator, or @task decorator tasks."
---

# Python: Airflow → Orchestra Conversion

## Overview

Airflow's `PythonOperator` runs a callable inline in the worker — the code lives right there in the DAG file, not in some separate repo the DAG checks out at runtime. Orchestra's Python integration (**Execute Script**) has two modes: `source: INLINE` runs code pasted directly into the task's `parameters.code`, and `source: GIT` runs a file checked out from a Git repo via `parameters.command`. **Default to `INLINE`** — it's the direct match for what Airflow already does (code inline in the DAG), needs no Git repo or connection wiring, and skips a whole conversion step. Only reach for `GIT` when the callable itself checks out and runs a script that already lives in a separate repo (rare for `PythonOperator` — more of a `BashOperator` pattern).

## Parameter Mapping

| Airflow concept | Orchestra YAML field | Notes |
|---|---|---|
| `python_callable` (the function) | `parameters.code` (inline) | Copy the callable body verbatim — no extraction to a separate file/repo needed |
| top-level `import`s beyond the stdlib | `parameters.build_command` | e.g. `build_command: 'pip install pandas boto3'` — installs before the code runs |
| `op_kwargs` / `op_args` | Inline into `code` as literals, or `parameters.environment_variables` + `os.environ.get(...)` in the code | |
| `requirements` (PythonVirtualenvOperator) | `parameters.build_command` | `pip install -r requirements` list as a `pip install ...` command |
| Python version | `parameters.python_version` | e.g. `'3.12'` |
| `task_id` | `name:` | Human-readable task name |
| `provide_context=True` / `**context` | Not applicable | Orchestra context is available via environment variables |
| `pool` / `queue` | Not applicable | Managed by Orchestra |
| upstream `>>` chains | `depends_on:` | |

## Orchestra YAML Structure

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: <task_id value from Airflow>
        connection: null                          # usually null for INLINE — no repo/creds needed unless the code itself needs a specific connection's secrets
        parameters:
          source: INLINE                           # default — code already lives in the DAG, no Git repo involved
          code: |
            <callable body, copied verbatim>
          build_command: 'pip install pandas'      # optional — only for non-stdlib imports
          python_version: '3.12'
        depends_on: []
        condition: null
        tags: []
```

Use `source: GIT` + `command:` (see `python-dagster-to-orchestra`/`python-prefect-to-orchestra` for the field shape) only when the Airflow task's callable genuinely runs a script that's already checked into a separate Git repo — not just because Orchestra supports it.

## Conversion Steps

1. **Copy the callable body verbatim** into `parameters.code` — no need to extract it into a standalone file or commit anything to Git.
2. **List non-stdlib imports** (`pandas`, `boto3`, etc.) and set `parameters.build_command: 'pip install <package> ...'`.
3. **Handle `op_kwargs`** — either inline the values as literals in the code, or read them via `os.environ.get(...)` and set `parameters.environment_variables`.
4. **Set `connection`** — leave `null` unless the code needs credentials/secrets that belong on a specific Orchestra connection (e.g. it instantiates a boto3/Snowflake client using connection-injected env vars).
5. **Wire dependencies**.

If instead the Airflow task genuinely checks out and runs a script from a separate Git repo (not the DAG repo itself), use `source: GIT`, commit/reference the script there, and create/verify an Orchestra Python connection pointing at that repo (URL, branch, credentials) as described for `source: GIT` tasks.

## Before / After Example

### Airflow DAG (before)

```python
from airflow.operators.python import PythonOperator

def compute_metrics(start_date: str, end_date: str) -> None:
    import pandas as pd
    df = pd.read_csv("s3://my-bucket/data.csv")
    # ... processing ...
    df.to_parquet("s3://my-bucket/output.parquet")

metrics_task = PythonOperator(
    task_id="compute_metrics",
    python_callable=compute_metrics,
    op_kwargs={"start_date": "{{ ds }}", "end_date": "{{ tomorrow_ds }}"},
)
```

### Orchestra YAML (after)

The callable body moves into `parameters.code` as-is — no separate script file, no Git repo, no connection needed here since nothing credentialed is involved:

```yaml
version: v1
name: my-pipeline
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
            # ... processing ...
            df.to_parquet("s3://my-bucket/output.parquet")
          build_command: 'pip install pandas'
          python_version: '3.12'
          environment_variables: '{"START_DATE": "2024-01-01", "END_DATE": "2024-01-02"}'
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Default to `source: INLINE`, not `GIT`** — the callable's code already lives in the DAG file; pasting it into `parameters.code` is a direct match. Don't reach for `source: GIT` (extracting to a script, committing it, wiring a connection) just because that's the other mode Orchestra supports — it's extra work with no source-fidelity benefit unless the callable genuinely runs a script from an external repo.
- **Consuming a JSON-shaped upstream output (converted XCom) in `code`?** Wrap the `${{ ...OUTPUTS[...] }}` substitution in Python triple-quotes for `json.loads()`, not single/double — see `airflow-xcoms-to-orchestra`'s Gotchas for why (raw text substitution, no escaping).
- **Airflow context / Jinja templates**: Airflow macros like `{{ ds }}` are not available in Orchestra. Replace with static values, pipeline variables, or read from environment variables set by Orchestra.
- **Inline lambdas / closures**: if the callable uses closures or imports from elsewhere in the same DAG file, inline those into `code` too so it's self-contained.
- **`@task` decorator (TaskFlow API)**: same approach — copy the decorated function body into `code` verbatim.
- **`PythonVirtualenvOperator` requirements**: list them in `build_command` as a `pip install ...` command.
- **`environment_variables` is a JSON string, not a nested map** — it's a single string field on the parameters model (e.g. `'{"KEY": "value"}'`), not a YAML mapping.
- **No specific connection mapped**: `connection: null` is the norm for `INLINE` tasks with no external credentials. Only set a specific connection if the code needs secrets injected from one (e.g. a boto3/Snowflake client reading connection-provided env vars) — never invent a placeholder like `${{ ENV.PYTHON_CONNECTION }}` just to fill the field.
- **Secrets**: do not hardcode credentials in `code`. If secrets are needed, use an Orchestra connection's injected env vars.
- **`source: GIT` still exists for real Git-backed scripts** — if the Airflow task checks out and runs a script from a separate repo, use `GIT` + `parameters.command`, and create/verify a Python connection pointing at that repo (URL, branch, credentials). Orchestra supports sparse checkout for large monorepos, configurable on the connection.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/python
- Orchestra Execute Script: https://docs.getorchestra.io/docs/integrations/utility/python/execute-script/

## Before converting: check it isn't actually a Slack task

A `PythonOperator`/`@task` whose entire function body posts a message to Slack — even one that calls `slack_sdk.WebClient(...).chat_postMessage(...)` directly instead of a dedicated Slack operator — is **not** generic Python. It belongs on `integration: SLACK` / `integration_job: SEND_SLACK_MESSAGE`, not `PYTHON_EXECUTE_SCRIPT`. See `slack-airflow-to-orchestra` before converting any task whose main job is formatting and sending a Slack message, even when it's a normal mid-DAG step rather than a callback.

## Adding Alerts

If the Airflow DAG uses `on_failure_callback` or `on_success_callback` for Slack/email notifications, replace those with an `alerts` block in the pipeline YAML. Alerts fire based on overall pipeline status and support Slack, Email, PagerDuty, Microsoft Teams, and Webhook destinations.

```yaml
version: v1
name: my-pipeline

alerts:
  - name: on-failure
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Optional context message.'

  - name: on-success
    statuses:
      - SUCCEEDED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

pipeline:
  # ... tasks unchanged
```

Valid statuses: `FAILED`, `SUCCEEDED`, `CANCELLED`, `WARNING`, `SKIPPED`. Multiple alerts with different destinations are supported — each needs a unique `name`. See the `slack-airflow-to-orchestra` skill for full schema details.
