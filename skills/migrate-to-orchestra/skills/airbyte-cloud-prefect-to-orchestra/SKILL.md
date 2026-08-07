---
name: airbyte-cloud-prefect-to-orchestra
description: "Use this skill when the user wants to convert a Prefect task that syncs Airbyte Cloud — AirbyteConnection block, trigger_sync_run_and_wait_for_completion, or AirbyteSyncResult — into an equivalent Orchestra pipeline task targeting Airbyte Cloud. Triggers: any mention of migrating or rewriting Prefect Airbyte tasks to Orchestra; any Prefect flow code importing from prefect_airbyte pointed at Airbyte Cloud."
---

## Overview

This skill converts Prefect `prefect_airbyte` tasks targeting Airbyte Cloud (api.airbyte.com) into Orchestra pipeline tasks using `integration: AIRBYTE_CLOUD` and `integration_job: AIRBYTE_CLOUD_JOB`. It covers sync and reset job types.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `AirbyteConnection.load("...")` | `connection:` | Orchestra Airbyte Cloud connection slug |
| `connection_id` (UUID) | `parameters.connection_id` | Copy verbatim — UUID string |
| `trigger_sync_run_and_wait_for_completion()` | `parameters.job_type: sync` | Orchestra always waits; no separate polling needed |
| `reset_cache=True` | `parameters.job_type: reset` | Full reload of the connection |
| Prefect block host `api.airbyte.com` | `integration: AIRBYTE_CLOUD` | Any other host → use `airbyte-server-prefect-to-orchestra` |

## Orchestra YAML Structure

```yaml
integration: AIRBYTE_CLOUD
integration_job: AIRBYTE_CLOUD_JOB
name: sync-task
connection: airbyte_cloud_prod_12345
parameters:
  connection_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
  job_type: sync
depends_on: []
condition: null
tags: []
```

## Conversion Steps

- [ ] Confirm the Prefect block's `airbyte_server_host` is `api.airbyte.com` — if not, use `airbyte-server-prefect-to-orchestra`
- [ ] Set `integration: AIRBYTE_CLOUD`
- [ ] Set `integration_job: AIRBYTE_CLOUD_JOB`
- [ ] Copy the `connection_id` UUID verbatim into `parameters.connection_id`
- [ ] Map `reset_cache=True` → `parameters.job_type: reset`; otherwise `parameters.job_type: sync`
- [ ] Set `connection:` to the Orchestra Airbyte Cloud connection slug (ask operator if unknown)
- [ ] Set `depends_on:` from upstream task dependencies

## Before / After Example

### Prefect (before)

```python
from prefect import flow, task
from prefect_airbyte.connections import AirbyteConnection
from prefect_airbyte.flows import trigger_sync_run_and_wait_for_completion

@flow
def sync_airbyte_cloud():
    airbyte_conn = AirbyteConnection.load("my-airbyte-cloud-block")
    trigger_sync_run_and_wait_for_completion(
        airbyte_connection=airbyte_conn,
        connection_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    )
```

### Orchestra YAML (after)

```yaml
version: v1
name: sync-airbyte-cloud
pipeline:
  stage-airbyte-sync:
    tasks:
      task-airbyte-sync:
        integration: AIRBYTE_CLOUD
        integration_job: AIRBYTE_CLOUD_JOB
        name: Sync Airbyte Cloud
        connection: airbyte_cloud_prod_12345
        parameters:
          connection_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
          job_type: sync
        depends_on: []
        condition: null
        tags: []
    depends_on: []
```

## Gotchas

- The UUID goes in `parameters.connection_id`, not on the `connection:` field — `connection:` is the Orchestra connection slug, not the Airbyte connection UUID
- Host `api.airbyte.com` = Airbyte Cloud; any other host = Airbyte Server (use `airbyte-server-prefect-to-orchestra`)
- `AIRBYTE_CLOUD_JOB` polls internally — no separate sensor task needed
- `job_type` is required; omitting it will cause a validation error

## References

- [Orchestra Airbyte Cloud integration](https://docs.getorchestra.io/docs/integrations/airbyte_cloud)
- [prefect-airbyte](https://prefecthq.github.io/prefect-airbyte/)

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
