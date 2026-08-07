import os

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from slack_sdk import WebClient


def notify_pipeline_complete(status: str) -> None:
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(
        channel="#data-alerts",
        text=f":white_check_mark: Nightly load finished — status: {status}.",
    )


with DAG(
    dag_id="nightly_load",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    notify_task = PythonOperator(
        task_id="notify_pipeline_complete",
        python_callable=notify_pipeline_complete,
        op_kwargs={"status": "Completed"},
    )
