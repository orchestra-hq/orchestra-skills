from airflow import DAG
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.operators.python import PythonOperator
from datetime import datetime

# Cross-DAG dependency on ONE task of the upstream DAG, not the whole DAG run.
with DAG(
    dag_id="marketing_attribution",
    start_date=datetime(2024, 1, 1),
    schedule="0 5 * * *",
    catchup=False,
) as dag:
    wait_for_sessions = ExternalTaskSensor(
        task_id="wait_for_sessions_loaded",
        external_dag_id="nightly_elt",
        external_task_id="load_sessions",
        allowed_states=["success"],
        poke_interval=60,
        timeout=7200,
    )

    build_attribution = PythonOperator(
        task_id="build_attribution",
        python_callable=lambda: None,
    )

    wait_for_sessions >> build_attribution
