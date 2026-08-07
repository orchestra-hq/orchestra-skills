from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def build_region_rollup(region: str, lookback_days: int) -> None:
    import os

    import requests

    api_key = os.environ["SALES_API_KEY"]
    resp = requests.get(
        "https://sales.internal.example.com/api/rollup",
        params={"region": region, "lookback_days": lookback_days},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"Rolled up {len(resp.json().get('rows', []))} rows for {region}")


with DAG(
    dag_id="region_sales_rollup",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    rollup_task = PythonOperator(
        task_id="build_region_rollup",
        python_callable=build_region_rollup,
        op_kwargs={"region": "us-east-1", "lookback_days": 7},
    )
