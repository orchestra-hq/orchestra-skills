---
name: tableau-dagster-to-orchestra
description: "Use this skill when the user wants to convert a Dagster Tableau integration — TableauCloudWorkspace, TableauServerWorkspace, load_tableau_asset_specs, or build_tableau_materializable_assets_definition — into an equivalent Orchestra pipeline task targeting Tableau Cloud. Triggers: any mention of migrating or rewriting Dagster Tableau assets to Orchestra; Dagster code importing from dagster_tableau."
---

# Tableau Cloud: Dagster -> Orchestra Conversion

## Overview

In Dagster, Tableau is integrated via `dagster-tableau`: a `TableauCloudWorkspace` (or `TableauServerWorkspace`) loads workbooks and datasources as asset specs via `load_tableau_asset_specs`, and materializable assets trigger workbook/extract refreshes. In Orchestra the equivalent is a task under the `TABLEAU_CLOUD` integration.

## Parameter Mapping

| Dagster concept | Orchestra YAML field | Notes |
|---|---|---|
| `TableauCloudWorkspace(...)` | `connection:` | Orchestra Tableau Cloud connection (server URL, site, token) |
| workbook asset | `parameters.workbook_name` + `parameters.project_name` | Display name + containing project |
| `site_name` / `pod_name` | Configured on the connection | Not per-task |
| materialization (refresh) | _(always waits)_ | Orchestra always waits for completion |
| asset key / name | `name:` | Human-readable task name |
| upstream asset deps | `depends_on:` | |

## Orchestra YAML Structure

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: TABLEAU_CLOUD
        integration_job: TABLEAU_REFRESH_WORKBOOK
        name: <descriptive name>
        connection: <orchestra-tableau-cloud-connection-name>
        parameters:
          project_name: <tableau-project-name>   # required
          workbook_name: <tableau-workbook-name>    # required
        depends_on: []
        condition: null
        tags: []
```

> **Datasource refresh** — for a published datasource, use `integration_job: TABLEAU_REFRESH_EXTRACT` and `parameters.datasource_name`.

## Conversion Steps

1. **Find the workspace + assets** — locate `TableauCloudWorkspace`, `load_tableau_asset_specs`, and the workbook/datasource being refreshed. Note `site_name`/`pod_name` and the workbook display name.
2. **Create/verify the Orchestra connection** — Settings -> Connections -> Tableau Cloud with server URL, site name, and a PAT. Site lives on the connection.
3. **Replace the asset with a task block** — use the workbook display name and its project.
4. **Wire dependencies**.

## Before / After Example

### Dagster (before)

```python
from dagster import Definitions, EnvVar
from dagster_tableau import TableauCloudWorkspace, load_tableau_asset_specs

tableau = TableauCloudWorkspace(
    connected_app_client_id=EnvVar("TABLEAU_CLIENT_ID"),
    connected_app_secret_id=EnvVar("TABLEAU_SECRET_ID"),
    connected_app_secret_value=EnvVar("TABLEAU_SECRET_VALUE"),
    username=EnvVar("TABLEAU_USERNAME"),
    site_name="mysite", pod_name="10ax",
)
tableau_specs = load_tableau_asset_specs(tableau)
defs = Definitions(assets=[*tableau_specs], resources={"tableau": tableau})
```

### Orchestra YAML (after)

```yaml
version: v1
name: my-pipeline
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: TABLEAU_CLOUD
        integration_job: TABLEAU_REFRESH_WORKBOOK
        name: refresh_sales_dashboard
        connection: tableau_cloud_prod_12345
        parameters:
          project_name: Sales
          workbook_name: Sales Dashboard
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Workbook name vs ID** — Orchestra uses the display name (case-sensitive). Dagster specs may key by LUID; use the human-readable name.
- **`project_name` is required** — Orchestra requires it alongside `workbook_name`.
- **Site / pod on the connection** — `site_name`/`pod_name` map to the Orchestra connection, not per-task. One connection per site.
- **Connected App vs PAT** — Dagster uses a Connected App; Orchestra typically uses a PAT. Update credentials on the connection.
- **Datasource refresh** — maps to `TABLEAU_REFRESH_EXTRACT` with `datasource_name`.
- **Server vs Cloud** — `dagster-tableau` supports both; Orchestra's `TABLEAU_CLOUD` covers Cloud and Server (verify Server version support).

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/tableau_cloud
- Dagster Tableau: https://docs.dagster.io/integrations/libraries/tableau
- dagster-tableau API: https://docs.dagster.io/api/python-api/libraries/dagster-tableau

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