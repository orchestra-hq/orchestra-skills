from dagster import asset_sensor, AssetKey, RunRequest, SensorEvaluationContext

# orders_raw is materialised early in the nightly_elt job, which then spends another
# 90 minutes on unrelated assets. The finance job only needs orders_raw.
@asset_sensor(
    asset_key=AssetKey("orders_raw"),
    job_name="finance_close",
    minimum_interval_seconds=120,
)
def orders_raw_sensor(context: SensorEvaluationContext, asset_event):
    yield RunRequest(run_key=context.cursor)
