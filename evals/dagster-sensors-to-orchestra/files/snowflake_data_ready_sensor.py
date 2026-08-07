from dagster import sensor, RunRequest, SkipReason, Definitions, job, op
from dagster_snowflake import SnowflakeResource


@op
def process_daily_orders():
    ...


@job
def process_daily_orders_job():
    process_daily_orders()


@sensor(job=process_daily_orders_job, minimum_interval_seconds=45)
def daily_orders_ready_sensor(context, snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        count = conn.cursor().execute(
            "SELECT COUNT(*) FROM raw.orders WHERE order_date = CURRENT_DATE"
        ).fetchone()[0]
    if count > 0:
        yield RunRequest(run_key=f"orders-ready-{context.cursor}")
    else:
        yield SkipReason("no orders loaded yet today")


defs = Definitions(
    jobs=[process_daily_orders_job],
    sensors=[daily_orders_ready_sensor],
    resources={"snowflake": SnowflakeResource(account="acme", user="svc_dagster")},
)
