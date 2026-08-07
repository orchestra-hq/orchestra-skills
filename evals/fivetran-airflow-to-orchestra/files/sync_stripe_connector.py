from datetime import datetime

from airflow import DAG
from fivetran_provider_async.operators import FivetranOperator

with DAG(
    dag_id="sync_stripe_fivetran",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    sync_stripe = FivetranOperator(
        task_id="sync_stripe",
        fivetran_conn_id="fivetran_prod",
        connector_id="brightly_typical",
        wait_for_completion=True,
    )
