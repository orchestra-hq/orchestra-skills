from airflow import DAG
from airflow.providers.airbyte.operators.airbyte import AirbyteTriggerSyncOperator
from airflow.providers.airbyte.sensors.airbyte import AirbyteSensor
from datetime import datetime

# Airflow connection "airbyte_cloud_prod" points at api.airbyte.com (Airbyte Cloud, API-key auth)
with DAG(
    dag_id="airbyte_cloud_marketing_sync",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    trigger_marketing = AirbyteTriggerSyncOperator(
        task_id="trigger_marketing_sync",
        airbyte_conn_id="airbyte_cloud_prod",
        connection_id="8c4d5e6f-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
        asynchronous=True,
    )

    wait_marketing = AirbyteSensor(
        task_id="wait_marketing_sync",
        airbyte_conn_id="airbyte_cloud_prod",
        airbyte_job_id=trigger_marketing.output,
        poke_interval=60,
    )

    trigger_marketing >> wait_marketing
