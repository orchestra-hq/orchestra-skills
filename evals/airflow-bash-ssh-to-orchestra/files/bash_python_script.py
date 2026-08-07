from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG("nightly_customer_etl", schedule_interval="@daily", catchup=False) as dag:
    run_etl_script = BashOperator(
        task_id="run_etl_script",
        bash_command="cd /opt/airflow && python scripts/transform_customers.py --env prod",
    )
