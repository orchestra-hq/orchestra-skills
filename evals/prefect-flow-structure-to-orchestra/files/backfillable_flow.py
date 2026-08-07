from datetime import timedelta

from prefect import flow, task
from prefect.client.schemas.schedules import IntervalSchedule

# retry_delay_seconds is in SECONDS in Prefect — 9000s = 150 minutes, above
# Orchestra's 120-minute retry_delay cap.
@task(retries=3, retry_delay_seconds=9000)
def rebuild_partition(partition_date: str):
    ...


@flow(name="backfillable-flow", retries=3, retry_delay_seconds=9000)
def backfillable_flow(partition_date: str = "2024-01-01"):
    rebuild_partition(partition_date)


if __name__ == "__main__":
    # A 5.5 hour interval has no clean 6-field cron equivalent.
    backfillable_flow.serve(
        name="backfillable-flow-deployment",
        schedules=[IntervalSchedule(interval=timedelta(hours=5, minutes=30))],
    )
