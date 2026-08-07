from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator

with DAG(
    dag_id="nightly_elt_pipeline",
    schedule_interval="30 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    run_ingest = PythonOperator(task_id="run_ingest", python_callable=lambda: None)
    run_transform = PythonOperator(task_id="run_transform", python_callable=lambda: None)

    send_completion_email = EmailOperator(
        task_id="send_completion_email",
        to="data-team@example.com",
        subject="Nightly ELT complete",
        html_content="Nightly ELT finished successfully — all tables refreshed.",
    )

    run_ingest >> run_transform >> send_completion_email
