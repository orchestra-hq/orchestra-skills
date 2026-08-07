from prefect import flow, task, allow_failure


@task
def purge_temp_tables():
    # Best-effort cleanup of scratch tables from the previous run. Occasionally
    # fails if a table is mid-vacuum, but that should never block the load.
    drop_scratch_schema("staging_tmp")


@task
def load_orders() -> int:
    print("Loading orders into the warehouse")
    return count_rows_loaded("orders")


@task
def send_load_failure_alert():
    print("Order load returned zero rows — investigate upstream source")


@flow
def warehouse_load_flow():
    cleanup_future = purge_temp_tables.submit()
    # allow_failure means load_orders proceeds even if purge_temp_tables fails.
    load_future = load_orders.submit(wait_for=[allow_failure(cleanup_future)])
    if load_future.result() == 0:
        send_load_failure_alert.submit(wait_for=[load_future])
