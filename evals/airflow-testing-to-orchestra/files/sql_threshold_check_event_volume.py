from airflow import DAG
from airflow.providers.common.sql.operators.sql import SQLThresholdCheckOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from datetime import datetime

with DAG(
    dag_id="event_volume_quality",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    load_events = SnowflakeOperator(
        task_id="load_events",
        snowflake_conn_id="snowflake_prod",
        sql="INSERT INTO analytics.events SELECT * FROM events_staging WHERE load_date = CURRENT_DATE",
    )

    # Fails (or warns) if today's event volume falls outside [5000, 200000].
    check_event_volume = SQLThresholdCheckOperator(
        task_id="check_event_volume",
        conn_id="snowflake_prod",
        sql="SELECT COUNT(*) FROM analytics.events WHERE load_date = CURRENT_DATE",
        min_threshold=5000,
        max_threshold=200000,
    )

    load_events >> check_event_volume
