---
name: powerbi-dagster-to-orchestra
description: "Use this skill when the user wants to convert a Dagster Power BI integration — PowerBIWorkspace, PowerBIServicePrincipal/PowerBIToken, load_powerbi_asset_specs, build_semantic_model_refresh_asset_definition, or a custom resource/op calling power_bi.trigger_and_poll_refresh — into an equivalent Orchestra pipeline task targeting Power BI. Triggers: any mention of migrating or rewriting Dagster Power BI assets to Orchestra; Dagster code importing from dagster_powerbi, or a custom op/resource wrapping the Power BI REST refresh API for a dataset or dataflow. Must be read before finalizing any Orchestra YAML that contains integration: POWER_BI."
---

# Power BI: Dagster -> Orchestra Conversion

## Overview

Dagster has an official `dagster-powerbi` integration for **semantic model (dataset)** refreshes: a `PowerBIWorkspace` (configured with `PowerBIServicePrincipal` or `PowerBIToken` credentials plus a `workspace_id`) is used with `load_powerbi_asset_specs` to snapshot the workspace as asset specs, and `build_semantic_model_refresh_asset_definition` turns a semantic-model asset spec into a materializable asset that triggers a refresh (internally calling `power_bi.trigger_and_poll_refresh(dataset_id)`).

**Critical: `load_powerbi_asset_specs` auto-discovers every dataset/dataflow/report/dashboard from the *live* Power BI workspace by calling the Power BI API when Dagster's definitions load.** The actual dataset GUIDs are almost never written anywhere in the static Python source — they only exist as live data returned by that API call. Each discovered dataset's GUID is exposed as `spec.metadata["dagster-powerbi/id"]` at runtime, but that's a live value, not something you can read off the page. This means: **don't expect to find a real dataset GUID sitting in the source code.** Only trust a literal you can actually see (a hardcoded GUID, or one read from an env var/Variable with a visible default). If the code just loops over all discovered specs with no such visible value, the real GUID genuinely isn't determinable from source — see Conversion Steps and Gotchas for what to do instead of guessing.

`dagster-powerbi` has **no documented support for dataflow refresh** — if a Dagster codebase refreshes a Power BI dataflow, it is almost always a hand-rolled `@op` or custom `ConfigurableResource` that calls the Power BI REST API directly (`POST /groups/{groupId}/dataflows/{dataflowId}/refreshes`) and polls the transaction status. Treat that pattern the same way you'd treat any custom REST-wrapping resource — there's no dedicated Dagster class to look for.

In Orchestra, both cases map to the `POWER_BI` integration.

## Parameter Mapping

| Dagster concept | Orchestra YAML field | Notes |
|---|---|---|
| `PowerBIWorkspace(workspace_id=...)` | `connection:` (workspace configured on the Orchestra connection) | Leave `parameters.workspace_id` blank/`null` unless a specific task targets a different workspace than the one configured on the connection — see Gotchas |
| `PowerBIServicePrincipal(tenant_id=, client_id=, client_secret=)` | `connection:` | Orchestra Power BI connection (Azure service principal) |
| semantic model asset's dataset ID (`spec.metadata["dagster-powerbi/id"]` at runtime / `trigger_and_poll_refresh(dataset_id)`) | `parameters.dataset_id` | Required for `POWER_BI_REFRESH_DATASET`. Usually **not visible in static source** — see Overview and Gotchas before assuming you can extract a real value |
| custom op's `dataflow_id` argument | `parameters.dataflow_id` | Required for `POWER_BI_REFRESH_DATAFLOW` instead of `dataset_id` |
| n/a (Dagster always does a default refresh) | `parameters.refresh_type` | Optional — one of `Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment`. Leave `null` unless the custom code explicitly requests a specific `DatasetRefreshType`. |
| n/a | `parameters.apply_refresh_policy` | Optional boolean, defaults to `null` |
| asset key / op name | `name:` | Human-readable task name |
| upstream asset deps | `depends_on:` | |

## Orchestra YAML Structure

Dataset (semantic model) refresh:

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATASET
        name: <descriptive name>
        connection: <orchestra-power-bi-connection-name>
        parameters:
          dataset_id: <power-bi-dataset-guid>     # required
          workspace_id: null                        # optional — leave null to use the workspace on the connection; only set if this task targets a different workspace
          refresh_type: null                        # optional enum
          apply_refresh_policy: null                 # optional bool
        depends_on: []
        condition: null
        tags: []
