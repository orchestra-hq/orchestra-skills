from prefect import task, flow


@task
def check_low_stock_count() -> int:
    conn = get_warehouse_conn()
    count = conn.cursor().execute(
        "SELECT COUNT(*) FROM inventory WHERE quantity < reorder_threshold"
    ).fetchone()[0]
    return count


@task
def trigger_reorder_workflow(low_stock_count: int):
    if low_stock_count > 0:
        print(f"Triggering reorder workflow for {low_stock_count} low-stock items")
    else:
        print("No items below reorder threshold, skipping reorder")


@flow
def inventory_monitor_flow():
    low_stock_count = check_low_stock_count.submit().result()
    trigger_reorder_workflow(low_stock_count)
