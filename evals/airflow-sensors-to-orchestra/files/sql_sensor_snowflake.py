from datetime import datetime

from airflow import DAG
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from airflow.sensors.sql import SqlSensor

with DAG(
    dag_id="month_end_close_processing",
    schedule_interval="0 6 * * 0",  # weekly reconciliation window
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    # The month-end close batch occasionally takes several days to fully land,
    # so the timeout is set generously to avoid the sensor giving up too early.
    wait_for_close_data = SqlSensor(
        task_id="wait_for_close_data",
        conn_id="snowflake_prod",
        sql="SELECT COUNT(*) FROM raw.orders WHERE order_date = CURRENT_DATE",
        poke_interval=45,
        timeout=500000,  # ~8333 minutes
        mode="reschedule",
    )

    process_close_data = SnowflakeOperator(
        task_id="process_close_data",
        snowflake_conn_id="snowflake_prod",
        sql="INSERT INTO orders_final SELECT * FROM raw.orders WHERE order_date = CURRENT_DATE",
    )

    wait_for_close_data >> process_close_data
