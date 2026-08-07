---
name: tableau-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that uses TableauOperator or TableauRefreshWorkbookOperator (apache-airflow-providers-tableau) into an equivalent Orchestra pipeline task targeting Tableau Cloud. Triggers: any mention of migrating or rewriting Tableau Airflow tasks to Orchestra; Airflow DAG code containing TableauOperator, TableauRefreshWorkbookOperator, or TableauJobStatusSensor."
---

# Tableau Cloud: Airflow → Orchestra Conversion

## Overview

Airflow's `TableauRefreshWorkbookOperator` (or `TableauOperator`) triggers a Tableau workbook or extract refresh and optionally waits for it to complete. `TableauJobStatusSensor` polls a running job. In Orchestra the equivalent is a task under the `TABLEAU_CLOUD` integration.

## Parameter Mapping

| Airflow parameter | Orchestra YAML field | Notes |
|---|---|---|
| `tableau_conn_id` | `connection:` | The name of the Orchestra connection to Tableau Cloud (stores server URL, site ID, token) |
| `workbook_name` | `parameters.workbook_name` | Name of the workbook to refresh |
| `site_id` | Configured on the Orchestra connection | Set the Tableau site on the connection, not per-task |
| `blocking` / `TableauJobStatusSensor` | _(always)_ | Orchestra always waits for job completion |
| `task_id` | `name:` | Human-readable task name |
| upstream `>>` chains | `depends_on:` | |

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
        name: <task_id value from Airflow>
        connection: <orchestra-tableau-cloud-connection-name>
        parameters:
          project_name: <tableau-project-name>   # required
          workbook_name: <tableau-workbook-name>    # required
        depends_on: []
        condition: null
        tags: []
```

> **Datasource refresh** — if refreshing a published datasource instead of a workbook, use `integration_job: TABLEAU_REFRESH_EXTRACT` and `parameters.datasource_name`.

## Conversion Steps

1. **Identify the Airflow task** — locate `TableauRefreshWorkbookOperator` or `TableauOperator`. Note `workbook_name`, `site_id`, and `tableau_conn_id`.
2. **Create/verify the Orchestra connection** — in Orchestra Settings → Connections, create a *Tableau Cloud* connection with server URL, site name, and a Personal Access Token (PAT). The site is configured on the connection, not per-task.
3. **Replace operator with task block** — use the YAML above.
4. **Drop any `TableauJobStatusSensor`** — Orchestra's task already polls for completion.
5. **Wire dependencies** — convert `>>` chains to `depends_on:`.

## Before / After Example

### Airflow DAG (before)

```python
from airflow.providers.tableau.operators.tableau import TableauOperator

refresh_sales_wb = TableauOperator(
    task_id="refresh_sales_dashboard",
    resource="workbooks",
    method="refresh",
    find="Sales Dashboard",
    match_with="name",
    tableau_conn_id="tableau_cloud_prod",
    blocking_refresh=True,
)
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
          project_name: Sales           # required — Tableau project containing the workbook
          workbook_name: Sales Dashboard
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **Workbook name vs ID**: Orchestra uses the workbook display name. Ensure it matches exactly (case-sensitive) as it appears in Tableau Cloud.
- **Site ID on the connection**: unlike Airflow where `site_id` is a task parameter, Orchestra stores it on the connection. If you refresh workbooks across multiple Tableau sites, you need one Orchestra connection per site.
- **Personal Access Token (PAT)**: Tableau Cloud requires PAT-based authentication for API access. Username/password auth is deprecated — update credentials when creating the Orchestra connection.
- **`TableauOperator` with `resource="datasources"`**: map to `TABLEAU_REFRESH_EXTRACT` in Orchestra, using `parameters.datasource_name` instead of `workbook_name`.
- **`blocking_refresh=False` + sensor pattern**: both collapse into one Orchestra task.
- **Tableau Server (on-prem)**: this skill is for Tableau Cloud. For Tableau Server, confirm whether Orchestra's Tableau Cloud integration supports your Server version via the REST API.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/tableau_cloud
- Airflow Tableau provider: https://airflow.apache.org/docs/apache-airflow-providers-tableau/stable/operators/tableau.html

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