```

Dataflow refresh (from a custom resource/op, since `dagster-powerbi` doesn't cover this):

```yaml
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATAFLOW
        parameters:
          dataflow_id: <power-bi-dataflow-guid>    # required
          workspace_id: null                        # optional — leave null unless this task targets a different workspace than the connection's
```

## Conversion Steps

1. **Find the workspace + assets** — locate `PowerBIWorkspace(...)`, its credentials (`PowerBIServicePrincipal` or `PowerBIToken`), and `load_powerbi_asset_specs`. Note the `workspace_id`.
2. **Find the refresh trigger** — look for `build_semantic_model_refresh_asset_definition(...)` (dataset/semantic-model case) or a custom `@op`/`ConfigurableResource` calling the Power BI REST refresh endpoint directly (dataflow case, or a hand-rolled dataset case).
3. **Determine whether a real dataset GUID is actually visible** — check whether the code filters `power_bi_specs` down to one/a few *specific* datasets using a value you can see (a hardcoded GUID, a name/GUID compared via a custom `DagsterPowerBITranslator`, or an env var/Variable with a visible default). If it does, use that visible value. **If it doesn't** — i.e. it builds a refresh asset for every spec matching a tag like `dagster-powerbi/asset_type == "semantic_model"`, with no per-dataset filter — the real GUID(s) only exist live in the Power BI workspace and can't be read from this source. Don't invent one (not a fake GUID, not a fake `${{ ENV.* }}` reference). Instead, emit the task with a clearly-marked placeholder and a `# MANUAL:` comment asking the user to fill in the real dataset GUID(s) from their Power BI workspace — and note that since Dagster refreshes *every* discovered dataset dynamically but Orchestra has no equivalent dynamic discovery, this may need to become one Orchestra task per real dataset rather than one task total.
4. **Create/verify the Orchestra connection** — Settings → Connections → Power BI, using the same Azure service-principal credentials (`tenant_id`, `client_id`, `client_secret`) as `PowerBIServicePrincipal`. If the Dagster code uses `PowerBIToken` instead, note that Orchestra's Power BI connection is service-principal based — you'll need to provision a service principal for the migration.
5. **Replace the asset with a task block** — use the workspace GUID plus whatever dataset/dataflow GUID resulted from step 3.
6. **Wire dependencies** — convert asset dependencies (`deps=[...]`, `AssetIn`) to `depends_on:`.

## Before / After Example

### Dagster (before)

```python
from dagster import Definitions, EnvVar, AssetKey
from dagster_powerbi import (
    PowerBIWorkspace,
    PowerBIServicePrincipal,
    load_powerbi_asset_specs,
    build_semantic_model_refresh_asset_definition,
)

power_bi = PowerBIWorkspace(
    credentials=PowerBIServicePrincipal(
        client_id=EnvVar("POWERBI_CLIENT_ID"),
        client_secret=EnvVar("POWERBI_CLIENT_SECRET"),
        tenant_id=EnvVar("POWERBI_TENANT_ID"),
    ),
    workspace_id=EnvVar("POWERBI_WORKSPACE_ID"),
)

power_bi_specs = load_powerbi_asset_specs(power_bi)
semantic_model_assets = [
    build_semantic_model_refresh_asset_definition(resource_key="power_bi", spec=spec)
    for spec in power_bi_specs
    if spec.tags.get("dagster-powerbi/asset_type") == "semantic_model"
]

defs = Definitions(
    assets=[*power_bi_specs, *semantic_model_assets],
    resources={"power_bi": power_bi},
)
```

### Orchestra YAML (after)

This source has no per-dataset filter — `semantic_model_assets` builds a refresh definition for *every* spec Dagster discovers live from the workspace, so no real GUID is visible anywhere in this code. Don't invent one; flag it and tell the user what's actually needed:

```yaml
version: v1
name: my-pipeline
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATASET
        name: refresh_dashboard_dataset
        connection: power_bi_prod_12345
        parameters:
          dataset_id: REPLACE_WITH_REAL_DATASET_GUID   # MANUAL: load_powerbi_asset_specs discovers datasets live from the Power BI API — no GUID is visible in this source. Look up the real dataset GUID(s) in Power BI (workspace → dataset settings → URL) and replace this. This Dagster code refreshes every discovered semantic model, so you likely need one Orchestra task per real dataset, not just one.
          workspace_id: null   # the connection is scoped to this workspace already; no per-task override needed here
        depends_on: []
        condition: null
        tags: []
```

