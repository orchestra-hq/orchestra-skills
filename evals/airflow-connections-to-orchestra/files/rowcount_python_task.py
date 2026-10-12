from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator


def count_pending_orders() -> int:
    import snowflake.connector

    creds = BaseHook.get_connection("snowflake_prod")
    conn = snowflake.connector.connect(
        account=creds.extra_dejson["account"],
        user=creds.login,
        password=creds.password,
        warehouse="ANALYTICS_WH",
    )
    return conn.cursor().execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]


count_task = PythonOperator(task_id="count_pending_orders", python_callable=count_pending_orders)
