from dagster import Definitions, op, job, EnvVar
from dagster_airbyte import AirbyteCloudResource, AirbyteResource

# Airbyte Cloud (hosted) — API key auth
airbyte_cloud = AirbyteCloudResource(
    api_key=EnvVar("AIRBYTE_CLOUD_API_KEY"),
    workspace_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
)

# Self-hosted Airbyte Server — host/port, not API-key-only
airbyte_server = AirbyteResource(
    host="airbyte-internal.example.com",
    port="8000",
    username=EnvVar("AIRBYTE_SERVER_USER"),
    password=EnvVar("AIRBYTE_SERVER_PASSWORD"),
)


@op
def sync_cloud_connection(airbyte_cloud: AirbyteCloudResource):
    airbyte_cloud.sync_and_poll(connection_id="11111111-2222-3333-4444-555555555555")


@op
def sync_server_connection(airbyte_server: AirbyteResource):
    airbyte_server.sync_and_poll(connection_id="66666666-7777-8888-9999-000000000000")


@job
def airbyte_sync_job():
    sync_cloud_connection()
    sync_server_connection()


defs = Definitions(
    jobs=[airbyte_sync_job],
    resources={"airbyte_cloud": airbyte_cloud, "airbyte_server": airbyte_server},
)
