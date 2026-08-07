from dagster import op, job, Out, Output


def get_new_row_count(table: str) -> int:
    ...  # queries stg_orders for rows landed since the last run


@op(out={"has_new_orders": Out(is_required=False), "no_new_orders": Out(is_required=False)})
def check_staging_orders(context):
    new_row_count = get_new_row_count("stg_orders")
    if new_row_count > 0:
        yield Output(new_row_count, "has_new_orders")
    else:
        yield Output(0, "no_new_orders")


@op
def load_orders(_, count):
    print(f"Loading {count} new orders into FCT_ORDERS")


@op
def send_no_data_notice(_, count):
    print("No new orders landed this run — skipping load, notifying team")


@job
def orders_sync_job():
    has_orders, no_orders = check_staging_orders()
    load_orders(has_orders)
    send_no_data_notice(no_orders)
