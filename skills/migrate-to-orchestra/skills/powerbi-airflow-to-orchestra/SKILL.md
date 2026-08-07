---
name: powerbi-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that uses PowerBIDatasetRefreshOperator (apache-airflow-providers-microsoft-azure, module airflow.providers.microsoft.azure.operators.powerbi) into an equivalent Orchestra pipeline task targeting Power BI. Triggers: any mention of migrating or rewriting Power BI Airflow tasks to Orchestra; Airflow DAG code containing PowerBIDatasetRefreshOperator, PowerBIHook, conn_id=\"powerbi_default\", or dataset_id/group_id refresh parameters. Must be read before finalizing any Orchestra YAML that contains integration: POWER_BI."
---

# Power BI: Airflow → Orchestra Conversion

## Overview

Airflow's `PowerBIDatasetRefreshOperator` (from `airflow.providers.microsoft.azure.operators.powerbi`) triggers a Power BI dataset (semantic model) refresh via an Azure service-principal connection and — being deferrable — waits for the refresh to complete using the Power BI REST API. In Orchestra the equivalent is a task under the `POWER_BI` integration.

There is no dedicated Airflow operator for **dataflow** refreshes in `apache-airflow-providers-microsoft-azure` as of this writing. A dataflow refresh in an Airflow DAG is typically hand-rolled as a `PythonOperator`/`HttpOperator` call against the Power BI REST API (`POST /groups/{groupId}/dataflows/{dataflowId}/refreshes`). Do not invent an operator name for this — treat any such hand-rolled task as a candidate for `POWER_BI_REFRESH_DATAFLOW` based on what the code is actually calling.

## Parameter Mapping

