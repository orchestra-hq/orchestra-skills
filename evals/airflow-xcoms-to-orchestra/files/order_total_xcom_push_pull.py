from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import snowflake.connector


def compute_order_total(ti, **context):
    conn = snowflake.connector.connect()
    total = conn.cursor().execute(
        "SELECT SUM(amount) FROM orders WHERE status = 'completed'"
    ).fetchone()[0]
    ti.xcom_push(key="order_total", value=total)


def post_total_to_finance(ti, **context):
    total = ti.xcom_pull(task_ids="compute_order_total", key="order_total")
    print(f"Posting order total of {total} to the finance system")


with DAG(
    "daily_order_totals",
    schedule_interval="@daily",
    start_date=days_ago(1),
) as dag:
    compute_total = PythonOperator(
        task_id="compute_order_total",
        python_callable=compute_order_total,
    )

    post_total = PythonOperator(
        task_id="post_total_to_finance",
        python_callable=post_total_to_finance,
    )

    compute_total >> post_total
