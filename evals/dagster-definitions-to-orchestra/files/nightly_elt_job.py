from dagster import Definitions, job, op, ScheduleDefinition, RetryPolicy, Backoff

default_retry = RetryPolicy(max_retries=2, delay=300, backoff=Backoff.LINEAR)


@op(retry_policy=default_retry)
def extract():
    ...


@op(retry_policy=default_retry)
def load(extracted):
    ...


@job(
    tags={
        "dagster/max_runtime": 3600,
        "dagster/concurrency_key": "elt",
        "dagster/max_concurrent": 1,
        "team": "data-team",
    }
)
def nightly_elt():
    load(extract())


nightly_schedule = ScheduleDefinition(
    job=nightly_elt,
    cron_schedule="0 2 * * *",
    execution_timezone="UTC",
)

defs = Definitions(jobs=[nightly_elt], schedules=[nightly_schedule])
