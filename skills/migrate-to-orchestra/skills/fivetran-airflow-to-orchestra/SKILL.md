---
name: fivetran-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that uses FivetranOperator or FivetranSensor (apache-airflow-providers-fivetran) into an equivalent Orchestra pipeline task. Triggers: any mention of migrating or rewriting Fivetran Airflow tasks to Orchestra; Airflow DAG code containing FivetranOperator or FivetranSensor."
---

# Fivetran: Airflow → Orchestra Conversion

## Overview

Airflow's `FivetranOperator` triggers a Fivetran connector sync and optionally waits for it. `FivetranSensor` polls a running sync. In Orchestra the equivalent is a **Sync** task under the `FIVETRAN` integration — it triggers and waits in a single task.

## Parameter Mapping

| Airflow parameter | Orchestra YAML field | Notes |
|---|---|---|
| `fivetran_conn_id` | `connection:` | The name of the Orchestra connection to Fivetran (stores API key + secret) |
| `connector_id` | `parameters.connector_id` | Fivetran connector ID string — copy verbatim |
| `wait_for_completion=True` | _(always)_ | Orchestra always waits |
| `schedule_type` / `reschedule_for` | _(not needed)_ | Scheduling is handled by Orchestra pipeline schedule |
| `task_id` | `name:` | Human-readable task name |
| upstream `>>` chains | `depends_on:` | List upstream task names/UUIDs |

## Orchestra YAML Structure

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: FIVETRAN
        integration_job: FIVETRAN_SYNC_ALL
        name: <task_id value from Airflow>
        connection: <orchestra-fivetran-connection-name>
        parameters:
          connector_id: <fivetran-connector-id>
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

1. **Identify the Airflow task** — locate `FivetranOperator`. Note `connector_id` and `fivetran_conn_id`.
2. **Verify/create the Orchestra connection** — in Orchestra Settings → Connections, confirm a *Fivetran* connection exists with your API key and secret. Note its name.
3. **Replace operator with task block** — use the YAML above.
4. **Drop any paired `FivetranSensor`** — Orchestra's sync task already polls.
5. **Wire dependencies** — convert `>>` chains to `depends_on:`.
6. **Remove scheduling fields** — `reschedule_for`, `schedule_type` are Fivetran-scheduler concepts; Orchestra's pipeline schedule replaces them.

## Before / After Example

### Airflow DAG (before)

```python
from fivetran_provider_async.operators import FivetranOperator

sync_salesforce = FivetranOperator(
    task_id="sync_salesforce",
    fivetran_conn_id="fivetran_prod",
    connector_id="bronzing_regularly",
    wait_for_completion=True,
)
```

### Orchestra YAML (after)

```yaml
version: v1
name: my-pipeline
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: FIVETRAN
        integration_job: FIVETRAN_SYNC_ALL
        name: sync_salesforce
        connection: fivetran_prod_12345
        parameters:
          connector_id: bronzing_regularly
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Connector ID format**: Fivetran connector IDs are short alphanumeric slugs (e.g. `bronzing_regularly`), not UUIDs.
- **Historical sync vs incremental**: Fivetran handles this internally; there's no Orchestra parameter to control it.
- **`FivetranOperator` + `FivetranSensor` pattern**: both collapse into a single Orchestra task.
- **API key scope**: the Orchestra Fivetran connection must have permission to trigger syncs on the target connector.
- **Fivetran dbt integration**: if the Airflow DAG also runs dbt after Fivetran, keep that as a separate `DBT_CORE` task with `depends_on` pointing to the Fivetran task.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/fivetran
- Airflow provider: https://airflow.apache.org/docs/apache-airflow-providers-fivetran/stable/

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
