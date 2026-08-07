---
name: fivetran-prefect-to-orchestra
description: "Use this skill when the user wants to convert a Prefect task that syncs Fivetran — FivetranConnector block, trigger_sync_and_wait_for_completion, or FivetranSyncResult — into an equivalent Orchestra pipeline task. Triggers: any mention of migrating or rewriting Prefect Fivetran tasks to Orchestra; any Prefect flow code importing from prefect_fivetran."
---

## Overview

Converts Prefect Fivetran sync tasks into Orchestra pipeline YAML. A Prefect `FivetranConnector` block plus `trigger_sync_and_wait_for_completion()` maps directly to a single Orchestra task with `integration: FIVETRAN` and `integration_job: FIVETRAN_SYNC_ALL`. Orchestra always waits for sync completion — no additional configuration is required.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `FivetranConnector.load("...")` | `connection:` | Stores API key + secret; create in Connectors → Fivetran |
| `connector_id` (slug) | `parameters.connector_id` | Short slug (e.g. `bronzing_regularly`), not a UUID |
| `trigger_sync_and_wait_for_completion()` | (always waits) | No extra config needed; Orchestra polls until done |
| `FivetranSyncResult` return value | (discard) | No downstream pass-through needed; use alerts for status |

## Orchestra YAML Structure

```yaml
version: v1
name: fivetran-flow
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

## Conversion Steps

- [ ] Identify the `FivetranConnector.load("...")` block name — this becomes `connection:`
- [ ] Find the `connector_id` slug in the Prefect block or Fivetran UI (Connectors page URL)
- [ ] Set `integration: FIVETRAN` and `integration_job: FIVETRAN_SYNC_ALL`
- [ ] Set `parameters.connector_id` to the slug
- [ ] Add credentials to the Orchestra Fivetran connection (Connectors → Fivetran → Connect) — never put API keys in YAML
- [ ] If a dbt task follows, add it as a separate task in `stage-001` (or a new stage) with `depends_on: [task-001]`
- [ ] Add an `alerts:` block if the Prefect flow had on_failure/on_completion hooks (see `prefect-alerts-to-orchestra`)

## Before / After Example

### Prefect (before)

```python
from prefect import flow
from prefect_fivetran import FivetranConnector
from prefect_fivetran.fivetran import trigger_sync_and_wait_for_completion

@flow
def fivetran_flow():
    connector = FivetranConnector.load("fivetran-prod")
    result = trigger_sync_and_wait_for_completion(fivetran_connector=connector)
```

### Orchestra YAML (after)

```yaml
version: v1
name: fivetran-flow
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

- `connector_id` is a **slug** (e.g. `bronzing_regularly`), not a UUID — find it on the Fivetran Connectors page in the URL or connector details
- `api_key` and `api_secret` go on the Orchestra Fivetran connection object, **never** in the pipeline YAML
- If dbt follows Fivetran in the same Prefect flow, model it as a separate task (`integration: DBT_CORE`, `integration_job: DBT_CORE_EXECUTE`) with `depends_on: [task-001]`
- Orchestra does not surface `FivetranSyncResult` — if downstream tasks consumed sync metadata, remove that dependency or use Orchestra pipeline outputs
- A single Orchestra task replaces both the block load and the trigger call — there is no two-step equivalent

## References

- https://docs.getorchestra.io/docs/integrations/fivetran
- https://prefecthq.github.io/prefect-fivetran/

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
