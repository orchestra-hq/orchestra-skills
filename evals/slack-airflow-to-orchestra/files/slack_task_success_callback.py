from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

SLACK_CONN_ID = "slack_default"


def notify_warehouse_load_success(context):
    SlackWebhookOperator(
        task_id="slack_load_success_notify",
        slack_webhook_conn_id=SLACK_CONN_ID,
        message=f":white_check_mark: {context['task_instance'].task_id} succeeded.",
        channel="#warehouse-notifications",
    ).execute(context=context)


with DAG(
    dag_id="nightly_warehouse_dag",
    schedule_interval="0 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    extract_data = PythonOperator(task_id="extract_data", python_callable=lambda: None)

    load_warehouse = PythonOperator(
        task_id="load_warehouse",
        python_callable=lambda: None,
        on_success_callback=notify_warehouse_load_success,
    )

    extract_data >> load_warehouse
