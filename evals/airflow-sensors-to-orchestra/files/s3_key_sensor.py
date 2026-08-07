from datetime import datetime

from airflow import DAG
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator

with DAG(
    dag_id="daily_orders_ingest",
    schedule_interval="0 7 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    wait_for_file = S3KeySensor(
        task_id="wait_for_orders_file",
        bucket_name="daily-uploads",
        bucket_key="orders/",
        wildcard_match=False,
        aws_conn_id="aws_default",
        poke_interval=90,
        timeout=3600,
        mode="reschedule",
    )

    process_orders = SnowflakeOperator(
        task_id="process_orders",
        snowflake_conn_id="snowflake_prod",
        sql="INSERT INTO orders_final SELECT * FROM orders_raw",
    )

    wait_for_file >> process_orders
