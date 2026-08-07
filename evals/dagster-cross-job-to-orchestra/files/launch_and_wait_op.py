import time

from dagster import job, op
from dagster_graphql import DagsterGraphQLClient


@op
def trigger_reporting_and_wait(context):
    client = DagsterGraphQLClient("dagster-webserver", port_number=3000)
    run_id = client.submit_job_execution(
        "reporting_job",
        run_config={"ops": {"build_report": {"config": {"env": "prod"}}}},
    )
    status = client.get_run_status(run_id)
    while status.is_in_progress:
        time.sleep(10)
        status = client.get_run_status(run_id)
    if not status.is_success:
        raise Exception(f"reporting_job run {run_id} did not succeed: {status}")
    return run_id


@op
def publish_dashboard(_context):
    ...


@job
def orchestration_job():
    publish_dashboard(trigger_reporting_and_wait())
