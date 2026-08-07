import os
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from slack_sdk import WebClient


def run_dbt_build():
    ...


def notify_dbt_complete():
    # No SlackWebhookOperator or SlackAPIOperator here at all — a plain PythonOperator
    # wrapping the raw Slack Web API client, wired as an explicit mid-DAG step below.
    WebClient(token=os.environ["SLACK_BOT_TOKEN"]).chat_postMessage(
        channel="#data-team",
        text="dbt build complete — starting downstream loads.",
    )


def load_downstream():
    ...


with DAG(
    dag_id="nightly_pipeline",
    schedule_interval="0 5 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    build = PythonOperator(task_id="run_dbt_build", python_callable=run_dbt_build)
    notify = PythonOperator(task_id="notify_dbt_complete", python_callable=notify_dbt_complete)
    load = PythonOperator(task_id="load_downstream", python_callable=load_downstream)

    build >> notify >> load
