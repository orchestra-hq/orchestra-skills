from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from datetime import datetime


def has_new_records():
    print("Checking the staging table for newly landed records")
    return True  # placeholder — real check queries the warehouse for new rows


def process_new_records():
    print("Processing newly landed records")


def send_summary():
    print("Sending a summary notification of processed records")


with DAG(
    dag_id="conditional_processing",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@hourly",
    catchup=False,
) as dag:
    check_new_data = ShortCircuitOperator(
        task_id="check_new_data",
        python_callable=has_new_records,
    )
    process = PythonOperator(task_id="process_new_records", python_callable=process_new_records)
    notify = PythonOperator(task_id="send_summary", python_callable=send_summary)

    # If check_new_data returns False, both process and notify are skipped entirely.
    check_new_data >> process >> notify
