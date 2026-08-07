import os

from prefect import flow, task
from slack_sdk import WebClient


def notify_on_load_success(task, task_run, state):
    WebClient(token=os.environ["SLACK_BOT_TOKEN"]).chat_postMessage(
        channel="#warehouse-notifications",
        text=f"{task.name} succeeded for run {task_run.id}.",
    )


@task
def extract_data():
    ...


@task(on_completion=[notify_on_load_success])
def load_warehouse(data):
    ...


@flow
def nightly_warehouse_flow():
    data = extract_data()
    load_warehouse(data)
