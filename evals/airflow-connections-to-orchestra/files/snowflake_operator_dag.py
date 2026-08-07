from datetime import datetime

from airflow import DAG
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator

with DAG(
    "revenue_rollup",
    schedule_interval="0 3 * * *",
    start_date=datetime(2023, 1, 1),
    catchup=False,
) as dag:
    load_revenue = SnowflakeOperator(
        task_id="load_revenue",
        snowflake_conn_id="snowflake_prod",
        warehouse="ANALYTICS_WH",
        database="ANALYTICS",
        role="TRANSFORMER",
        sql="INSERT INTO analytics.core.daily_revenue SELECT * FROM analytics.core.orders",
    )
