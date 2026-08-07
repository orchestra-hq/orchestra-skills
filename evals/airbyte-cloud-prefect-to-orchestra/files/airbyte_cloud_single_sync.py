from prefect import flow
from prefect_airbyte.connections import AirbyteConnection
from prefect_airbyte.flows import trigger_sync_run_and_wait_for_completion

# Airbyte Cloud (hosted) block — configured against api.airbyte.com, API-key auth, no host/port
airbyte_conn = AirbyteConnection.load("marketing-airbyte-cloud")


@flow
def sync_marketing_flow():
    trigger_sync_run_and_wait_for_completion(
        airbyte_connection=airbyte_conn,
        connection_id="7e2c9f10-4b3a-4d5e-9f1a-2b3c4d5e6f70",
    )