| Airflow parameter | Orchestra YAML field | Notes |
|---|---|---|
| `conn_id` (e.g. `powerbi_default`) | `connection:` | Orchestra Power BI connection (Azure service principal) |
| `dataset_id` | `parameters.dataset_id` | Required for `POWER_BI_REFRESH_DATASET` |
| `group_id` | `parameters.workspace_id` | **Airflow's `group_id` is Orchestra's `workspace_id`** — same Power BI workspace GUID, renamed field. Leave `null` unless this task's workspace differs from the one configured on the Orchestra connection — see Gotchas |
| (hand-rolled dataflow call) `dataflowId` | `parameters.dataflow_id` | Required for `POWER_BI_REFRESH_DATAFLOW` instead of `dataset_id` |
| n/a (Airflow has no equivalent knob) | `parameters.refresh_type` | Optional — one of `Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment` (mirrors Power BI's own `DatasetRefreshType` enum). Leave `null`/omit unless the DAG explicitly requests a non-default refresh type. |
| n/a | `parameters.apply_refresh_policy` | Optional boolean, defaults to `null`. Only set if the source DAG's REST call explicitly passes `applyRefreshPolicy`. |
| `task_id` | `name:` | Human-readable task name |
| upstream `>>` chains | `depends_on:` | |

## Orchestra YAML Structure

Dataset refresh:

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATASET
        name: <task_id value from Airflow>
        connection: <orchestra-power-bi-connection-name>
        parameters:
          dataset_id: <power-bi-dataset-guid>     # required
          workspace_id: null                        # optional — leave null to use the workspace on the connection; only set if this task's group_id differs from it
          refresh_type: null                        # optional enum — see mapping table
          apply_refresh_policy: null                 # optional bool
        depends_on: []
        condition: null
        tags: []
```

Dataflow refresh:

```yaml
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATAFLOW
        parameters:
          dataflow_id: <power-bi-dataflow-guid>    # required
          workspace_id: null                        # optional — leave null unless this task's group_id differs from the connection's workspace
```

## Conversion Steps

1. **Identify the Airflow task** — locate `PowerBIDatasetRefreshOperator`. Note `conn_id`, `dataset_id`, and `group_id`.
2. **Create/verify the Orchestra connection** — Settings → Connections → Power BI. Power BI's API is gated behind an Azure AD service principal (tenant ID, client/application ID, client secret) with Power BI API permissions — the same credential shape as the `Azure` connection type described in `airflow-connections-to-orchestra` (tenant, client ID, client secret), just scoped to Power BI. Reuse that pattern rather than a database-style connection.
3. **Replace operator with task block** — use the dataset YAML above; rename `group_id` → `workspace_id`.
4. **Check for a hand-rolled dataflow refresh** — if the DAG separately calls the Power BI REST API for a dataflow (not a dataset), convert that task to `POWER_BI_REFRESH_DATAFLOW` with `dataflow_id` instead of `dataset_id`.
5. **Wire dependencies** — convert `>>` chains to `depends_on:`.

## Before / After Example

Source: `research/dag_sources/reporting_powerbi_slack.py`.

### Airflow DAG (before)

```python
from airflow.providers.microsoft.azure.operators.powerbi import (
    PowerBIDatasetRefreshOperator,
)
from airflow.providers.slack.operators.slack import SlackAPIPostOperator

refresh_dashboard_dataset = PowerBIDatasetRefreshOperator(
    task_id="refresh_dashboard_dataset",
    conn_id="powerbi_default",
    dataset_id=POWERBI_DATASET_ID,
    group_id=POWERBI_WORKSPACE_ID,
)

notify_slack = SlackAPIPostOperator(
    task_id="notify_slack",
    slack_conn_id="slack_default",
    channel=SLACK_CHANNEL,
    text=(
        ":bar_chart: Power BI dashboard refreshed successfully "
        "(dag: {{ dag.dag_id }}, run: {{ run_id }})."
    ),
)

refresh_dashboard_dataset >> notify_slack
```

### Orchestra YAML (after)

`POWERBI_DATASET_ID` is an `os.getenv()`-with-default value identifying which distinct dataset gets refreshed — a real per-environment knob, so per `airflow-dag-structure-to-orchestra`'s `params`/`Variable.get()` → `inputs:` rule it becomes a pipeline input. `SLACK_CHANNEL` is different: it's just a static destination read via `os.getenv()` with nothing in the DAG varying it, so the known value goes in directly as a literal rather than through `inputs:` or `${{ ENV.* }}` (see `slack-airflow-to-orchestra`). `POWERBI_WORKSPACE_ID` is the same single workspace used by every task, which belongs on the Orchestra Power BI connection itself, so it's left `null` here rather than plumbed through as another input:

```yaml
version: v1
name: reporting-powerbi-slack

inputs:
  powerbi_dataset_id:
    type: string
    default: my-dataset-id

pipeline:
  stage-001:
    tasks:
      refresh-dashboard-dataset:
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATASET
        name: refresh_dashboard_dataset
        connection: power_bi_prod_12345
        parameters:
          dataset_id: ${{ inputs.powerbi_dataset_id }}
          workspace_id: null   # single workspace used throughout; configure it on the connection instead
        depends_on: []
        condition: null
        tags: []
      notify-slack:
        integration: SLACK
        integration_job: SEND_SLACK_MESSAGE
        name: notify_slack
        connection: slack_default_54321
        parameters:
          channel_name: '#analytics'   # known, static destination — used directly, not via inputs/ENV
          text: ':bar_chart: Power BI dashboard refreshed successfully.'
        depends_on:
          - refresh-dashboard-dataset
        condition: null
        tags: []
```

## Gotchas

- **`additionalProperties: false`** — Orchestra's `POWER_BI_REFRESH_DATASET` and `POWER_BI_REFRESH_DATAFLOW` parameter models reject any key not listed above. Don't invent parameters like `notify_option` or `refresh_mode` just because the Power BI REST API or an Airflow XCom pattern references them.
- **Dataset vs. dataflow use different ID field names** — `POWER_BI_REFRESH_DATASET` takes `dataset_id`; `POWER_BI_REFRESH_DATAFLOW` takes `dataflow_id`. Never mix them (`dataflow_id` is invalid on the dataset job and vice versa).
- **`group_id` → `workspace_id` rename** — Airflow's `PowerBIDatasetRefreshOperator(group_id=...)` is the same GUID as Orchestra's `workspace_id`.
- **Don't reflexively carry `workspace_id` through as `${{ ENV.POWERBI_WORKSPACE_ID }}` or an input** — if every task uses the same single `group_id`, that workspace belongs on the Orchestra Power BI connection itself (configured once at connection setup), not repeated per task. Leave `parameters.workspace_id: null` by default — Orchestra falls back to the connection's workspace. Only set an explicit value when a specific task's `group_id` genuinely differs from the connection's workspace, since dataset/dataflow IDs are only unique within a workspace.
- **`refresh_type` values are case-sensitive and fixed** — only `Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment` are valid (mirrors Microsoft's own `DatasetRefreshType` enum exactly). Leave it `null` unless the source DAG explicitly requests one.
- **No dedicated Airflow dataflow operator** — if you see a DAG calling the dataflow refresh REST endpoint via `PythonOperator`/`HttpOperator`/`SimpleHttpOperator`, that's the `POWER_BI_REFRESH_DATAFLOW` equivalent; don't look for a `PowerBIDataflowRefreshOperator` — it doesn't exist in the provider package.
- **Polling collapses into one task** — Airflow's deferrable operator polls the refresh status itself; Orchestra's task already waits for completion, so there's nothing extra to convert.
- **Connection is an Azure service principal, not a Power BI username/password** — legacy Power BI username/password auth is deprecated for automation; make sure the service principal has been added to the target workspace with the right permissions before wiring the connection.
- **Never fabricate `${{ ENV.POWERBI_DATASET_ID }}` for `dataset_id`** — use the actual dataset GUID whenever it's visible in the source (hardcoded, or `os.getenv(..., "default-id")` with a real default — see the `inputs:` example above). Only use an `${{ ENV.VAR }}` reference when the source itself reads the ID from that exact environment variable with no fallback. An invented reference produces a pipeline that fails with no matching value to set in Orchestra.

## References

- Orchestra Power BI integration: https://docs.getorchestra.io/docs/integrations/power_bi
- Airflow Microsoft Azure provider (Power BI operators): https://airflow.apache.org/docs/apache-airflow-providers-microsoft-azure/stable/operators/powerbi.html
- Power BI REST API — refresh dataset: https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset
- Power BI REST API — refresh dataflow: https://learn.microsoft.com/en-us/rest/api/power-bi/dataflows/refresh-dataflow
- See `airflow-connections-to-orchestra` for the Azure service-principal connection pattern.

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
