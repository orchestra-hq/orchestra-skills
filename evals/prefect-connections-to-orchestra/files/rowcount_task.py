from prefect import task
from prefect_snowflake.database import SnowflakeConnector


@task
def count_pending_orders() -> int:
    connector = SnowflakeConnector.load("snowflake-prod")
    with connector.get_connection() as conn:
        return conn.cursor().execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]
