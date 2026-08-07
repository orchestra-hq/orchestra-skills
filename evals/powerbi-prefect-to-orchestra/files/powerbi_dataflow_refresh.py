import os
import time
import requests
import msal
from prefect import task, flow


def _token():
    app = msal.ConfidentialClientApplication(
        client_id=os.environ["POWERBI_CLIENT_ID"],
        client_credential=os.environ["POWERBI_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{os.environ['POWERBI_TENANT_ID']}",
    )
    return app.acquire_token_for_client(scopes=["https://analysis.windows.net/powerbi/api/.default"])["access_token"]


@task(retries=2, retry_delay_seconds=120)
def refresh_marketing_dataflow():
    token = _token()
    workspace_id = os.environ["POWERBI_WORKSPACE_ID"]
    dataflow_id = os.environ["MARKETING_DATAFLOW_ID"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/dataflows/{dataflow_id}/refreshes",
        headers=headers,
    )
    resp.raise_for_status()
    while True:
        time.sleep(15)
        status = requests.get(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/dataflows/{dataflow_id}/transactions",
            headers=headers,
        ).json()
        if status["value"][0]["status"] == "Success":
            break


@flow
def marketing_dataflow_flow():
    refresh_marketing_dataflow()
