"""Nightly DAG that posts failures to two Google Chat spaces via incoming webhooks.

The webhook URLs are held in Airflow Variables:
  - `gchat_data_alerts_webhook`  -> the "Data Alerts" space
  - `gchat_oncall_webhook`       -> the "On-call" space

In Orchestra these are already set up as Google Chat connections named
`google_chat_data_alerts_12345` and `google_chat_oncall_67890`.
"""

import requests
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from datetime import datetime


def notify_google_chat(context):
    text = f"DAG {context['dag'].dag_id} failed on {context['ds']}"
    for var in ("gchat_data_alerts_webhook", "gchat_oncall_webhook"):
        requests.post(Variable.get(var), json={"text": text})


with DAG(
    dag_id="nightly_etl",
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 2 * * *",
    default_args={"on_failure_callback": notify_google_chat},
) as dag:
    load = PythonOperator(task_id="load", python_callable=lambda: None)
