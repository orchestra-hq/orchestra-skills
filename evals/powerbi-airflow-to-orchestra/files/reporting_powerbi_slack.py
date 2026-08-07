import os

from airflow import DAG
from airflow.providers.microsoft.azure.operators.powerbi import (
    PowerBIDatasetRefreshOperator,
)
from airflow.providers.slack.operators.slack import SlackAPIPostOperator

POWERBI_DATASET_ID = os.getenv("POWERBI_DATASET_ID", "my-dataset-id")
POWERBI_WORKSPACE_ID = os.getenv("POWERBI_WORKSPACE_ID")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#analytics")

with DAG("reporting_powerbi_slack", schedule_interval="@daily", catchup=False) as dag:
    refresh_dashboard_dataset = PowerBIDatasetRefreshOperator(
        task_id="refresh_dashboard_dataset",
        conn_id="powerbi_default",
        dataset_id=POWERBI_DATASET_ID,
        group_id=POWERBI_WORKSPACE_ID,
    )

    notify_slack = SlackAPIPostOperator(
        task_id="notify_slack",
        slack_conn_id="slack_default",
        channel=SLACK_CHANNEL,
        text=(
            ":bar_chart: Power BI dashboard refreshed successfully "
            "(dag: {{ dag.dag_id }}, run: {{ run_id }})."
        ),
    )

    refresh_dashboard_dataset >> notify_slack
