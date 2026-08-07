from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.pagerduty.hooks.pagerduty_events import PagerdutyEventsHook

PAGERDUTY_CONN_ID = "pagerduty_oncall_67890"


def pagerduty_alert(context):
    hook = PagerdutyEventsHook(pagerduty_conn_id=PAGERDUTY_CONN_ID)
    hook.send_event(
        summary=f"Critical load failed: {context['dag'].dag_id}.{context['task_instance'].task_id}",
        severity="critical",
        source="airflow-critical-load",
    )


default_args = {
    "owner": "data-eng",
}

with DAG(
    dag_id="critical_load_pipeline",
    default_args=default_args,
    schedule_interval="*/15 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    stage_data = PythonOperator(task_id="stage_data", python_callable=lambda: None)

    critical_load = PythonOperator(
        task_id="critical_load",
        python_callable=lambda: None,
        on_failure_callback=pagerduty_alert,
    )

    downstream_report = PythonOperator(task_id="downstream_report", python_callable=lambda: None)

    stage_data >> critical_load >> downstream_report
