import os

from prefect import flow, task
from prefect_snowflake import SnowflakeConnector, SnowflakeCredentials

snowflake_creds = SnowflakeCredentials(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
)

snowflake_connector = SnowflakeConnector(
    credentials=snowflake_creds,
    database="ANALYTICS",
    warehouse="ANALYTICS_WH",
    schema="CORE",
)


@task
def load_daily_revenue():
    with snowflake_connector.get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO analytics.core.daily_revenue SELECT * FROM analytics.core.orders"
        )


@flow(name="daily-revenue-load")
def daily_revenue_flow():
    load_daily_revenue()
