---
name: python-dagster-to-orchestra
description: "Use this skill when the user wants to convert a Dagster @op or @asset that runs arbitrary Python (computation, API calls, pandas, boto3) into an equivalent Orchestra Python pipeline task. Triggers: any mention of migrating or rewriting Dagster ops/assets to Orchestra; plain @op / @asset / @multi_asset functions containing Python logic (not a dedicated integration like dbt/Airbyte/Fivetran)."
---

# Python: Dagster -> Orchestra Conversion

## Overview

Dagster's `@op` and `@asset` run Python inline in the Dagster executor — the logic lives right there in the op/asset function, not in a separate repo checked out at runtime. For how Orchestra's Python integration handles that (the `INLINE`/`GIT` execution modes and the default choice), see the shared reference: [`../../references/python-task.md`](../../references/python-task.md#inline-vs-git-execution-modes).

## Parameter Mapping

| Dagster concept | Orchestra YAML field | Notes |
|---|---|---|
| `@op` / `@asset` function body | `parameters.code` (inline) | Copy the body verbatim — no extraction to a file/repo needed |
| top-level `import`s beyond the stdlib | `parameters.build_command` | e.g. `build_command: 'pip install pandas boto3'` |
| `Config` fields | Inline as literals in `code`, or `parameters.environment_variables` + `os.environ` | |
| injected resources (S3/Snowflake/etc.) | instantiate in `code` + connection secrets | No DI in Orchestra scripts — set `connection:` only if the code needs credentials from one |
| Python version | `parameters.python_version` | e.g. `'3.12'` |
| asset key / op name | `name:` | Human-readable task name |
| in-memory return value | `set_outputs` or external storage | See dagster-io-managers-to-orchestra |
| upstream asset/op deps | `depends_on:` | |

## Orchestra YAML Structure

See the shared [Task YAML skeleton](../../references/python-task.md#task-yaml-skeleton) for the full field shape (`integration: PYTHON`, `integration_job: PYTHON_EXECUTE_SCRIPT`, `source: INLINE`, `code`, `build_command`, `python_version`). Set `name:` to the op/asset name.

Use `source: GIT` + `command:` only when the op/asset genuinely runs a script that already lives in a separate Git repo — not by default just because Orchestra supports it.

## Conversion Steps

1. **Copy the function body verbatim** into `parameters.code` — no extraction to a standalone file, no Git commit.
2. **List non-stdlib imports** and set `parameters.build_command: 'pip install <package> ...'`.
3. **Replace resources** — anything the op received via context (clients, credentials) must be instantiated directly in `code`, reading secrets from env vars set by an Orchestra connection (only wire `connection:` if this is actually needed).
4. **Handle config** — `Config` fields become inline literals in `code`, or `parameters.environment_variables` read with `os.environ`.
5. **Reproduce IO-manager persistence** — if Dagster persisted the return value via an IO manager, write to S3/warehouse explicitly in `code`.
6. **Wire dependencies**.

If instead the op/asset genuinely checks out and runs a script from a separate Git repo, use `source: GIT`, and create/verify an Orchestra Python connection pointing at that repo (URL, branch, credentials).

## Before / After Example

### Dagster (before)

```python
from dagster import asset, Config

class MetricsConfig(Config):
    start_date: str
    end_date: str

@asset
def metrics(config: MetricsConfig):
    import pandas as pd
    df = pd.read_csv("s3://my-bucket/data.csv")
    # ... processing using config.start_date / config.end_date ...
    df.to_parquet("s3://my-bucket/output.parquet")
    return df
```

### Extracted script (`scripts/compute_metrics.py`)

```python
import os
import pandas as pd

start_date = os.environ["START_DATE"]
end_date = os.environ["END_DATE"]

df = pd.read_csv("s3://my-bucket/data.csv")
# ... processing ...
df.to_parquet("s3://my-bucket/output.parquet")
```

### Orchestra YAML (after)

The op body moves into `parameters.code` as-is — no separate script file, no Git repo, no connection needed here since nothing credentialed is involved:

```yaml
version: v1
name: my-pipeline
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: metrics
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

- **Default to `source: INLINE`, not `GIT`** — the op/asset body already lives in the Dagster code; pasting it into `parameters.code` is a direct match. Reach for `GIT` only when the op genuinely runs a script from an already-separate repo.
- **Resources / dependency injection** — Dagster ops receive clients via context; the inlined code instantiates its own and reads credentials from connection-injected env vars (only wire `connection:` if this is actually needed).
- **`Config` -> inline literals or `environment_variables`** — read with `os.environ` (see the shared reference for the [`environment_variables` JSON-string format](../../references/python-task.md#environment_variables-is-a-json-string)).
- **In-memory inputs/outputs** — Orchestra tasks do not share Python objects; pass small values via `set_outputs` or stage data in S3/warehouse.
- **Consuming a JSON-shaped upstream output in `code`?** See the shared reference's [triple-quote guidance](../../references/python-task.md#consuming-a-json-shaped-upstream-output) — and `dagster-io-managers-to-orchestra`'s Gotchas for why the substitution needs it (raw text substitution, no escaping).
- **IO managers** — replicate any IO-manager persistence explicitly in `code`.
- **`@multi_asset`** — one op producing several assets becomes one Orchestra PYTHON task.

For the `connection: null` default and secrets handling, and using `source: GIT` for real Git-backed scripts, see the shared reference: [`../../references/python-task.md`](../../references/python-task.md).

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/python
- Orchestra Execute Script: https://docs.getorchestra.io/docs/integrations/utility/python/execute-script/
- Dagster assets: https://docs.dagster.io/concepts/assets/software-defined-assets
- Dagster ops: https://docs.dagster.io/concepts/ops-jobs-graphs/ops

## Before converting: check it isn't actually a Slack task

An `@op`/`@asset` whose entire body posts a message to Slack — even one that calls `SlackResource`'s client or raw `slack_sdk`/`WebClient.chat_postMessage(...)` directly, not via a run-status sensor or hook — is **not** generic Python. It belongs on `integration: SLACK` / `integration_job: SEND_SLACK_MESSAGE`, not a plain Python task. See `slack-dagster-to-orchestra`'s "Option 2: Explicit Slack Pipeline Task" before converting any op/asset whose main job is formatting and sending a Slack message, even when it's a normal mid-run step rather than a failure/success hook.

## Adding Alerts

If the Dagster code sends notifications via a run failure sensor, `make_slack_on_run_failure_sensor`, or op success/failure hooks, replace those with an `alerts` block in the pipeline YAML. Alerts fire based on overall pipeline status and support Slack, Email, PagerDuty, Microsoft Teams, and Webhook destinations.

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

Valid statuses: `FAILED`, `SUCCEEDED`, `CANCELLED`, `WARNING`, `SKIPPED`. Multiple alerts with different destinations are supported — each needs a unique `name`. See the `slack-dagster-to-orchestra` skill for full schema details.