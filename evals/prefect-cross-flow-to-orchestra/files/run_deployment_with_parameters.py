from prefect import flow
from prefect.deployments import run_deployment


@flow
def daily_report_orchestrator():
    run_deployment(
        name="daily-report/prod",
        parameters={"env": "prod", "report_date": "{{ scheduled_start_time }}"},
        timeout=300,
    )
