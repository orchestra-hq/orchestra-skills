from prefect import flow


@flow
def child_ingest_flow(env: str = "prod"):
    ...


@flow
def parent_pipeline_flow():
    # Subflow: runs inline, tracked as a child run of this flow's execution
    child_ingest_flow(env="prod")
