from prefect import flow
from prefect_airbyte.connections import AirbyteConnection
from prefect_airbyte.flows import trigger_sync_run_and_wait_for_completion

# Self-hosted Airbyte Server block — configured against airbyte-internal.mycorp.com:8000,
# basic auth (NOT api.airbyte.com / Airbyte Cloud)
airbyte_conn = AirbyteConnection.load("warehouse-airbyte-server")


@flow
def sync_warehouse_flow():
    trigger_sync_run_and_wait_for_completion(
        airbyte_connection=airbyte_conn,
        connection_id="d3e4f5a6-7890-4bcd-9ef0-123456789abc",
    )
