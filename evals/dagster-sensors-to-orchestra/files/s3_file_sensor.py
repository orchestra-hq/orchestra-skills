from dagster import sensor, RunRequest, SkipReason, Definitions, job, op
from dagster_aws.s3 import S3Resource


@op
def process_orders():
    ...


@job
def process_orders_job():
    process_orders()


@sensor(job=process_orders_job, minimum_interval_seconds=90)
def orders_file_sensor(context, s3: S3Resource):
    response = s3.get_client().list_objects_v2(
        Bucket="daily-uploads", Prefix="orders/"
    )
    if response.get("KeyCount", 0) > 0:
        yield RunRequest(run_key="orders-file-arrived")
    else:
        yield SkipReason("orders file not yet present")


defs = Definitions(
    jobs=[process_orders_job],
    sensors=[orders_file_sensor],
    resources={"s3": S3Resource()},
)
