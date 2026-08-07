from dagster import Definitions, EnvVar, define_asset_job, ScheduleDefinition
from dagster_airbyte import AirbyteCloudResource, build_airbyte_assets
from dagster_slack import make_slack_on_run_failure_sensor

# Airbyte Cloud (hosted) — API key auth, no host/port
airbyte_cloud = AirbyteCloudResource(
    api_key=EnvVar("AIRBYTE_CLOUD_API_KEY"),
)

salesforce_assets = build_airbyte_assets(
    connection_id="a4d8e2f0-1234-4abc-9def-56789abcdef0",
    destination_tables=["salesforce_accounts", "salesforce_opportunities"],
    group_name="crm_raw",
)

netsuite_assets = build_airbyte_assets(
    connection_id="c9b7a6d5-4321-4fed-8cba-0987654321ff",
    destination_tables=["netsuite_invoices"],
    group_name="finance_raw",
)

sync_all_job = define_asset_job(
    name="sync_all_airbyte_cloud_job",
    selection=[*salesforce_assets, *netsuite_assets],
)

daily_sync_schedule = ScheduleDefinition(job=sync_all_job, cron_schedule="0 3 * * *")

slack_on_failure = make_slack_on_run_failure_sensor(
    channel="#data-alerts",
    slack_token=EnvVar("SLACK_TOKEN"),
)

defs = Definitions(
    assets=[*salesforce_assets, *netsuite_assets],
    jobs=[sync_all_job],
    schedules=[daily_sync_schedule],
    sensors=[slack_on_failure],
    resources={"airbyte": airbyte_cloud},
)
