from dagster import asset, IOManager, io_manager
import snowflake.connector


class SnowflakeCountIOManager(IOManager):
    """Persists small scalar outputs so downstream ops can load them."""

    def handle_output(self, context, obj):
        context.log.info(f"Persisting {context.name} = {obj}")

    def load_input(self, context):
        return context.upstream_output.metadata.get("value")


@io_manager
def snowflake_count_io_manager():
    return SnowflakeCountIOManager()


@asset(io_manager_key="snowflake_count_io_manager")
def pending_order_count() -> int:
    conn = snowflake.connector.connect()
    count = conn.cursor().execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'pending'"
    ).fetchone()[0]
    return count


@asset
def process_pending_orders(pending_order_count: int):
    if pending_order_count > 0:
        print(f"Processing {pending_order_count} pending orders")
    else:
        print("No pending orders to process")
