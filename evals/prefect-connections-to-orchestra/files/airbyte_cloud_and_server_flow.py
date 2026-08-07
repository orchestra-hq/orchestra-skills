import os

from prefect import flow, task
from prefect_airbyte import AirbyteConnection
from prefect_airbyte.flows import trigger_sync_and_wait_for_completion

# Airbyte Cloud (hosted) — pointed at api.airbyte.com, API-key auth
airbyte_cloud = AirbyteConnection(
    airbyte_server_host="api.airbyte.com",
    airbyte_server_port=443,
    airbyte_api_version="v1",
    connection_id="11111111-2222-3333-4444-555555555555",
)

# Self-hosted Airbyte Server — internal host, basic auth
airbyte_server = AirbyteConnection(
    airbyte_server_host="airbyte-internal.example.com",
    airbyte_server_port=8000,
    connection_id="66666666-7777-8888-9999-000000000000",
    username=os.environ["AIRBYTE_SERVER_USER"],
    password=os.environ["AIRBYTE_SERVER_PASSWORD"],
)


@task
def sync_cloud_connection():
    return trigger_sync_and_wait_for_completion(airbyte_connection=airbyte_cloud)


@task
def sync_server_connection():
    return trigger_sync_and_wait_for_completion(airbyte_connection=airbyte_server)


@flow(name="airbyte-sync-flow")
def airbyte_sync_flow():
    sync_cloud_connection()
    sync_server_connection()
