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

Source of truth: verified live against the real Orchestra backend via the `validate_pipeline` MCP
tool (not a static schema file — an earlier version of this doc claimed `workspace_id` and
`apply_refresh_policy` don't exist at all, based on a local schema snapshot that turned out to be
stale; live validation proved that wrong, so trust a live check over any cached schema copy for
these two integrations' finer edge cases).

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
          dataset_id: <power-bi-dataset-guid>   # required
          workspace_id: null                      # optional — see Workspace scoping below
          refresh_type: null                      # optional enum — see below
          apply_refresh_policy: null               # optional bool — only when refresh_type is Full/Automatic/DataOnly
        depends_on: []
        condition: null
        tags: []
```

Dataflow refresh — same shape, `integration_job: POWER_BI_REFRESH_DATAFLOW` and `dataflow_id`
instead of `dataset_id`. Neither `refresh_type` nor `apply_refresh_policy` exists on this job —
`additionalProperties: false` rejects both if you try:

```yaml
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATAFLOW
        parameters:
          dataflow_id: <power-bi-dataflow-guid>   # required
          workspace_id: null                        # optional — see Workspace scoping below
```

`dataset_id` and `dataflow_id` are mutually exclusive: a task is either `POWER_BI_REFRESH_DATASET`
or `POWER_BI_REFRESH_DATAFLOW`, never both on the same job.

## refresh_type and apply_refresh_policy — POWER_BI_REFRESH_DATASET only

`refresh_type` is optional, case-sensitive, a fixed set mirroring Power BI's own
`DatasetRefreshType` enum exactly:

`Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment`

Leave `refresh_type: null`/omit it unless the source explicitly requests a non-default refresh
type.

`apply_refresh_policy` is optional and boolean, but **conditionally valid**: the backend rejects it
unless `refresh_type` is one of `Full`, `Automatic`, or `DataOnly` (`"apply_refresh_policy is only
supported when refresh_type is Full, Automatic, or DataOnly"`). Only set it alongside one of those
three `refresh_type` values — never set it with `ClearValues`/`Calculate`/`Defragment`, and never
set it at all on `POWER_BI_REFRESH_DATAFLOW` (it doesn't exist there).

## Workspace scoping

`workspace_id` is a genuine, optional parameter on **both** jobs — it is not connection-only.
Leave it `null` to use the workspace already configured on the Power BI connection; only set an
explicit value when a specific task targets a *different* workspace than the one on the
connection. This is the same general pattern as other integrations' task-parameter-vs-connection-
scope tradeoff — see
[`connections.md`](connections.md#dont-duplicate-connection-level-scope-into-task-parameters).

## References

- Orchestra Power BI integration: https://docs.getorchestra.io/docs/integrations/power_bi
- Power BI REST API — refresh dataset: https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset
- Power BI REST API — refresh dataflow: https://learn.microsoft.com/en-us/rest/api/power-bi/dataflows/refresh-dataflow
