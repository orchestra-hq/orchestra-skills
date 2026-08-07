from prefect import flow, task


@task
def check_staging_orders() -> int:
    # Queries stg_orders for rows landed since the last run and returns the count.
    return run_query("SELECT COUNT(*) AS row_count FROM staging.stg_orders WHERE loaded_at > last_watermark()")


@task
def load_orders(count: int):
    print(f"Loading {count} new orders into FCT_ORDERS")


@task
def send_no_data_notice():
    print("No new orders landed this run — skipping load, notifying team")


@flow
def orders_sync_flow():
    # The branch decision depends on a value only known once the flow is running,
    # not on anything passed in at trigger time.
    check_future = check_staging_orders.submit()
    new_row_count = check_future.result()

    if new_row_count > 0:
        load_orders.submit(new_row_count, wait_for=[check_future])
    else:
        send_no_data_notice.submit(wait_for=[check_future])
