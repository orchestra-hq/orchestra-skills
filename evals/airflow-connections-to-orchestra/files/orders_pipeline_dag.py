from datetime import datetime

from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator


def notify_slack(**context):
    # A credential pointer — the real webhook/token lives on the Connection record,
    # not in this source file.
    conn = BaseHook.get_connection("slack_alerts")
    webhook_url = conn.password
    # Non-secret config — just a channel name that's tunable per environment.
    channel = Variable.get("alerts_channel", default_var="#data-alerts")
    print(f"posting to {channel} via {webhook_url}")


with DAG(
    "orders_pipeline",
    schedule_interval="0 4 * * *",
    start_date=datetime(2023, 1, 1),
    catchup=False,
) as dag:
    # Non-secret config — the target table name, tunable per trigger.
    target_table = Variable.get("target_table", default_var="orders")

    load = SnowflakeOperator(
        task_id="load_orders",
        snowflake_conn_id="snowflake_prod",
        sql=f"INSERT INTO analytics.core.{target_table} SELECT * FROM staging.orders",
    )

    notify = PythonOperator(
        task_id="notify_slack",
        python_callable=notify_slack,
    )

    load >> notify
