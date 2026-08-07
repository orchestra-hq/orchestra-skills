from prefect import flow
from prefect_slack import SlackWebhook


def post_failure_to_slack(flow, flow_run, state):
    SlackWebhook.load("data-alerts").notify(
        body=f"Flow {flow.name} failed — check Orchestra logs.",
        channel="#eng-oncall",
    )


@flow(on_failure=[post_failure_to_slack])
def nightly_ingest():
    ...
