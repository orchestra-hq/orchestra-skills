"""Prefect flow with an on_failure hook posting to a Google Chat space webhook.

The Orchestra Google Chat connection for this space is `google_chat_data_alerts_12345`.
"""

import os

import requests
from prefect import flow


def notify_google_chat(flow, flow_run, state):
    requests.post(
        os.environ["GOOGLE_CHAT_WEBHOOK_URL"],
        json={"text": f"Flow {flow.name} failed: {state.message}"},
    )


@flow(on_failure=[notify_google_chat])
def nightly_etl():
    ...
