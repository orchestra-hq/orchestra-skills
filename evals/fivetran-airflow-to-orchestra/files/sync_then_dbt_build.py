from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from fivetran_provider_async.operators import FivetranOperator

with DAG(
    dag_id="sync_then_build_marts",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    sync_netsuite = FivetranOperator(
        task_id="sync_netsuite",
        fivetran_conn_id="fivetran_prod",
        connector_id="loosely_secondary",
        wait_for_completion=True,
    )

    dbt_build_marts = BashOperator(
        task_id="dbt_build_marts",
        bash_command="dbt build --select tag:daily --project-dir dbt_project --profiles-dir dbt_project",
    )

    sync_netsuite >> dbt_build_marts
