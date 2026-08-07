from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
    "email_on_failure": False,
}

with DAG(
    "nightly_elt",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["elt", "nightly"],
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=lambda: None,
    )

    load = SnowflakeOperator(
        task_id="load",
        snowflake_conn_id="snowflake_default",
        sql="INSERT INTO analytics.core.daily_revenue SELECT * FROM analytics.core.orders",
    )

    extract >> load
