from dagster import (
    AssetKey,
    Definitions,
    EventLogEntry,
    RunRequest,
    SensorEvaluationContext,
    asset_sensor,
    define_asset_job,
)

# `raw_orders` is materialized by a job in a separate code location
# (the "ingestion" deployment); this code location only consumes it.
reporting_job = define_asset_job("reporting_job", selection=["daily_order_summary"])


@asset_sensor(asset_key=AssetKey("raw_orders"), job=reporting_job)
def raw_orders_materialized_sensor(
    context: SensorEvaluationContext, asset_event: EventLogEntry
):
    yield RunRequest(run_key=context.cursor, run_config={})


defs = Definitions(
    jobs=[reporting_job],
    sensors=[raw_orders_materialized_sensor],
)
