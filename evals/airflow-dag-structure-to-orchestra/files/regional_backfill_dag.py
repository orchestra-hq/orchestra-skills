from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from airflow.utils.task_group import TaskGroup

# retry_delay of 3 hours = 180 minutes, far beyond Orchestra's 120-minute cap once converted.
default_args = {
    "retries": 3,
    "retry_delay": timedelta(hours=3),
}

with DAG(
    "regional_backfill",
    default_args=default_args,
    schedule_interval="30 1 * * *",
    start_date=datetime(2023, 1, 1),
    catchup=True,
    tags=["backfill"],
) as dag:
    # Nested TaskGroups: "regional_extract" is the only top-level group, with "emea"
    # and "apac" nested inside it.
    with TaskGroup("regional_extract") as regional_extract:
        with TaskGroup("emea") as emea:
            extract_emea = PythonOperator(
                task_id="extract_emea",
                python_callable=lambda: None,
            )
            load_emea = SnowflakeOperator(
                task_id="load_emea",
                snowflake_conn_id="snowflake_default",
                sql="INSERT INTO analytics.core.emea_orders SELECT * FROM staging.emea_orders",
            )
            extract_emea >> load_emea

        with TaskGroup("apac") as apac:
            extract_apac = PythonOperator(
                task_id="extract_apac",
                python_callable=lambda: None,
            )
            load_apac = SnowflakeOperator(
                task_id="load_apac",
                snowflake_conn_id="snowflake_default",
                sql="INSERT INTO analytics.core.apac_orders SELECT * FROM staging.apac_orders",
            )
            extract_apac >> load_apac
