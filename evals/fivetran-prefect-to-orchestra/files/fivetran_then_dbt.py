from prefect import flow
from prefect_dbt.cli import DbtCoreOperation
from prefect_fivetran import FivetranConnector
from prefect_fivetran.fivetran import trigger_sync_and_wait_for_completion


@flow
def sync_then_transform_flow():
    # The "fivetran-prod" block stores api_key/api_secret plus this connector's
    # slug: connector_id=quietly_frontier (NetSuite connector).
    connector = FivetranConnector.load("fivetran-prod")
    trigger_sync_and_wait_for_completion(fivetran_connector=connector)

    # dbt build runs only after the Fivetran sync above has landed fresh data.
    with DbtCoreOperation(
        commands=["dbt build --select tag:daily"],
        project_dir="dbt_project",
    ) as dbt_op:
        dbt_op.run()


if __name__ == "__main__":
    sync_then_transform_flow()
