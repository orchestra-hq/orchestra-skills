from airflow import DAG
from airflow.providers.airbyte.operators.airbyte import AirbyteTriggerSyncOperator
from datetime import datetime

# Airflow connection "airbyte_cloud_prod" points at api.airbyte.com (Airbyte Cloud, API-key auth)
with DAG(
    dag_id="airbyte_cloud_orders_sync",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@hourly",
    catchup=False,
) as dag:
    sync_orders = AirbyteTriggerSyncOperator(
        task_id="sync_orders_table",
        airbyte_conn_id="airbyte_cloud_prod",
        connection_id="5f3a2b1c-9d8e-4f7a-b6c5-d4e3f2a1b0c9",
        asynchronous=False,
    )
