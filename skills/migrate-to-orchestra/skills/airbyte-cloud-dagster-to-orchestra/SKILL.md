---
name: airbyte-cloud-dagster-to-orchestra
description: "Use this skill when the user wants to convert a Dagster integration that syncs Airbyte Cloud — AirbyteCloudResource, build_airbyte_assets, load_airbyte_cloud_asset_specs, or airbyte_assets — into an equivalent Orchestra pipeline task targeting Airbyte Cloud. Triggers: any mention of migrating or rewriting Dagster Airbyte assets/resources to Orchestra; any Dagster code importing from dagster_airbyte pointed at Airbyte Cloud."
---

# Airbyte Cloud: Dagster -> Orchestra Conversion

## Overview

In Dagster, Airbyte Cloud is integrated via `dagster-airbyte`: an `AirbyteCloudResource` holds credentials and `build_airbyte_assets` (or `load_airbyte_cloud_asset_specs`) turns each Airbyte connection into Dagster assets. Materializing those assets triggers the sync. In Orchestra the equivalent is a single **Sync** task under the `AIRBYTE_CLOUD` integration. Orchestra always polls for completion; there is no separate sensor.

## Parameter Mapping

| Dagster concept | Orchestra YAML field | Notes |
|---|---|---|
| `AirbyteCloudResource(api_key=...)` | `connection:` | Orchestra connection of type Airbyte Cloud (stores the API key) |
| `build_airbyte_assets(connection_id=...)` | `parameters.connection_id` | Airbyte Cloud connection UUID — copy verbatim |
| asset materialization | `parameters.job_type: sync` | Use `reset` for a full reload |
| `destination_tables=[...]` | _(not needed)_ | Orchestra syncs the whole connection |
| asset key / name | `name:` | Human-readable task name |
| upstream asset deps | `depends_on:` | Upstream Orchestra task UUIDs/names |

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
        name: <descriptive name>
        connection: <orchestra-airbyte-cloud-connection-name>
        parameters:
          connection_id: <airbyte-connection-uuid>
          job_type: sync          # required: "sync" or "reset"
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

1. **Find the Airbyte resource** — locate `AirbyteCloudResource` and the `connection_id` passed to `build_airbyte_assets` / asset specs.
2. **Find/create the Orchestra connection** — in Orchestra Settings -> Connections, confirm an Airbyte Cloud connection exists. Its name goes in `connection:`.
3. **Replace the asset(s) with a task block** — one Orchestra task per Airbyte `connection_id`, copying the UUID verbatim.
4. **Set `job_type`** — `sync` normally, `reset` if the Dagster code performs a reset.
5. **Wire dependencies** — convert upstream asset dependencies to `depends_on:`.

## Before / After Example

### Dagster (before)

```python
from dagster import Definitions, EnvVar
from dagster_airbyte import AirbyteCloudResource, build_airbyte_assets

airbyte = AirbyteCloudResource(api_key=EnvVar("AIRBYTE_CLOUD_API_KEY"))

airbyte_assets = build_airbyte_assets(
    connection_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    destination_tables=["users"],
)

defs = Definitions(assets=airbyte_assets, resources={"airbyte": airbyte})
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
        name: sync_users
        connection: airbyte_cloud_prod_12345
        parameters:
          connection_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
          job_type: sync
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Airbyte Cloud vs Server** — `AIRBYTE_CLOUD` is the managed SaaS product; use `AIRBYTE_SERVER` for self-hosted. In Dagster, `AirbyteCloudResource` -> Cloud, `AirbyteResource` -> Server.
- **One connection per task** — `build_airbyte_assets` binds to a single `connection_id` -> one Orchestra task. Multiple connections -> multiple tasks.
- **Asset-per-table granularity is dropped** — Orchestra triggers the whole connection sync as one task; per-table lineage is not represented in the YAML.
- **`connection_id` is a UUID** — copy verbatim; do not confuse with the Dagster resource key or the Orchestra connection name.
- **API key lives on the connection** — the Dagster `EnvVar` API key maps to the Orchestra Airbyte Cloud connection, never the YAML.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/airbyte_cloud
- Dagster Airbyte: https://docs.dagster.io/integrations/libraries/airbyte
- dagster-airbyte API: https://docs.dagster.io/api/python-api/libraries/dagster-airbyte

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