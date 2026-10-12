from dagster import EnvVar, op
from dagster_snowflake import SnowflakeResource

snowflake_prod = SnowflakeResource(
    account=EnvVar("SNOWFLAKE_ACCOUNT"),
    user=EnvVar("SNOWFLAKE_USER"),
    password=EnvVar("SNOWFLAKE_PASSWORD"),
    warehouse="ANALYTICS_WH",
)


@op(required_resource_keys={"snowflake_prod"})
def count_pending_orders(context) -> int:
    with context.resources.snowflake_prod.get_connection() as conn:
        return conn.cursor().execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]
