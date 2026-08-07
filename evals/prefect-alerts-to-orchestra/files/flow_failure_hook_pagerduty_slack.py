import requests
from prefect import flow


PAGERDUTY_URL = "https://events.pagerduty.com/v2/enqueue"


def page_pagerduty(flow, flow_run, state):
    requests.post(
        PAGERDUTY_URL,
        json={
            "routing_key": "pd_integration_key",
            "event_action": "trigger",
            "payload": {
                "summary": f"Flow {flow.name} failed",
                "severity": "critical",
            },
        },
    )


def post_slack_incident(flow, flow_run, state):
    # Also posts to #incidents via a separate Slack integration configured on the hook.
    ...


@flow(on_failure=[page_pagerduty, post_slack_incident])
def critical_pipeline():
    ...
