from dagster import Definitions, asset, EnvVar
from dagster_snowflake import SnowflakeResource

snowflake = SnowflakeResource(
    account=EnvVar("SNOWFLAKE_ACCOUNT"),
    user=EnvVar("SNOWFLAKE_USER"),
    password=EnvVar("SNOWFLAKE_PASSWORD"),
    warehouse="ANALYTICS_WH",
    database="ANALYTICS",
    role="TRANSFORMER",
)


@asset
def daily_revenue(snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO analytics.core.daily_revenue SELECT * FROM analytics.core.orders"
        )


defs = Definitions(assets=[daily_revenue], resources={"snowflake": snowflake})
