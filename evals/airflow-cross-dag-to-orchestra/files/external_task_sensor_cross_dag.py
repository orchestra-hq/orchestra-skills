from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor


def build_daily_report():
    ...


with DAG(
    dag_id="daily_report",
    schedule_interval="0 8 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    wait_for_elt = ExternalTaskSensor(
        task_id="wait_for_nightly_elt",
        external_dag_id="nightly_elt",
        external_task_id=None,  # wait for the whole upstream DAG
        poke_interval=60,
        timeout=3600,
    )

    report = PythonOperator(
        task_id="build_daily_report",
        python_callable=build_daily_report,
    )

    wait_for_elt >> report