If instead the source filters `power_bi_specs` down to a specific dataset — by a hardcoded GUID, or by comparing `spec.metadata["dagster-powerbi/id"]` / a custom `DagsterPowerBITranslator`'s output against a literal name/GUID you can see — use that visible value directly as `dataset_id` and skip the `# MANUAL:` flag.

## Gotchas

- **`additionalProperties: false`** — Orchestra's `POWER_BI_REFRESH_DATASET` and `POWER_BI_REFRESH_DATAFLOW` parameter models reject any key not in the mapping table above. Don't carry over Dagster/Power-BI-API-only fields (e.g. `notifyOption`) as extra parameter keys.
- **Dataset vs. dataflow use different ID field names** — `POWER_BI_REFRESH_DATASET` takes `dataset_id`; `POWER_BI_REFRESH_DATAFLOW` takes `dataflow_id`. Never mix them.
- **`dagster-powerbi` only covers datasets/semantic models** — there is no `build_dataflow_refresh_asset_definition` or equivalent. A dataflow refresh in a Dagster codebase is always a hand-rolled resource/op — don't search for an official class that doesn't exist.
- **`PowerBIToken` vs. Orchestra's connection** — Orchestra's Power BI connection is provisioned as an Azure service principal; if the Dagster code authenticates with a raw API token (`PowerBIToken`), you'll need to set up a proper service principal in Azure AD before creating the Orchestra connection.
- **`refresh_type` values are case-sensitive and fixed** — only `Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment` are valid. Leave `null` unless the source code explicitly requests one.
- **Asset materialization polling collapses into one task** — `trigger_and_poll_refresh` already waits synchronously in Dagster; Orchestra's task does the same, so there's nothing extra to model.
- **Never fabricate a value for `dataset_id` — not an `${{ ENV.* }}` reference, and not a made-up-looking literal GUID either.** `load_powerbi_asset_specs` discovers datasets live from the Power BI API; the GUID (`spec.metadata["dagster-powerbi/id"]`) only exists at Dagster runtime and is essentially never written anywhere in the static source. If you can't point to an actual visible GUID/name filter in the code, don't invent one in either direction — use a `# MANUAL:`-flagged placeholder (see the Before/After example) so the user fills in the real value from their Power BI workspace instead of silently deploying a pipeline that refreshes a nonexistent or wrong dataset.
- **One Dagster asset can mean many real Orchestra tasks** — if the code builds a refresh definition for every spec matching a tag (no per-dataset filter), Dagster is refreshing *every* dataset discovered in the workspace at run time. Orchestra has no equivalent dynamic discovery — say so in the `# MANUAL:` comment, since the user likely needs one `POWER_BI_REFRESH_DATASET` task per real dataset, not the single templated task this skill can produce from source alone.
- **Don't reflexively carry `workspace_id` through as `${{ ENV.POWERBI_WORKSPACE_ID }}`** — `PowerBIWorkspace(workspace_id=...)` just scopes the whole resource to one workspace, which is exactly what the Orchestra Power BI connection is configured with at setup. If every task in the DAG uses that same single workspace, leave `parameters.workspace_id: null` — Orchestra falls back to the connection's workspace. Only set an explicit `workspace_id` value (literal, input, or real `${{ ENV.VAR }}`) when a specific task genuinely targets a *different* workspace than the connection's, since dataset/dataflow IDs are only unique within a workspace.

## References

- Orchestra Power BI integration: https://docs.getorchestra.io/docs/integrations/power_bi
- Dagster & Power BI: https://docs.dagster.io/integrations/libraries/powerbi/powerbi-pythonic
- dagster-powerbi API reference: https://docs.dagster.io/api/libraries/dagster-powerbi
- Power BI REST API — refresh dataset: https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset
- Power BI REST API — refresh dataflow: https://learn.microsoft.com/en-us/rest/api/power-bi/dataflows/refresh-dataflow
- See `dagster-connections-to-orchestra` for the Azure service-principal connection pattern.

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
