---
name: airbyte-server-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that uses AirbyteTriggerSyncOperator or AirbyteSensor pointed at a self-hosted Airbyte Server instance into an equivalent Orchestra pipeline task. Triggers: any mention of migrating or converting Airflow self-hosted Airbyte tasks to Orchestra; Airflow DAG code with AirbyteTriggerSyncOperator using a host/port pointing to an on-prem or self-managed Airbyte deployment."
---

# Airbyte Server: Airflow → Orchestra Conversion

## Overview

Self-hosted Airbyte uses the same `AirbyteTriggerSyncOperator` / `AirbyteSensor` as Airbyte Cloud in Airflow, but the Airflow connection points to your own host. In Orchestra the equivalent is a **Sync** task under the `AIRBYTE_SERVER` integration, which uses a separate connection type that stores the server host URL.

## Parameter Mapping

| Airflow parameter | Orchestra YAML field | Notes |
|---|---|---|
| `airbyte_conn_id` | `connection:` | The name of the Orchestra connection to Airbyte Server (stores host + API key) |
| `connection_id` | `parameters.connection_id` | Airbyte connection UUID — copy verbatim |
| `asynchronous` / `AirbyteSensor` | _(not needed)_ | Orchestra always polls; drop the sensor |
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
        integration: AIRBYTE_SERVER
        integration_job: AIRBYTE_SERVER_JOB
        name: <task_id value from Airflow>
        connection: <orchestra-airbyte-server-connection-name>
        parameters:
          connection_id: <airbyte-connection-uuid>
          job_type: sync          # required: "sync" or "reset"
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

1. **Identify the Airflow task** — locate `AirbyteTriggerSyncOperator`. Note the `airbyte_conn_id` (which holds the host) and the `connection_id` UUID.
2. **Create/verify the Orchestra connection** — in Orchestra Settings → Connections, create a connection of type *Airbyte Server* pointing to your host URL and API credentials. Note its name.
3. **Replace operator with task block** — use the YAML above.
4. **Drop any paired `AirbyteSensor`** — redundant in Orchestra.
5. **Wire dependencies**.

## Before / After Example

### Airflow DAG (before)

```python
from airflow.providers.airbyte.operators.airbyte import AirbyteTriggerSyncOperator
from airflow.providers.airbyte.sensors.airbyte import AirbyteSensor

trigger = AirbyteTriggerSyncOperator(
    task_id="trigger_crm_sync",
    airbyte_conn_id="airbyte_self_hosted",
    connection_id="bb112233-4455-6677-8899-aabbccddeeff",
    asynchronous=True,
)

wait = AirbyteSensor(
    task_id="wait_crm_sync",
    airbyte_conn_id="airbyte_self_hosted",
    airbyte_job_id=trigger.output,
    poke_interval=60,
)

trigger >> wait
```

### Orchestra YAML (after)

```yaml
version: v1
name: my-pipeline
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: AIRBYTE_SERVER
        integration_job: AIRBYTE_SERVER_JOB
        name: trigger_crm_sync
        connection: airbyte_self_hosted_12345
        parameters:
          connection_id: bb112233-4455-6677-8899-aabbccddeeff
          job_type: sync
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Cloud vs Server**: Use `AIRBYTE_SERVER` only for self-hosted. For Airbyte Cloud SaaS use `AIRBYTE_CLOUD` (see separate skill).
- **Trigger + Sensor merges into one task**: both the trigger and the sensor collapse into a single Orchestra task.
- **Host URL**: Orchestra's Airbyte Server connection stores `http(s)://host:port` — confirm the Orchestra connection matches the Airflow connection's host value.
- **API version**: Airbyte Server connections in Orchestra may use the v1 Config API or the newer OSS API — verify in Orchestra connection settings.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/airbyte_server
- Airflow provider: https://airflow.apache.org/docs/apache-airflow-providers-airbyte/stable/operators/airbyte.html

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
