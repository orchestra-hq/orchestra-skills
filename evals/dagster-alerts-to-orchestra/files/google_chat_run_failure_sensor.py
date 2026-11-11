"""Dagster run-failure sensor that posts to a Google Chat space incoming webhook.

The Orchestra Google Chat connection for this space is `google_chat_data_alerts_12345`.
"""

import os

import requests
from dagster import DefaultSensorStatus, RunFailureSensorContext, run_failure_sensor


@run_failure_sensor(default_status=DefaultSensorStatus.RUNNING)
def google_chat_on_run_failure(context: RunFailureSensorContext):
    requests.post(
        os.environ["GOOGLE_CHAT_WEBHOOK_URL"],
        json={"text": f"Run {context.dagster_run.job_name} failed: {context.failure_event.message}"},
    )
