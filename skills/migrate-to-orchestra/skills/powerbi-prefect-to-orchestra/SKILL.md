---
name: powerbi-prefect-to-orchestra
description: "Use this skill when the user wants to convert a Prefect @task that refreshes a Power BI dataset (semantic model) or dataflow — typically using msal/requests against the Power BI REST API, or a custom PowerBIBlock/ConfigurableResource wrapping it — into an equivalent Orchestra pipeline task targeting Power BI. Triggers: any mention of migrating Power BI refresh Prefect tasks to Orchestra; Prefect flow code importing msal or requests and calling the Power BI 'refreshes' or 'datasets/{id}/refreshes' / 'dataflows/{id}/refreshes' REST endpoints. Must be read before finalizing any Orchestra YAML that contains integration: POWER_BI."
---

## Overview

There is no official Prefect Power BI block or collection. Power BI refresh tasks in Prefect are always hand-rolled `@task` functions that (1) acquire an Azure AD token for a service principal — usually via `msal.ConfidentialClientApplication` — and (2) call the Power BI REST API directly with `requests` (or `httpx`) to trigger a dataset or dataflow refresh and poll its status. This skill converts that pattern into Orchestra pipeline tasks using the `POWER_BI` integration. Authentication (tenant ID, client ID/application ID, client secret) moves from environment variables inside the task to a named Orchestra Power BI connection.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `msal.ConfidentialClientApplication(client_id, client_credential, authority=f".../{tenant_id}")` | `connection:` | Orchestra Power BI connection holds tenant ID, client ID, and client secret (Azure service principal) |
| `POST /v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/refreshes` | `integration_job: POWER_BI_REFRESH_DATASET` + `parameters.dataset_id` | `group_id` in the URL path maps to `parameters.workspace_id` — leave `null` unless it varies from the connection's workspace, see Gotchas |
| `POST /v1.0/myorg/groups/{group_id}/dataflows/{dataflow_id}/refreshes` | `integration_job: POWER_BI_REFRESH_DATAFLOW` + `parameters.dataflow_id` | Same `group_id` → `workspace_id` mapping — leave `null` unless it varies from the connection's workspace |
| JSON body `{"notifyOption": "MailOnFailure"}` or similar | _(dropped)_ | Not a valid Orchestra parameter — Orchestra pipeline `alerts:` replaces failure notification, see below |
| JSON body `{"type": "Full"}` or `refreshRequest.type` | `parameters.refresh_type` | Optional — one of `Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment` |
| polling loop (`GET .../refreshes/{id}` until `Completed`/`Failed`) | _(always)_ | Orchestra's task already waits for completion |
| `retries` / `retry_delay_seconds` on `@task` | `configuration.retries` / `configuration.retry_delay` | Under `configuration:` block — `retry_delay` is integer MINUTES (not seconds); convert by dividing by 60, cap at 120 |

## Orchestra YAML Structure

Dataset (semantic model) refresh:

```yaml
integration: POWER_BI
integration_job: POWER_BI_REFRESH_DATASET
name: refresh_dashboard_dataset
connection: power_bi_prod_12345
parameters:
  dataset_id: my-dataset-id
  workspace_id: null            # optional — leave null to use the workspace on the connection; only set if this task targets a different workspace
  refresh_type: null            # optional enum
  apply_refresh_policy: null    # optional bool
depends_on: []
condition: null
tags: []
```

Dataflow refresh:

```yaml
integration: POWER_BI
integration_job: POWER_BI_REFRESH_DATAFLOW
name: refresh_marketing_dataflow
connection: power_bi_prod_12345
parameters:
  dataflow_id: my-dataflow-id
  workspace_id: null            # optional — leave null unless this task targets a different workspace than the connection's
depends_on: []
condition: null
tags: []
```

## Conversion Steps

- [ ] Identify whether the task's REST call targets `.../datasets/{id}/refreshes` (→ `POWER_BI_REFRESH_DATASET`) or `.../dataflows/{id}/refreshes` (→ `POWER_BI_REFRESH_DATAFLOW`)
- [ ] Extract the dataset/dataflow ID and the workspace (`group_id`) from the URL, function arguments, or environment variables
- [ ] Extract any explicit refresh type (`"type": "Full"`, etc.) from the request body — map to `refresh_type`; otherwise leave `null`
- [ ] Create an Orchestra Power BI connection via Settings → Connections → Power BI, using the same Azure service-principal credentials (`tenant_id`, `client_id`, `client_secret`) the `msal` call used
- [ ] Note the connection name assigned by Orchestra (e.g. `power_bi_prod_12345`)
- [ ] Write the Orchestra task YAML using the structure above
- [ ] Delete the Prefect `@task` function, its polling loop, and any `msal`/`requests` imports no longer needed
- [ ] If the task was called inside a `@flow`, replace the call with a `depends_on:` reference in the Orchestra pipeline YAML

