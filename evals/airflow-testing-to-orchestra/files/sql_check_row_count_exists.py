from airflow import DAG
from airflow.providers.common.sql.operators.sql import SqlCheckOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from datetime import datetime

with DAG(
    dag_id="daily_orders_quality",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    load_orders = SnowflakeOperator(
        task_id="load_orders",
        snowflake_conn_id="snowflake_prod",
        sql="INSERT INTO orders SELECT * FROM orders_staging WHERE load_date = CURRENT_DATE",
    )

    # SqlCheckOperator passes when the SQL result is truthy — this check passes
    # only when at least one row landed today.
    check_row_count = SqlCheckOperator(
        task_id="check_row_count",
        conn_id="snowflake_prod",
        sql="SELECT COUNT(*) > 0 FROM orders WHERE load_date = CURRENT_DATE",
    )

    load_orders >> check_row_count
