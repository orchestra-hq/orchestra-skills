from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

SLACK_CONN_ID = "slack_default"


def task_fail_slack_alert(context):
    SlackWebhookOperator(
        task_id="slack_fail_notify",
        slack_webhook_conn_id=SLACK_CONN_ID,
        message=f":x: DAG {context['dag'].dag_id} failed — check Airflow logs.",
        channel="#eng-oncall",
    ).execute(context=context)


default_args = {
    "owner": "data-eng",
    "on_failure_callback": task_fail_slack_alert,
}

with DAG(
    dag_id="nightly_ingest",
    default_args=default_args,
    schedule_interval="0 3 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    ingest = PythonOperator(task_id="ingest", python_callable=lambda: None)
