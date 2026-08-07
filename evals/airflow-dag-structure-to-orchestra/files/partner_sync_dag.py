import os
from datetime import datetime

import requests
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator


def sync_table(**context):
    target_env = context["params"]["target_env"]
    table = Variable.get("table", default_var="orders")
    api_key = os.environ["PARTNER_API_KEY"]
    requests.post(
        f"https://partner.example.com/sync/{table}",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"env": target_env},
    )


# No schedule_interval — this DAG is only ever triggered manually or by an upstream
# automation, never on a cron.
with DAG(
    "partner_sync",
    schedule_interval=None,
    start_date=datetime(2023, 1, 1),
    catchup=False,
    params={"target_env": "prod"},
) as dag:
    sync = PythonOperator(
        task_id="sync_table",
        python_callable=sync_table,
    )
