from dagster import asset, asset_check, AssetCheckResult, AssetCheckSeverity, Definitions
from dagster_snowflake import SnowflakeResource


@asset
def orders(snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        conn.cursor().execute("INSERT INTO orders SELECT * FROM orders_staging")


@asset_check(asset=orders)
def no_null_order_ids(snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        nulls = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE order_id IS NULL"
        ).fetchone()[0]
    return AssetCheckResult(passed=nulls == 0, metadata={"null_count": nulls})


@asset_check(asset=orders, severity=AssetCheckSeverity.WARN)
def orders_not_stale(snowflake: SnowflakeResource):
    # Soft check: flag (don't fail the run) if orders haven't landed in 7 days.
    with snowflake.get_connection() as conn:
        stale = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE created_at < CURRENT_DATE - 7"
        ).fetchone()[0]
    return AssetCheckResult(passed=stale == 0, metadata={"stale_rows": stale})


defs = Definitions(
    assets=[orders],
    asset_checks=[no_null_order_ids, orders_not_stale],
    resources={"snowflake": SnowflakeResource(account="xy12345", user="svc_dagster")},
)
