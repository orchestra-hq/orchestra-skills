from prefect import flow
from prefect.deployments import run_deployment


@flow
def nightly_elt():
    ...


@flow
def build_report():
    ...


@flow
def daily_report_orchestrator():
    # Fire nightly-elt and block until it finishes before continuing
    run_deployment(name="nightly-elt/prod", timeout=600)
    build_report()
