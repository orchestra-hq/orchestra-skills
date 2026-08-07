from dagster import Definitions, EnvVar, define_asset_job
from dagster_airbyte import AirbyteResource, build_airbyte_assets

# Self-hosted Airbyte Server — host/port + basic auth, not API-key-only
airbyte_server = AirbyteResource(
    host="airbyte-internal.mycorp.com",
    port="8000",
    username=EnvVar("AIRBYTE_SERVER_USER"),
    password=EnvVar("AIRBYTE_SERVER_PASSWORD"),
)

warehouse_assets = build_airbyte_assets(
    connection_id="d3e4f5a6-7890-4bcd-9ef0-123456789abc",
    destination_tables=["inventory_items", "warehouse_locations"],
    group_name="warehouse_raw",
)

sync_warehouse_job = define_asset_job(
    name="sync_warehouse_job",
    selection=warehouse_assets,
)

defs = Definitions(
    assets=warehouse_assets,
    jobs=[sync_warehouse_job],
    resources={"airbyte": airbyte_server},
)
