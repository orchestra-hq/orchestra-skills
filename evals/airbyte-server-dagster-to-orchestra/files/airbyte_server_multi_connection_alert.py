from dagster import Definitions, EnvVar, define_asset_job, ScheduleDefinition
from dagster_airbyte import AirbyteResource, build_airbyte_assets
from dagster_slack import make_slack_on_run_failure_sensor

# Self-hosted Airbyte Server — host/port + basic auth, not API-key-only
airbyte_server = AirbyteResource(
    host="airbyte.onprem.internal",
    port="8001",
    username=EnvVar("AIRBYTE_SERVER_USER"),
    password=EnvVar("AIRBYTE_SERVER_PASSWORD"),
)

hr_assets = build_airbyte_assets(
    connection_id="11aa22bb-33cc-44dd-55ee-66ff77aa88bb",
    destination_tables=["employees", "departments"],
    group_name="hr_raw",
)

billing_assets = build_airbyte_assets(
    connection_id="99887766-5544-3322-1100-ffeeddccbbaa",
    destination_tables=["invoices"],
    group_name="billing_raw",
)

sync_all_job = define_asset_job(
    name="sync_hr_and_billing_job",
    selection=[*hr_assets, *billing_assets],
)

nightly_schedule = ScheduleDefinition(job=sync_all_job, cron_schedule="30 1 * * *")

slack_on_failure = make_slack_on_run_failure_sensor(
    channel="#data-eng-alerts",
    slack_token=EnvVar("SLACK_TOKEN"),
)

defs = Definitions(
    assets=[*hr_assets, *billing_assets],
    jobs=[sync_all_job],
    schedules=[nightly_schedule],
    sensors=[slack_on_failure],
    resources={"airbyte": airbyte_server},
)
