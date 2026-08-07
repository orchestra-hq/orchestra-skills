from airflow import DAG
from airflow.providers.tableau.operators.tableau import TableauOperator
from datetime import datetime

with DAG(
    dag_id="refresh_finance_extract_dag",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    refresh_finance_ds = TableauOperator(
        task_id="refresh_finance_extract",
        resource="datasources",
        method="refresh",
        find="Finance Extract",
        match_with="name",
        tableau_conn_id="tableau_cloud_prod",
        blocking_refresh=True,
    )
