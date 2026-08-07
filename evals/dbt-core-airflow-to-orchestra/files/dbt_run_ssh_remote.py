from datetime import datetime

from airflow import DAG
from airflow.providers.ssh.operators.ssh import SSHOperator

# No lockfile or pyproject.toml is visible on the remote server dbt_build_server
# hosts this from, so there's no signal here for pip/poetry/uv.

with DAG(
    dag_id="remote_dbt_run",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    dbt_run_remote = SSHOperator(
        task_id="dbt_run_remote_warehouse",
        ssh_conn_id="dbt_build_server",
        command=(
            "cd /home/dbtuser/analytics && "
            "dbt run --select tag:core --project-dir transform --profiles-dir transform --target prod"
        ),
    )
