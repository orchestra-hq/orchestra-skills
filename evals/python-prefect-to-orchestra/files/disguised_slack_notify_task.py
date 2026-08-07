import os

from prefect import flow, task
from slack_sdk import WebClient


@task
def notify_pipeline_complete(status: str) -> None:
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(
        channel="#data-alerts",
        text=f":white_check_mark: Nightly load finished — status: {status}.",
    )


@flow
def nightly_load_flow():
    status = "Completed"
    notify_pipeline_complete(status=status)
