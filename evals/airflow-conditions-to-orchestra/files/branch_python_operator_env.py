from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from datetime import datetime


def choose_branch(**context):
    env = context["params"]["env"]
    return "run_prod_load" if env == "prod" else "run_staging_load"


def run_prod_load():
    print("Loading data into the prod warehouse")


def run_staging_load():
    print("Loading data into the staging warehouse")


with DAG(
    dag_id="env_aware_load",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"env": "prod"},
) as dag:
    choose_env = BranchPythonOperator(
        task_id="choose_env",
        python_callable=choose_branch,
    )
    prod_load = PythonOperator(task_id="run_prod_load", python_callable=run_prod_load)
    staging_load = PythonOperator(task_id="run_staging_load", python_callable=run_staging_load)

    # The env param decides at trigger time which branch runs; the other is skipped.
    choose_env >> [prod_load, staging_load]
