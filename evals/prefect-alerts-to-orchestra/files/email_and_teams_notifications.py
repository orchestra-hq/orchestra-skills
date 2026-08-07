from prefect import flow


def send_failure_email(flow, flow_run, state):
    send_email(
        email_from="alerts@example.com",
        email_to=["data-team@example.com"],
        subject=f"Flow {flow.name} failed",
        body=str(state.message),
    )


# Separately, a Prefect Automation posts to Microsoft Teams on the same failure trigger
# (configured in the Prefect UI, not in code) — the target webhook connection is
# `teams_webhook_54321`.


@flow(on_failure=[send_failure_email])
def nightly_etl():
    ...
