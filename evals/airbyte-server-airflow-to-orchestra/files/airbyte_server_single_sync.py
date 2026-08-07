from airflow import DAG
from airflow.providers.airbyte.operators.airbyte import AirbyteTriggerSyncOperator
from datetime import datetime

# Airflow connection "airbyte_self_hosted" points at airbyte-internal.mycorp.com:8000
# (self-hosted Airbyte Server, basic auth — NOT api.airbyte.com / Airbyte Cloud)
with DAG(
    dag_id="airbyte_server_crm_sync",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    sync_crm = AirbyteTriggerSyncOperator(
        task_id="sync_crm_accounts",
        airbyte_conn_id="airbyte_self_hosted",
        connection_id="2b4c6d8e-0a1b-4c2d-8e3f-4a5b6c7d8e9f",
        asynchronous=False,
    )