## Before / After Example

### Prefect (before)

```python
import os
import time
import requests
import msal
from prefect import task, flow

def _get_powerbi_token():
    app = msal.ConfidentialClientApplication(
        client_id=os.environ["POWERBI_CLIENT_ID"],
        client_credential=os.environ["POWERBI_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{os.environ['POWERBI_TENANT_ID']}",
    )
    result = app.acquire_token_for_client(
        scopes=["https://analysis.windows.net/powerbi/api/.default"]
    )
    return result["access_token"]

@task
def refresh_powerbi_dataset():
    token = _get_powerbi_token()
    workspace_id = os.environ["POWERBI_WORKSPACE_ID"]
    dataset_id = os.environ["POWERBI_DATASET_ID"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
        headers=headers,
    )
    resp.raise_for_status()

    while True:
        time.sleep(15)
        status = requests.get(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes/top/1",
            headers=headers,
        ).json()
        state = status["value"][0]["status"]
        if state == "Completed":
            break
        if state == "Failed":
            raise RuntimeError("Power BI dataset refresh failed")

@flow
def powerbi_flow():
    refresh_powerbi_dataset()
```

### Orchestra YAML (after)

```yaml
pipeline:
  stage-refresh:
    tasks:
      refresh-dashboard-dataset:
        integration: POWER_BI
        integration_job: POWER_BI_REFRESH_DATASET
        name: refresh_dashboard_dataset
        connection: power_bi_prod_12345
        parameters:
          dataset_id: ${{ ENV.POWERBI_DATASET_ID }}
          workspace_id: null   # single workspace used throughout; connection is already scoped to it, so no per-task override needed
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **`additionalProperties: false`** — `POWER_BI_REFRESH_DATASET` and `POWER_BI_REFRESH_DATAFLOW` reject any parameter key not in the mapping table above; don't carry over REST-body-only fields like `notifyOption` as top-level parameters.
- **Dataset vs. dataflow use different ID fields** — `dataset_id` on `POWER_BI_REFRESH_DATASET`, `dataflow_id` on `POWER_BI_REFRESH_DATAFLOW`. Never pass both, and never pass `dataflow_id` on the dataset job or vice versa.
- **There is no native Prefect Power BI block** — every Power BI refresh in Prefect is a hand-rolled `@task` wrapping `msal` + `requests`/`httpx`; do not look for a `PowerBIBlock` or official collection.
- **`group_id` in the REST URL is `workspace_id` in Orchestra** — same GUID, just a naming difference between the raw Power BI REST API and Orchestra's parameter model.
- **Don't reflexively carry `workspace_id` through as `${{ ENV.POWERBI_WORKSPACE_ID }}`** — if every task reads the same single `group_id`/workspace env var, that workspace belongs on the Orchestra connection itself, not repeated in every task's parameters. Leave `parameters.workspace_id: null` by default; only set an explicit value when a specific task truly targets a workspace different from the connection's.
- **Manual polling loops are dropped entirely** — Orchestra's task already waits for the refresh to reach a terminal state; don't try to preserve the `while True: time.sleep(...)` logic.
- **Only use `${{ ENV.POWERBI_DATASET_ID }}` if the source genuinely reads it that way** — in the example above it's legitimate because `dataset_id = os.environ["POWERBI_DATASET_ID"]` has no literal fallback, so the pipeline really does need that Orchestra environment variable set. If the source instead has a literal/hardcoded dataset ID, or an `os.getenv(..., "default-id")` with a real default, use that literal value directly — don't fabricate an `${{ ENV.VAR }}` reference the source doesn't actually read; it produces a pipeline that fails with no matching value to set.
- **`refresh_type` values are case-sensitive and fixed** — only `Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, `Defragment` are valid; leave `null` if the source code didn't set an explicit `type` in the refresh request body.
- **Token acquisition code disappears** — the `msal.ConfidentialClientApplication` boilerplate for getting a bearer token is replaced entirely by the Orchestra connection; don't try to preserve it as a preceding task.

## References

- Orchestra Power BI integration: https://docs.getorchestra.io/docs/integrations/power_bi
- Power BI REST API — refresh dataset: https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset
- Power BI REST API — refresh dataflow: https://learn.microsoft.com/en-us/rest/api/power-bi/dataflows/refresh-dataflow
- See `prefect-connections-to-orchestra` for the Azure service-principal connection pattern.
- See `prefect-alerts-to-orchestra` for all notification patterns.

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
