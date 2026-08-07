from prefect import task, flow
import snowflake.connector


@task
def compute_order_total() -> float:
    conn = snowflake.connector.connect()
    total = conn.cursor().execute(
        "SELECT SUM(amount) FROM orders WHERE status = 'completed'"
    ).fetchone()[0]
    return total


@task
def post_total_to_finance(order_total: float):
    print(f"Posting order total of {order_total} to the finance system")


@flow
def daily_order_totals_flow():
    total = compute_order_total()
    post_total_to_finance(total)
