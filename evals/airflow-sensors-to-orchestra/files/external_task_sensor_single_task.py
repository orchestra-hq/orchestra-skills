from airflow import DAG
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.operators.python import PythonOperator
from datetime import datetime

# The revenue report only needs the orders table loaded. It does not care about the
# rest of nightly_elt, which keeps running for another two hours after load_orders.
with DAG(
    dag_id="revenue_report",
    start_date=datetime(2024, 1, 1),
    schedule="0 5 * * *",
    catchup=False,
) as dag:
    wait_for_orders_loaded = ExternalTaskSensor(
        task_id="wait_for_orders_loaded",
        external_dag_id="nightly_elt",
        external_task_id="load_orders",
        allowed_states=["success"],
        poke_interval=120,
        timeout=10800,
    )

    build_revenue_report = PythonOperator(
        task_id="build_revenue_report",
        python_callable=lambda: None,
    )

    wait_for_orders_loaded >> build_revenue_report
