from datetime import datetime

from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.bash import BashOperator

# The dbt project's profiles.yml reads DBT_SF_* env vars. Airflow fills them from
# the same `snowflake_prod` connection the rest of the deployment already uses.
sf = BaseHook.get_connection("snowflake_prod")

with DAG(
    dag_id="analytics_dbt_build",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="dbt build --select tag:daily --project-dir warehouse/dbt",
        env={
            "DBT_SF_ACCOUNT": sf.extra_dejson["account"],
            "DBT_SF_USER": sf.login,
            "DBT_SF_PASSWORD": sf.password,
        },
    )
