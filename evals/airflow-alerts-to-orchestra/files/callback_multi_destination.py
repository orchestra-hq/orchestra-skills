from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.providers.pagerduty.hooks.pagerduty_events import PagerdutyEventsHook

SLACK_CONN_ID = "slack_default"
PAGERDUTY_CONN_ID = "pagerduty_prod_12345"


def notify_slack_failure(context):
    SlackWebhookOperator(
        task_id="slack_fail_notify",
        slack_webhook_conn_id=SLACK_CONN_ID,
        message=f":x: DAG {context['dag'].dag_id} failed on task {context['task_instance'].task_id}",
        channel="#incidents",
    ).execute(context=context)


def page_oncall_failure(context):
    hook = PagerdutyEventsHook(pagerduty_conn_id=PAGERDUTY_CONN_ID)
    hook.send_event(
        summary=f"DAG {context['dag'].dag_id} failed — immediate attention required",
        severity="critical",
    )


def on_failure_notify(context):
    # Fan out to both destinations on any task failure.
    notify_slack_failure(context)
    page_oncall_failure(context)


default_args = {
    "owner": "data-eng",
    "retries": 1,
    "on_failure_callback": on_failure_notify,
    "on_success_callback": None,
}

with DAG(
    dag_id="revenue_reporting_pipeline",
    default_args=default_args,
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    extract = PythonOperator(task_id="extract_revenue", python_callable=lambda: None)
    transform = PythonOperator(task_id="transform_revenue", python_callable=lambda: None)
    load = PythonOperator(task_id="load_revenue", python_callable=lambda: None)

    extract >> transform >> load
