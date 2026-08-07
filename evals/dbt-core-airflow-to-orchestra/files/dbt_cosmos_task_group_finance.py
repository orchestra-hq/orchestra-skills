from datetime import datetime

from airflow import DAG
from cosmos import DbtTaskGroup, ProfileConfig, ProjectConfig

# The dbt project's repo is cloned to /usr/local/airflow/clone by a prior step;
# the dbt project itself lives under finance/transform inside that clone, and
# ships a requirements.txt at its root for Python dependencies.
profile_config = ProfileConfig(
    profile_name="finance_analytics",
    target_name="prod",
    profiles_yml_filepath="/usr/local/airflow/clone/finance/transform/profiles.yml",
)

with DAG(
    dag_id="cosmos_finance_dbt",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    finance_dbt_task_group = DbtTaskGroup(
        group_id="finance_dbt_task_group",
        project_config=ProjectConfig(dbt_project_path="/usr/local/airflow/clone/finance/transform"),
        profile_config=profile_config,
        operator_args={"select": "tag:finance", "exclude": "tag:deprecated"},
    )
