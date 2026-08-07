from dagster import (
    Definitions,
    job,
    op,
    RetryPolicy,
    DailyPartitionsDefinition,
    build_schedule_from_partitioned_job,
)

daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")

# delay is in SECONDS in Dagster — 9000s = 150 minutes, above Orchestra's 120-minute cap.
slow_retry = RetryPolicy(max_retries=3, delay=9000)


@op(retry_policy=slow_retry)
def rebuild_partition(context):
    partition_date = context.partition_key
    ...


@job(partitions_def=daily_partitions)
def backfillable_job():
    rebuild_partition()


backfillable_schedule = build_schedule_from_partitioned_job(backfillable_job)

defs = Definitions(jobs=[backfillable_job], schedules=[backfillable_schedule])
