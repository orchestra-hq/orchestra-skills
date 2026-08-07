from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor


def build_revenue_report():
    ...


with DAG(
    dag_id="revenue_report",
    schedule_interval="0 9 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    wait_for_upstream = ExternalTaskSensor(
        task_id="wait_for_nightly_elt",
        external_dag_id="nightly_elt",
        external_task_id=None,  # wait for the whole upstream DAG
        poke_interval=60,
        timeout=3600,
        mode="reschedule",
    )

    build_report = PythonOperator(
        task_id="build_revenue_report",
        python_callable=build_revenue_report,
    )

    wait_for_upstream >> build_report
