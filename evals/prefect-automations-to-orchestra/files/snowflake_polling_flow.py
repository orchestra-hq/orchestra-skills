import time

from prefect import flow, task
from prefect_snowflake import SnowflakeConnector


@task
def wait_for_daily_orders(poll_interval_seconds: int = 30):
    connector = SnowflakeConnector.load("sf-prod")
    with connector.get_connection() as conn:
        while True:
            count = conn.cursor().execute(
                "SELECT COUNT(*) FROM raw.orders WHERE order_date = CURRENT_DATE"
            ).fetchone()[0]
            if count > 0:
                return count
            time.sleep(poll_interval_seconds)


@task
def process_daily_orders(order_count: int):
    ...


@flow(name="process-daily-orders")
def process_daily_orders_flow():
    order_count = wait_for_daily_orders()
    process_daily_orders(order_count)
