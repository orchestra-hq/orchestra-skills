import os
import time
import requests
import msal
from prefect import task, flow


def _get_token():
    app = msal.ConfidentialClientApplication(
        client_id=os.environ["POWERBI_CLIENT_ID"],
        client_credential=os.environ["POWERBI_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{os.environ['POWERBI_TENANT_ID']}",
    )
    result = app.acquire_token_for_client(scopes=["https://analysis.windows.net/powerbi/api/.default"])
    return result["access_token"]


@task
def refresh_sales_dataset():
    token = _get_token()
    workspace_id = os.environ["POWERBI_WORKSPACE_ID"]
    dataset_id = "8f3c1a90-6b2d-4e77-9c10-5a6b7c8d9e0f"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
        headers=headers,
        json={"type": "Full"},
    )
    resp.raise_for_status()

    while True:
        time.sleep(20)
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
def sales_dataset_flow():
    refresh_sales_dataset()
