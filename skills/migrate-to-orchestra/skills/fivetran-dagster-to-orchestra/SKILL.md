---
name: fivetran-dagster-to-orchestra
description: "Use this skill when the user wants to convert a Dagster Fivetran integration — FivetranResource / FivetranWorkspace, build_fivetran_assets, load_fivetran_asset_specs, or fivetran_assets — into an equivalent Orchestra pipeline task. Triggers: any mention of migrating or rewriting Dagster Fivetran assets/resources to Orchestra; Dagster code importing from dagster_fivetran."
---

# Fivetran: Dagster -> Orchestra Conversion

## Overview

In Dagster, Fivetran is integrated via `dagster-fivetran`: a `FivetranResource` (or `FivetranWorkspace`) holds the API key/secret and `build_fivetran_assets` turns each connector into assets. Materializing the assets triggers the connector sync. In Orchestra the equivalent is a single **Sync** task under the `FIVETRAN` integration — trigger and wait in one task.

## Parameter Mapping

| Dagster concept | Orchestra YAML field | Notes |
|---|---|---|
| `FivetranResource(api_key=, api_secret=)` | `connection:` | Orchestra Fivetran connection (stores API key + secret) |
| `build_fivetran_assets(connector_id=...)` | `parameters.connector_id` | Connector slug — copy verbatim |
| asset materialization | _(always waits)_ | Orchestra always waits for completion |
| `destination_tables=[...]` | _(not needed)_ | Whole connector synced |
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
        integration: FIVETRAN
        integration_job: FIVETRAN_SYNC_ALL
        name: <descriptive name>
        connection: <orchestra-fivetran-connection-name>
        parameters:
          connector_id: <fivetran-connector-id>
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

1. **Find the Fivetran resource** — locate `FivetranResource` and the `connector_id` passed to `build_fivetran_assets`.
2. **Verify/create the Orchestra connection** — Settings -> Connections -> Fivetran with API key + secret. Note its name.
3. **Replace assets with a task block** — one task per connector.
4. **Wire dependencies** — convert upstream asset deps to `depends_on:`.

## Before / After Example

### Dagster (before)

```python
from dagster import Definitions, EnvVar
from dagster_fivetran import FivetranResource, build_fivetran_assets

fivetran = FivetranResource(
    api_key=EnvVar("FIVETRAN_API_KEY"), api_secret=EnvVar("FIVETRAN_API_SECRET"),
)
salesforce_assets = build_fivetran_assets(
    connector_id="bronzing_regularly",
    destination_tables=["accounts", "opportunities"],
)
defs = Definitions(assets=salesforce_assets, resources={"fivetran": fivetran})
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

- **Connector ID format** — short alphanumeric slugs (e.g. `bronzing_regularly`), not UUIDs.
- **Asset-per-table granularity is dropped** — Orchestra triggers the whole connector sync as one task.
- **One connector per task** — each connector becomes its own Orchestra task.
- **API key + secret on the connection** — the Dagster `EnvVar` credentials map to the Orchestra Fivetran connection, not the YAML.
- **dbt after Fivetran** — chained `@dbt_assets` downstream become a separate `DBT_CORE` task with `depends_on` on the Fivetran task.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/fivetran
- Dagster Fivetran: https://docs.dagster.io/integrations/libraries/fivetran
- dagster-fivetran API: https://docs.dagster.io/api/python-api/libraries/dagster-fivetran

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