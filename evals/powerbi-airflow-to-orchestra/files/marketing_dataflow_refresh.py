import os

import requests
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator

MARKETING_DATAFLOW_ID = os.getenv("MARKETING_DATAFLOW_ID")
MARKETING_WORKSPACE_ID = os.getenv("MARKETING_WORKSPACE_ID")


def refresh_marketing_dataflow(**context):
    # There is no PowerBIDataflowRefreshOperator in
    # apache-airflow-providers-microsoft-azure, so the dataflow refresh REST
    # call is hand-rolled via a plain PythonOperator instead.
    conn = BaseHook.get_connection("powerbi_default")
    token = conn.password  # service-principal token acquired via MSAL upstream
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{MARKETING_WORKSPACE_ID}"
        f"/dataflows/{MARKETING_DATAFLOW_ID}/refreshes",
        headers=headers,
    )
    resp.raise_for_status()


with DAG("marketing_dataflow_refresh", schedule_interval="@daily", catchup=False) as dag:
    refresh_marketing_dataflow_task = PythonOperator(
        task_id="refresh_marketing_dataflow",
        python_callable=refresh_marketing_dataflow,
    )
