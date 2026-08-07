---
name: airbyte-server-dagster-to-orchestra
description: "Use this skill when the user wants to convert a Dagster integration that syncs a self-hosted Airbyte Server (open-source / OSS) instance — AirbyteResource (with host/port) plus build_airbyte_assets — into an equivalent Orchestra pipeline task. Triggers: any mention of migrating self-hosted Airbyte Dagster assets to Orchestra; Dagster code using dagster_airbyte AirbyteResource configured with a host/port pointing to an on-prem or self-managed Airbyte deployment."
---

# Airbyte Server: Dagster -> Orchestra Conversion

## Overview

Self-hosted Airbyte is integrated in Dagster via `dagster-airbyte`'s `AirbyteResource`, configured with a `host` and `port` pointing at your own deployment, plus `build_airbyte_assets`. In Orchestra the equivalent is a **Sync** task under the `AIRBYTE_SERVER` integration, which uses a connection type that stores the server host URL and credentials.

## Parameter Mapping

| Dagster concept | Orchestra YAML field | Notes |
|---|---|---|
| `AirbyteResource(host=, port=)` | `connection:` | Orchestra Airbyte Server connection (stores host + credentials) |
| `build_airbyte_assets(connection_id=...)` | `parameters.connection_id` | Airbyte connection UUID — copy verbatim |
| asset materialization | `parameters.job_type: sync` | `reset` for full reload |
| `destination_tables=[...]` | _(not needed)_ | Whole connection is synced |
| asset key / name | `name:` | Human-readable task name |
| upstream asset deps | `depends_on:` | Upstream task names/UUIDs |

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
        name: <descriptive name>
        connection: <orchestra-airbyte-server-connection-name>
        parameters:
          connection_id: <airbyte-connection-uuid>
          job_type: sync
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

1. **Identify the resource** — `AirbyteResource(host=..., port=...)` indicates self-hosted; note the `connection_id` from the asset build.
2. **Create/verify the Orchestra connection** — Settings -> Connections -> Airbyte Server, pointing at your host URL and credentials. Note its name.
3. **Replace assets with a task block** — one task per `connection_id`.
4. **Set `job_type`** — `sync` or `reset`.
5. **Wire dependencies**.

## Before / After Example

### Dagster (before)

```python
from dagster import Definitions, EnvVar
from dagster_airbyte import AirbyteResource, build_airbyte_assets

airbyte = AirbyteResource(
    host="airbyte.internal.mycorp.com", port="8000",
    username=EnvVar("AIRBYTE_USER"), password=EnvVar("AIRBYTE_PASSWORD"),
)
crm_assets = build_airbyte_assets(
    connection_id="bb112233-4455-6677-8899-aabbccddeeff",
    destination_tables=["contacts", "accounts"],
)
defs = Definitions(assets=crm_assets, resources={"airbyte": airbyte})
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
        name: sync_crm
        connection: airbyte_self_hosted_12345
        parameters:
          connection_id: bb112233-4455-6677-8899-aabbccddeeff
          job_type: sync
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Cloud vs Server** — use `AIRBYTE_SERVER` only for self-hosted. The Dagster tell is `AirbyteResource(host=, port=)` rather than `AirbyteCloudResource`.
- **Host URL** — the Dagster host/port maps to the Orchestra Airbyte Server connection's host URL.
- **Destination tables collapse** — many declared tables, one connection sync task.
- **API version** — self-hosted connections may use the v1 Config API or newer OSS API; verify in Orchestra.
- **Credentials on the connection** — `EnvVar` username/password map to the Orchestra connection, not the YAML.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/airbyte_server
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