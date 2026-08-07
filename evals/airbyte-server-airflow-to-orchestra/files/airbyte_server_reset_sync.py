from airflow import DAG
from airflow.providers.airbyte.hooks.airbyte import AirbyteHook
from airflow.operators.python import PythonOperator
from datetime import datetime

CONNECTION_ID = "99887766-5544-3322-1100-ffeeddccbbaa"


def reset_billing_connection():
    # Airflow connection "airbyte_self_hosted_billing" points at airbyte.onprem.internal:8001
    # (self-hosted Airbyte Server, basic auth — NOT api.airbyte.com / Airbyte Cloud)
    hook = AirbyteHook(airbyte_conn_id="airbyte_self_hosted_billing")
    job = hook.submit_reset_connection(connection_id=CONNECTION_ID)
    hook.wait_for_job(job_id=job.job_id, wait_seconds=5, timeout=3600)


with DAG(
    dag_id="airbyte_server_billing_reset",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@weekly",
    catchup=False,
) as dag:
    reset_billing = PythonOperator(
        task_id="reset_billing_connection",
        python_callable=reset_billing_connection,
    )
