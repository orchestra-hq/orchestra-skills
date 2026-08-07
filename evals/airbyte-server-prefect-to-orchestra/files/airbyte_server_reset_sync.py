from prefect import flow
from prefect_airbyte.connections import AirbyteConnection
from prefect_airbyte.flows import trigger_sync_run_and_wait_for_completion

# Self-hosted Airbyte Server block — configured against airbyte.onprem.internal:8001,
# basic auth (NOT api.airbyte.com / Airbyte Cloud)
airbyte_conn = AirbyteConnection.load("billing-airbyte-server")


@flow
def reset_billing_flow():
    trigger_sync_run_and_wait_for_completion(
        airbyte_connection=airbyte_conn,
        connection_id="99887766-5544-3322-1100-ffeeddccbbaa",
        reset_cache=True,
    )
