---
name: dagster-cross-job-to-orchestra
description: "Use this skill when a Dagster project creates dependencies between jobs/code locations or triggers downstream runs: @run_status_sensor (on SUCCESS) yielding RunRequest, @asset_sensor watching another job's asset, cross-code-location asset dependencies (SourceAsset / AssetKey across locations), or a sensor that launches another job. Triggers: any sensor/op that launches another Dagster job, any cross-job or cross-code-location asset dependency, any RunRequest targeting a different job."
---

# Dagster Cross-Job Triggering -> Orchestra

## Overview

Dagster cross-job patterns — `@run_status_sensor` launching a downstream job, `@asset_sensor` on an upstream asset, and cross-code-location asset dependencies — all have Orchestra equivalents. Orchestra provides two mechanisms:

1. **`TRIGGER_PIPELINE` task** — an explicit pipeline step that triggers another pipeline and waits for it to complete. Use when one pipeline must trigger another mid-flow and wait.

2. **`trigger_events:` block** — event-driven triggering at the pipeline root. When an upstream pipeline completes, this pipeline starts automatically. This is the cleaner equivalent of `@run_status_sensor` / `@asset_sensor`.

---

## `@run_status_sensor` (SUCCESS, launching a job) -> `trigger_events:` (preferred)

```python
# Dagster
@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    monitored_jobs=[nightly_elt],
    request_job=daily_report,
)
def trigger_report_on_elt_success(context):
    return RunRequest(run_config={"ops": {"build": {"config": {"env": "prod"}}}})
```

```yaml
# Orchestra — daily-report pipeline
version: v1
name: daily-report

trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-nightly-elt-pipeline"
    statuses: [SUCCEEDED, WARNING]
    run_inputs:
      env: prod

pipeline:
  ...
```

**TriggerEventModel fields:**

| Field | Required | Notes |
|---|---|---|
| `type` | yes | Always `pipeline` |
| `pipeline_id` | yes | UUID of the upstream pipeline, or `"*"` for any |
| `statuses` | no | Default `[SUCCEEDED, WARNING]` |
| `run_inputs` | no | Inputs passed to the triggered run |

Multiple entries = OR logic (fires when any upstream completes).

---

## Explicit launch-and-wait -> `ORCHESTRA` + `TRIGGER_PIPELINE`

When a pipeline must trigger another and wait before continuing:

```yaml
task-001:
  integration: ORCHESTRA
  integration_job: TRIGGER_PIPELINE
  name: trigger_reporting
  parameters:
    pipeline_id: "uuid-of-daily-reporting-pipeline"
    run_inputs:
      env: prod
    branch: null
  depends_on: []
  condition: null
  tags: []
```

| Parameter | Required | Notes |
|---|---|---|
| `pipeline_id` | yes | UUID from the Orchestra URL |
| `run_inputs` | no | Inputs for the triggered pipeline |
| `branch` | no | Git branch override |

**`TRIGGER_PIPELINE` always waits** for the triggered pipeline before proceeding — there is no fire-and-forget. If the Dagster sensor only launches (does not wait), prefer `trigger_events:` on the downstream pipeline.

---

## `@asset_sensor` and cross-code-location deps -> `trigger_events:`

An `@asset_sensor` watching an upstream materialization, or a cross-code-location asset dependency, maps to `trigger_events:` keyed on the upstream pipeline:

```yaml
trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-producer-pipeline"
    statuses: [SUCCEEDED]
```

---

## Before / After Example

### Dagster (before)

```python
from dagster import run_status_sensor, DagsterRunStatus, RunRequest, Definitions

@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    monitored_jobs=[nightly_elt],
    request_job=daily_report,
)
def trigger_report_on_elt_success(context):
    return RunRequest(run_config={"ops": {"build": {"config": {"env": "prod"}}}})

defs = Definitions(jobs=[nightly_elt, daily_report], sensors=[trigger_report_on_elt_success])
```

### Orchestra YAML (after)

```yaml
# nightly-elt pipeline (separate YAML)
version: v1
name: nightly-elt
pipeline:
  ...

---
# daily-report pipeline — triggered by nightly-elt completion
version: v1
name: daily-report

trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-nightly-elt-pipeline"
    statuses: [SUCCEEDED, WARNING]
    run_inputs:
      env: prod

pipeline:
  stage-build:
    tasks:
      build-report:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: build_report
        connection: my_python_conn_12345
        parameters:
          command: 'python scripts/build_report.py'
          python_version: '3.12'
        depends_on: []
        condition: null
        tags: []
```

---

## Gotchas

- **`@run_status_sensor(SUCCESS)` launching a job -> `trigger_events:`** — cleaner than polling.
- **Launch-and-wait mid-flow -> `TRIGGER_PIPELINE` task**.
- **`pipeline_id` is a UUID** — from the Orchestra URL, not the pipeline name.
- **`TRIGGER_PIPELINE` always waits** — no fire-and-forget; prefer `trigger_events:` if the sensor only launches.
- **`@asset_sensor` / cross-code-location deps -> `trigger_events:`**.
- **`trigger_events:` uses OR logic** — chain pipelines for AND logic.
- **`RunRequest(run_config=...)` -> `run_inputs`**.
- **`statuses` default** — `SUCCEEDED` + `WARNING` if omitted.
- **Circular dependencies** — Orchestra validates against circular trigger chains.

## Adding Alerts

```yaml
alerts:
  - name: on-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
```

## References

- Orchestra TRIGGER_PIPELINE: https://docs.getorchestra.io/docs/integrations/orchestra
- Orchestra trigger_events: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Dagster run status sensors: https://docs.dagster.io/concepts/automation/sensors#run-status-sensors
- Dagster asset sensors: https://docs.dagster.io/concepts/automation/asset-sensors
