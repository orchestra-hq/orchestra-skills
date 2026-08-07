from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

# This project ships a pyproject.toml + poetry.lock at its root, so Python deps
# are managed with Poetry rather than pip or uv.

with DAG(
    dag_id="nightly_dbt_build",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command="dbt seed --project-dir warehouse/dbt --profiles-dir warehouse/dbt",
    )

    dbt_build_daily = BashOperator(
        task_id="dbt_build_daily",
        bash_command=(
            "dbt build --select tag:daily --target prod "
            "--project-dir warehouse/dbt --profiles-dir warehouse/dbt"
        ),
    )

    dbt_seed >> dbt_build_daily
