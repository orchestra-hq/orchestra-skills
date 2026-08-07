---
name: airflow-cross-dag-to-orchestra
description: "Use this skill when an Airflow DAG uses TriggerDagRunOperator, ExternalTaskSensor, or SubDagOperator to create cross-DAG dependencies or trigger downstream pipelines. Triggers: any DAG with external_dag_id=, trigger_dag_id=, SubDagOperator, or Airflow Datasets."
---

# Airflow Cross-DAG Triggering → Orchestra

## Overview

Airflow cross-DAG patterns — `TriggerDagRunOperator`, `ExternalTaskSensor`, `SubDagOperator`, Datasets — all have Orchestra equivalents. Orchestra provides two mechanisms:

1. **`TRIGGER_PIPELINE` task** — an explicit pipeline step that triggers another pipeline and waits for it to complete. Equivalent to `TriggerDagRunOperator(wait_for_completion=True)`.

2. **`trigger_events:` block** — event-driven triggering at the pipeline root. When an upstream pipeline completes, this pipeline starts automatically. Equivalent to `ExternalTaskSensor` + DAG scheduling, but cleaner.

---

## TriggerDagRunOperator → ORCHESTRA + TRIGGER_PIPELINE

```python
# Airflow
trigger_downstream = TriggerDagRunOperator(
    task_id="trigger_reporting",
    trigger_dag_id="daily_reporting",
    conf={"date": "{{ ds }}", "env": "prod"},
    wait_for_completion=True,
    execution_date="{{ execution_date }}",
)
```

```yaml
# Orchestra
task-001:
  integration: ORCHESTRA
  integration_job: TRIGGER_PIPELINE
  name: trigger_reporting
  parameters:
    pipeline_id: "uuid-of-daily-reporting-pipeline"   # UUID from Orchestra UI
    run_inputs:                                         # optional — equivalent to conf={}
      date: "${{ ORCHESTRA.CURRENT_TIME }}"
      env: prod
    branch: null                                        # optional — git branch override
  depends_on: []
  condition: null
  tags: []
```

**TRIGGER_PIPELINE parameters:**

| Parameter | Required | Notes |
|---|---|---|
| `pipeline_id` | ✅ | UUID of the pipeline to trigger (find in Orchestra URL) |
| `run_inputs` | ❌ | Key-value dict passed as inputs to the triggered pipeline |
| `branch` | ❌ | Git branch to use for the triggered pipeline run |

**Key difference from Airflow:** `TRIGGER_PIPELINE` always waits for the triggered pipeline to complete before proceeding. There is no `wait_for_completion=False` equivalent.

---

## ExternalTaskSensor → `trigger_events:` (preferred)

When an upstream pipeline is in Orchestra and you want to start a pipeline automatically on its completion, use `trigger_events:` at the pipeline root — no sensor polling needed.

```python
# Airflow
wait_for_elt = ExternalTaskSensor(
    task_id="wait_for_upstream_elt",
    external_dag_id="nightly_elt",
    external_task_id=None,   # wait for whole DAG
    poke_interval=60,
    timeout=3600,
)
```

```yaml
# Orchestra — event-driven trigger
version: v1
name: daily-reporting

trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-nightly-elt-pipeline"
    statuses: [SUCCEEDED, WARNING]   # null defaults to SUCCEEDED + WARNING
    run_inputs:                       # optional inputs to pass to this pipeline run
      triggered_by: upstream_elt

pipeline:
  ...
```

**TriggerEventModel fields:**

| Field | Required | Notes |
|---|---|---|
| `type` | ✅ | Always `pipeline` |
| `pipeline_id` | ✅ | UUID of the upstream pipeline, or `"*"` for any pipeline |
| `statuses` | ❌ | Which completion statuses trigger this pipeline. Default: `[SUCCEEDED, WARNING]` |
| `run_inputs` | ❌ | Input values to pass to the triggered run |

**Multiple upstream triggers (OR logic):**

```yaml
trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-pipeline-a"
  - type: pipeline
    pipeline_id: "uuid-of-pipeline-b"
  # fires when EITHER pipeline-a OR pipeline-b completes
```

---

