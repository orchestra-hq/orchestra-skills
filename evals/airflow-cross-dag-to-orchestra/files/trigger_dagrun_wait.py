from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def publish_dashboard():
    ...


with DAG(
    dag_id="orchestration_dag",
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    trigger_reporting = TriggerDagRunOperator(
        task_id="trigger_reporting",
        trigger_dag_id="daily_reporting",
        conf={"env": "prod"},
        wait_for_completion=True,
        poke_interval=30,
    )

    publish = PythonOperator(
        task_id="publish_dashboard",
        python_callable=publish_dashboard,
    )

    trigger_reporting >> publish
