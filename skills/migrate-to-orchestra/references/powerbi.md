# Orchestra Power BI task — shared reference

Canonical Orchestra-side syntax for the `POWER_BI` integration's task shape, shared by
`powerbi-airflow-to-orchestra`, `powerbi-dagster-to-orchestra`, and `powerbi-prefect-to-orchestra`.
Each of those skills covers the source-specific mapping (which Airflow operator / Dagster asset /
Prefect task pattern produces which Orchestra task, and how to recognize one in source); this file
is the Orchestra side only — the part that's identical regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the per-source "how do I
recognize a Power BI refresh in this source" test (`PowerBIDatasetRefreshOperator` vs.
`PowerBIWorkspace`/`load_powerbi_asset_specs` vs. hand-rolled `msal`+`requests`), since the source
vocabulary genuinely differs per orchestrator; the parameter-mapping tables (source construct ->
Orchestra field), since their left-hand column is inherently source-specific; the Conversion
Steps/Checklist and Gotchas sections, since each mixes in source-specific mechanics throughout
rather than being byte-identical; the Before/After examples, since they translate real source code;
and any sentence that names another orchestrator or a sibling skill.

Source of truth for both parameter models: `PowerBIRefreshDatasetParametersModel` /
`PowerBIRefreshDataflowParametersModel` in the pipeline schema
(`skills/orchestra/references/orchestra/schemas/tasks/integrations/POWER_BI/`). Both set
`additionalProperties: false` — there is no `workspace_id` and no `apply_refresh_policy` field on
either one; don't invent them (an earlier version of these skills did, before this reference existed
— if you see either field anywhere, it's wrong).

## Power BI task YAML shape

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
        name: <descriptive task name>
        connection: <orchestra-power-bi-connection-name>
        parameters:
          dataset_id: <power-bi-dataset-guid>   # required, only field besides refresh_type
          refresh_type: null                      # optional enum — see below
        depends_on: []
        condition: null
        tags: []
```

Dataflow refresh — same shape, `integration_job: POWER_BI_REFRESH_DATAFLOW` and `dataflow_id`
instead of `dataset_id`. `refresh_type` does **not** exist on this job — `dataflow_id` is the only
parameter:

```yaml
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATAFLOW
        parameters:
          dataflow_id: <power-bi-dataflow-guid>   # required, only parameter this job accepts
```

`dataset_id` and `dataflow_id` are mutually exclusive: a task is either `POWER_BI_REFRESH_DATASET`
(takes `dataset_id` + optional `refresh_type`) or `POWER_BI_REFRESH_DATAFLOW` (takes `dataflow_id`
alone), never both on the same job.

## refresh_type enum

Optional, and **only valid on `POWER_BI_REFRESH_DATASET`** (not on the dataflow job at all — see
above). Case-sensitive, fixed set mirroring Power BI's own `DatasetRefreshType` enum exactly:

`Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment`

Leave `refresh_type: null`/omit it unless the source explicitly requests a non-default refresh
type.

## Workspace is entirely connection-scoped — no task-level override

Unlike some other integrations, Power BI's workspace is **not** a task parameter at all — it's
configured once when the Power BI connection is set up (Settings -> Connections -> Power BI) and
applies to every task that uses that connection. There is no `workspace_id` field on either job to
set or leave null.

If the source targets more than one Power BI workspace across different tasks, that requires
**one Orchestra Power BI connection per workspace** — point each task's `connection:` at the
connection scoped to the workspace it needs. There is no way to override the workspace per task.

## References

- Orchestra Power BI integration: https://docs.getorchestra.io/docs/integrations/power_bi
- Power BI REST API — refresh dataset: https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset
- Power BI REST API — refresh dataflow: https://learn.microsoft.com/en-us/rest/api/power-bi/dataflows/refresh-dataflow
