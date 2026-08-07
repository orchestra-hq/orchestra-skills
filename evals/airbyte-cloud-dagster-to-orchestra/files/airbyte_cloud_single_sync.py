from dagster import Definitions, EnvVar, define_asset_job
from dagster_airbyte import AirbyteCloudResource, build_airbyte_assets

# Airbyte Cloud (hosted) — API key auth, no host/port
airbyte_cloud = AirbyteCloudResource(
    api_key=EnvVar("AIRBYTE_CLOUD_API_KEY"),
)

marketing_assets = build_airbyte_assets(
    connection_id="7e2c9f10-4b3a-4d5e-9f1a-2b3c4d5e6f70",
    destination_tables=["hubspot_contacts", "hubspot_deals"],
    group_name="marketing_raw",
)

sync_marketing_job = define_asset_job(
    name="sync_marketing_job",
    selection=marketing_assets,
)

defs = Definitions(
    assets=marketing_assets,
    jobs=[sync_marketing_job],
    resources={"airbyte": airbyte_cloud},
)
