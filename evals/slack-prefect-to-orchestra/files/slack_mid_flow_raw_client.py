import os

from prefect import flow, task
from slack_sdk import WebClient


@task
def run_dbt_build():
    ...


@task
def notify_dbt_complete():
    # No prefect_slack import here at all — this is a plain @task wrapping the raw
    # Slack Web API client, called explicitly as a step in the flow body below.
    WebClient(token=os.environ["SLACK_BOT_TOKEN"]).chat_postMessage(
        channel="#data-team",
        text="dbt build complete — starting downstream loads.",
    )


@task
def load_downstream(_):
    ...


@flow
def nightly_pipeline():
    build_result = run_dbt_build()
    notify_result = notify_dbt_complete(wait_for=[build_result])
    load_downstream(build_result, wait_for=[notify_result])
