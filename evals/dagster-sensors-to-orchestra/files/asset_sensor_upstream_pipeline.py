from dagster import asset_sensor, EventLogEntry, RunRequest, AssetKey, Definitions, job, op

UPSTREAM_ASSET = AssetKey("raw_orders")


@op
def build_revenue_report():
    ...


@job
def revenue_report_job():
    build_revenue_report()


@asset_sensor(asset_key=UPSTREAM_ASSET, job=revenue_report_job, minimum_interval_seconds=120)
def raw_orders_materialized_sensor(context, asset_event: EventLogEntry):
    yield RunRequest(run_key=context.cursor)


defs = Definitions(jobs=[revenue_report_job], sensors=[raw_orders_materialized_sensor])
