---
name: tableau-prefect-to-orchestra
description: "Use this skill when the user wants to convert a Prefect @task that refreshes a Tableau workbook or extract — using tableau-server-client (TSC) library, RefreshWorkbookRequest, or ScheduleItem — into an equivalent Orchestra pipeline task targeting Tableau Cloud. Triggers: any mention of migrating Tableau refresh Prefect tasks to Orchestra; Prefect flow code importing tableau_server_client and calling rest_api.workbooks.refresh."
---

## Overview

Converts Prefect `@task` functions that use the `tableau-server-client` (TSC) Python library to refresh Tableau workbooks or datasource extracts into Orchestra pipeline tasks using the `TABLEAU_CLOUD` integration. Authentication (Personal Access Token + site ID) moves from environment variables inside the task to a named Orchestra Tableau Cloud connection.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `TSC.Server("https://10ax.online.tableau.com")` + `site_id` | `connection:` | Orchestra Tableau Cloud connection holds server URL, site ID, and PAT |
| `server.workbooks.filter(name="Sales Dashboard")` | `parameters.workbook_name` | String value from filter call |
| project name (from code context or filter chain) | `parameters.project_name` | **REQUIRED** alongside `workbook_name` |
| `server.workbooks.refresh(workbook)` | `integration_job: TABLEAU_REFRESH_WORKBOOK` | |
| `server.datasources.refresh(ds)` | `integration_job: TABLEAU_REFRESH_EXTRACT` + `parameters.datasource_name` | Switch integration_job and use datasource_name instead |
| `treat_failure_as_warning` | `treat_failure_as_warning: true` | Optional TaskModel field |
| retries / retry_delay | `configuration.retries` / `configuration.retry_delay` | Under `configuration:` block — `retry_delay` is integer MINUTES (not seconds); convert Prefect's `retry_delay_seconds` by dividing by 60, cap at 120 |

## Orchestra YAML Structure

```yaml
integration: TABLEAU_CLOUD
integration_job: TABLEAU_REFRESH_WORKBOOK   # or TABLEAU_REFRESH_EXTRACT
name: refresh_sales_dashboard
connection: tableau_cloud_prod_12345
parameters:
  project_name: Sales
  workbook_name: Sales Dashboard
depends_on: []
condition: null
tags: []
```

For a datasource extract refresh:

```yaml
integration: TABLEAU_CLOUD
integration_job: TABLEAU_REFRESH_EXTRACT
name: refresh_orders_extract
connection: tableau_cloud_prod_12345
parameters:
  project_name: Sales
  datasource_name: Orders Extract
depends_on: []
condition: null
tags: []
```

## Conversion Steps

- [ ] Identify whether the task calls `server.workbooks.refresh()` (→ `TABLEAU_REFRESH_WORKBOOK`) or `server.datasources.refresh()` (→ `TABLEAU_REFRESH_EXTRACT`)
- [ ] Extract the workbook/datasource name from the `.filter(name=...)` call or surrounding code comments
- [ ] Extract or infer the Tableau project name (check filter chain, variable names, or ask the user)
- [ ] Create an Orchestra Tableau Cloud connection via Integrations → New Connection → Tableau Cloud (server URL, site ID, PAT name, PAT value)
- [ ] Note the connection name assigned by Orchestra (e.g. `tableau_cloud_prod_12345`)
- [ ] Write the Orchestra task YAML using the structure above
- [ ] Delete the Prefect `@task` function and any TSC imports no longer needed
- [ ] If the task was called inside a `@flow`, replace the call with a `depends_on:` reference in the Orchestra pipeline YAML

## Before / After Example

### Prefect (before)

```python
import tableau_server_client as TSC
import os
from prefect import task, flow

@task
def refresh_tableau_workbook():
    tableau_auth = TSC.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_TOKEN"],
        site_id="mysite",
    )
    server = TSC.Server("https://10ax.online.tableau.com")
    with server.auth.sign_in(tableau_auth):
        workbook = server.workbooks.filter(name="Sales Dashboard").pop()
        server.workbooks.refresh(workbook)

@flow
def tableau_flow():
    refresh_tableau_workbook()
```

### Orchestra YAML (after)

```yaml
pipeline:
  stage-refresh:
    tasks:
      refresh-sales-dashboard:
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

- `project_name` is **REQUIRED** in Orchestra alongside `workbook_name` — extract it from filter logic, Tableau UI, or ask the user; the task will fail without it
- Site ID and PAT credentials belong on the Orchestra Tableau Cloud connection, not in YAML or env vars
- For datasource refresh: use `integration_job: TABLEAU_REFRESH_EXTRACT` and `parameters.datasource_name` (not `workbook_name`)
- There is no native Prefect Tableau block — Tableau tasks in Prefect are always a Python `@task` wrapping TSC; do not look for a block reference
- The TSC `.filter()` call returns a generator — `.pop()` picks the first match; confirm the workbook name is unique in the project before migrating
- `server.workbooks.refresh()` is async on Tableau Server; Orchestra polls for completion automatically

## References

- https://docs.getorchestra.io/docs/integrations/tableau_cloud
- https://tableau.github.io/server-client-python/docs/
- See `prefect-alerts-to-orchestra` for all notification patterns.

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