## SubDagOperator → Flatten or Separate Pipeline

Airflow Sub-DAGs are mostly an anti-pattern — they create scheduling complexity and have known issues. In Orchestra:

**Option A — Flatten into stages**: If the sub-DAG is small and tightly coupled to the parent, convert its tasks into additional stages in the same Orchestra pipeline.

**Option B — Separate pipeline**: If the sub-DAG represents a reusable or independently schedulable unit, convert it to its own Orchestra pipeline and trigger it with `TRIGGER_PIPELINE`.

```python
# Airflow
subdag_op = SubDagOperator(
    task_id="process_subdag",
    subdag=create_subdag(dag_id, "process_subdag", default_args),
)
```

```yaml
# Orchestra — Option B: separate pipeline + trigger
# In the parent pipeline:
task-trigger-subpipeline:
  integration: ORCHESTRA
  integration_job: TRIGGER_PIPELINE
  name: process_subpipeline
  parameters:
    pipeline_id: "uuid-of-process-pipeline"
  depends_on: []
```

---

## Airflow Datasets → `trigger_events:` with any pipeline

Airflow Datasets (2.4+) trigger DAGs when an upstream DAG updates a dataset. In Orchestra, use `trigger_events:` with the relevant upstream pipeline UUID.

```python
# Airflow
my_dataset = Dataset("s3://my-bucket/orders/")

with DAG("producer", schedule=None) as producer_dag:
    update_task = PythonOperator(..., outlets=[my_dataset])

with DAG("consumer", schedule=[my_dataset]) as consumer_dag:
    ...
```

```yaml
# Orchestra — consumer pipeline
trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-producer-pipeline"
    statuses: [SUCCEEDED]
```

---

## Before / After Example

### Airflow DAG (before)

```python
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor

with DAG("orchestrator") as dag:

    wait_for_elt = ExternalTaskSensor(
        task_id="wait_for_elt",
        external_dag_id="nightly_elt",
    )

    trigger_report = TriggerDagRunOperator(
        task_id="trigger_report",
        trigger_dag_id="daily_report",
        conf={"env": "prod"},
        wait_for_completion=True,
    )

    wait_for_elt >> trigger_report
```

### Orchestra YAML (after)

```yaml
# nightly-elt pipeline (separate YAML)
version: v1
name: nightly-elt
pipeline:
  ...   # existing ELT tasks

---
# orchestrator pipeline — triggered by nightly-elt completion
version: v1
name: orchestrator

trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-nightly-elt-pipeline"
    statuses: [SUCCEEDED, WARNING]

pipeline:
  stage-trigger-report:
    tasks:
      trigger-report:
        integration: ORCHESTRA
        integration_job: TRIGGER_PIPELINE
        name: trigger_daily_report
        parameters:
          pipeline_id: "uuid-of-daily-report-pipeline"
          run_inputs:
            env: prod
        depends_on: []
        condition: null
        tags: []
    depends_on: []
```

---

## Gotchas

- **`pipeline_id` is a UUID** — find it in the Orchestra UI pipeline URL (e.g. `app.getorchestra.io/pipelines/xxxxxxxx-xxxx-...`). It's not the pipeline name.
- **`TRIGGER_PIPELINE` always waits** — unlike Airflow's `wait_for_completion=False` option, Orchestra always waits for the triggered pipeline before proceeding.
- **`trigger_events:` uses OR logic** — any single entry firing starts the pipeline. For AND logic (wait for both pipeline A and pipeline B), chain: trigger_events fires pipeline B, and pipeline A is a `TRIGGER_PIPELINE` task at the start of pipeline B.
- **Sub-DAGs → prefer flattening** — if the sub-DAG is <5 tasks, just add them as stages in the parent pipeline. The trigger overhead of a separate pipeline isn't worth it for small workloads.
- **`statuses` default** — if omitted, `trigger_events` fires on `SUCCEEDED` and `WARNING` only. Explicitly set `statuses: [SUCCEEDED]` if you don't want WARNING runs to trigger downstream.
- **Circular dependencies** — Orchestra validates that pipelines don't form circular trigger chains. Plan your pipeline graph before converting.

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
