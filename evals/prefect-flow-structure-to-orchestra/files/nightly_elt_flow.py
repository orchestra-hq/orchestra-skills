from prefect import flow, task
from prefect.client.schemas.schedules import CronSchedule

# A global concurrency limit named "nightly-elt-limit" caps this flow to 1 concurrent
# run — created out-of-band via `prefect gcl create nightly-elt-limit --limit 1` and
# referenced here only by tag, the same way `dagster/concurrency_key` works.
CONCURRENCY_LIMIT_TAG = "nightly-elt-limit"


@task(retries=2, retry_delay_seconds=300)
def extract():
    ...


@task(retries=2, retry_delay_seconds=300)
def load(extracted):
    ...


@flow(
    name="nightly-elt",
    retries=2,
    retry_delay_seconds=300,
    timeout_seconds=3600,
    tags=["elt", CONCURRENCY_LIMIT_TAG, "data-team"],
)
def nightly_elt():
    load(extract())


if __name__ == "__main__":
    nightly_elt.serve(
        name="nightly-elt-deployment",
        schedules=[CronSchedule(cron="0 2 * * *", timezone="UTC")],
        limit=1,
    )
