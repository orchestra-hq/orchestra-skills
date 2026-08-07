from airflow import DAG
from great_expectations_provider.operators.great_expectations import GreatExpectationsOperator
from datetime import datetime

with DAG(
    dag_id="customer_events_ge_checkpoint",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    # No native Orchestra integration exists for Great Expectations — this checkpoint
    # validates the customer_events table against a suite of expectations.
    run_ge_checkpoint = GreatExpectationsOperator(
        task_id="run_ge_checkpoint",
        checkpoint_name="customer_events_checkpoint",
        data_context_root_dir="/opt/airflow/great_expectations",
    )
