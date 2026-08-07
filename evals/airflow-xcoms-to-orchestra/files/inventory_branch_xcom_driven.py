from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.dates import days_ago


def check_low_stock_count(ti, **context):
    import snowflake.connector

    conn = snowflake.connector.connect()
    count = conn.cursor().execute(
        "SELECT COUNT(*) FROM inventory WHERE quantity < reorder_threshold"
    ).fetchone()[0]
    ti.xcom_push(key="low_stock_count", value=count)


def decide_branch(ti, **context):
    count = ti.xcom_pull(task_ids="check_low_stock_count", key="low_stock_count")
    return "trigger_reorder_workflow" if count > 0 else "skip_reorder"


with DAG(
    "inventory_reorder_check",
    schedule_interval="@daily",
    start_date=days_ago(1),
) as dag:
    check_count = PythonOperator(
        task_id="check_low_stock_count",
        python_callable=check_low_stock_count,
    )

    branch = BranchPythonOperator(
        task_id="decide_branch",
        python_callable=decide_branch,
    )

    trigger_reorder = PythonOperator(
        task_id="trigger_reorder_workflow",
        python_callable=lambda: print("Triggering reorder workflow"),
    )

    skip_reorder = PythonOperator(
        task_id="skip_reorder",
        python_callable=lambda: print("No low-stock items, skipping reorder"),
    )

    check_count >> branch >> [trigger_reorder, skip_reorder]
