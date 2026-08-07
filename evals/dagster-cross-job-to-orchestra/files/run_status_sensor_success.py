from dagster import (
    Definitions,
    DagsterRunStatus,
    RunRequest,
    job,
    op,
    run_status_sensor,
)


@op
def extract_and_load():
    ...


@job
def nightly_elt():
    extract_and_load()


@op
def build_report():
    ...


@job
def daily_report():
    build_report()


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    monitored_jobs=[nightly_elt],
    request_job=daily_report,
)
def trigger_report_on_elt_success(context):
    return RunRequest(run_config={"ops": {"build_report": {"config": {"env": "prod"}}}})


defs = Definitions(
    jobs=[nightly_elt, daily_report],
    sensors=[trigger_report_on_elt_success],
)
