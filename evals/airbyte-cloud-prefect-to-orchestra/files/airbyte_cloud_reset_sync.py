from prefect import flow
from prefect_airbyte.connections import AirbyteConnection
from prefect_airbyte.flows import trigger_sync_run_and_wait_for_completion

# Airbyte Cloud (hosted) block — configured against api.airbyte.com, API-key auth, no host/port
airbyte_conn = AirbyteConnection.load("finance-airbyte-cloud")


@flow
def reset_finance_flow():
    trigger_sync_run_and_wait_for_completion(
        airbyte_connection=airbyte_conn,
        connection_id="b6f1a2c3-8d4e-4f5a-b6c7-d8e9f0a1b2c3",
        reset_cache=True,
    )
