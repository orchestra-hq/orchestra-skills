# Automation (configured in the Prefect UI, not Python):
#   Trigger: "Object created" event in s3://raw-uploads/orders/
#   Action:  Run deployment process-orders/prod
#   Polling interval configured in the Automation UI: every 120 seconds
#
# Before Automations existed for this deployment, the same wait was done with
# a plain polling task — kept here as the equivalent Python logic.

import time

import boto3
from prefect import flow, task


@task
def wait_for_orders_file(poll_interval_seconds: int = 120):
    s3 = boto3.client("s3")
    while True:
        response = s3.list_objects_v2(Bucket="raw-uploads", Prefix="orders/")
        if response.get("KeyCount", 0) > 0:
            return response["KeyCount"]
        time.sleep(poll_interval_seconds)


@task
def process_orders(file_count: int):
    ...


@flow(name="process-orders")
def process_orders_flow():
    file_count = wait_for_orders_file()
    process_orders(file_count)
