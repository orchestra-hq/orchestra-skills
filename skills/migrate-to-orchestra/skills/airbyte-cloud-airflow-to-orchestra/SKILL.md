---
name: airbyte-cloud-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that uses AirbyteTriggerSyncOperator or AirbyteSensor (apache-airflow-providers-airbyte) into an equivalent Orchestra pipeline task targeting Airbyte Cloud. Triggers: any mention of migrating, converting, or rewriting Airflow Airbyte tasks to Orchestra; any Airflow DAG code containing AirbyteTriggerSyncOperator or AirbyteSensor pointed at Airbyte Cloud."
---

# Airbyte Cloud: Airflow → Orchestra Conversion

## Overview

An Airflow `AirbyteTriggerSyncOperator` task triggers a connection sync in Airbyte Cloud and optionally waits for completion. In Orchestra the equivalent is a **Sync** task under the `AIRBYTE_CLOUD` integration. Orchestra always polls for completion; there is no separate sensor.

## Parameter Mapping

| Airflow parameter | Orchestra YAML field | Notes |
|---|---|---|
| `airbyte_conn_id` | `connection:` | The name of the Orchestra connection to Airbyte Cloud |
| `connection_id` | `parameters.connection_id` | Airbyte Cloud connection UUID — copy verbatim |
| `asynchronous` flag | `parameters.job_type` | Set `job_type: sync` for normal sync (or `reset` for full reload) |
| `asynchronous=False` (default) | _(no field needed)_ | Orchestra always waits for completion |
| `asynchronous=True` | Not directly supported | Remove sensor task; Orchestra handles polling |
| `timeout` / `wait_seconds` | _(managed by Orchestra)_ | Configure timeout on the Orchestra task UI/YAML |
| `task_id` | `name:` | Human-readable task name |
| `depends_on` (upstream task IDs) | `depends_on:` | List of upstream Orchestra task UUIDs or names |

## Orchestra YAML Structure

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: AIRBYTE_CLOUD
        integration_job: AIRBYTE_CLOUD_JOB
        name: <task_id value from Airflow>
        connection: <orchestra-airbyte-cloud-connection-name>
        parameters:
          connection_id: <airbyte-connection-uuid>
          job_type: sync          # required: "sync" or "reset"
        depends_on: []   # replace with upstream task names/UUIDs
        condition: null
        tags: []
```

## Conversion Steps

1. **Identify the Airflow task** — locate `AirbyteTriggerSyncOperator` in the DAG. Note `connection_id` and `airbyte_conn_id`.
2. **Find/create the Orchestra connection** — in Orchestra Settings → Connections, confirm a connection of type *Airbyte Cloud* exists. Its name goes in `connection:`.
3. **Replace operator with task block** — use the YAML structure above, copying `connection_id` verbatim.
4. **Drop any paired `AirbyteSensor`** — Orchestra's sync task already polls; the sensor is redundant.
5. **Wire dependencies** — convert Airflow `>>` / `set_upstream` chains to `depends_on:` lists.
6. **Remove Airflow-only fields** — `retries`, `retry_delay`, `pool` have no direct Orchestra equivalent; configure retries on the Orchestra task if needed.

## Before / After Example

### Airflow DAG (before)

```python
from airflow.providers.airbyte.operators.airbyte import AirbyteTriggerSyncOperator

sync_users = AirbyteTriggerSyncOperator(
    task_id="sync_users_table",
    airbyte_conn_id="airbyte_cloud_prod",
    connection_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    asynchronous=False,
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
        integration: AIRBYTE_CLOUD
        integration_job: AIRBYTE_CLOUD_JOB
        name: sync_users_table
        connection: airbyte_cloud_prod_12345
        parameters:
          connection_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
          job_type: sync
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Airbyte Cloud vs Airbyte Server**: `AIRBYTE_CLOUD` is for the managed SaaS product. For self-hosted Airbyte use `AIRBYTE_SERVER` (see separate skill).
- **Multiple connections per DAG**: each `AirbyteTriggerSyncOperator` becomes its own Orchestra task block.
- **`asynchronous=True` + `AirbyteSensor` pattern**: merge both into a single Orchestra sync task; drop the sensor.
- **Connection UUID format**: the Airbyte `connection_id` is a UUID. Do not confuse with the Airflow connection ID (a string name).

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/airbyte_cloud
- Airflow provider: https://airflow.apache.org/docs/apache-airflow-providers-airbyte/stable/operators/airbyte.html

## Adding Alerts to Airbyte Tasks

If the Airflow DAG uses `on_failure_callback` or `on_success_callback` to send Slack (or other) notifications when the Airbyte sync fails or succeeds, replace those with an `alerts` block in the pipeline YAML:

```yaml
version: v1
name: my-pipeline

alerts:
  - name: airbyte-sync-failed
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Airbyte sync failed — check connection in Airbyte dashboard.'

  - name: airbyte-sync-succeeded
    statuses:
      - SUCCEEDED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

pipeline:
  stage-001:
    tasks:
      task-001:
        integration: AIRBYTE_CLOUD
        integration_job: AIRBYTE_CLOUD_JOB
        # ...
```

See the `slack-airflow-to-orchestra` skill for full `AlertModel` schema and destination options (Email, PagerDuty, Teams, Webhook).
