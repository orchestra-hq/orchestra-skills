from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

# requirements.txt at the repo root pins:
#   dbt-oss>=2,<3
# (the team dropped dbt-core and dbt-snowflake when they moved to dbt v2;
#  the DAG's commands were never updated afterwards)

with DAG(
    dag_id="marts_dbt_build",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command="dbt run -m tag:marts --partial-parse --target prod",
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command="dbt test --models tag:marts --target prod",
    )

    dbt_run_marts >> dbt_test_marts
