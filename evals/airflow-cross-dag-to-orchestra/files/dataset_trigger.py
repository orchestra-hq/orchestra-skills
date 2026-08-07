from datetime import datetime

from airflow import DAG, Dataset
from airflow.operators.python import PythonOperator

orders_dataset = Dataset("s3://data-lake/orders/")


def extract_orders():
    ...


with DAG(
    dag_id="orders_producer",
    schedule_interval="0 5 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as producer_dag:
    extract = PythonOperator(
        task_id="extract_orders",
        python_callable=extract_orders,
        outlets=[orders_dataset],
    )


def build_order_summary():
    ...


with DAG(
    dag_id="orders_summary_consumer",
    schedule=[orders_dataset],
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as consumer_dag:
    summarize = PythonOperator(
        task_id="build_order_summary",
        python_callable=build_order_summary,
    )
