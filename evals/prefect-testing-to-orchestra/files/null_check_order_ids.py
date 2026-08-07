from prefect import flow, task
from prefect_snowflake import SnowflakeConnector


@task
def load_orders():
    connector = SnowflakeConnector.load("sf-prod")
    with connector.get_connection() as conn:
        conn.cursor().execute("INSERT INTO orders SELECT * FROM orders_staging")


@task
def check_no_null_order_ids():
    connector = SnowflakeConnector.load("sf-prod")
    with connector.get_connection() as conn:
        nulls = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE order_id IS NULL"
        ).fetchone()[0]
    assert nulls == 0, f"Found {nulls} null order IDs"


@flow
def orders_quality_flow():
    load_future = load_orders.submit()
    check_no_null_order_ids.submit(wait_for=[load_future])
