from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def clean_inventory_snapshot():
    import pandas as pd

    df = pd.read_csv("s3://raw-landing-bucket/inventory/daily_snapshot.csv")
    df = df.drop_duplicates(subset=["sku"])
    df["available_units"] = df["on_hand_units"] - df["reserved_units"]
    df = df[df["available_units"] >= 0]

    df.to_parquet("s3://curated-bucket/inventory/clean_daily_snapshot.parquet", index=False)
    print(f"Wrote {len(df)} clean inventory rows")


with DAG(
    dag_id="daily_inventory_snapshot",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    clean_snapshot_task = PythonOperator(
        task_id="clean_inventory_snapshot",
        python_callable=clean_inventory_snapshot,
    )
