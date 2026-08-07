from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime


def sync_orders():
    print("Syncing orders from the source system")


def sync_customers():
    print("Syncing customers from the source system")


def build_reporting_tables():
    print("Building downstream reporting tables from orders + customers")


with DAG(
    dag_id="reporting_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    sync_orders_task = PythonOperator(task_id="sync_orders", python_callable=sync_orders)
    sync_customers_task = PythonOperator(task_id="sync_customers", python_callable=sync_customers)

    # Run the reporting build as long as neither upstream sync outright failed —
    # it's fine if one of them was skipped (e.g. a disabled source for this run).
    build_reporting = PythonOperator(
        task_id="build_reporting_tables",
        python_callable=build_reporting_tables,
        trigger_rule=TriggerRule.NONE_FAILED,
    )

    [sync_orders_task, sync_customers_task] >> build_reporting
