# airflow.cfg on this deployment:
#
#   [secrets]
#   backend = airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
#   backend_kwargs = {"connections_prefix": "airflow/connections"}
#
# Every conn_id below resolves through AWS Secrets Manager; there are no
# metadata-DB rows and no AIRFLOW_CONN_* env vars for them.

from airflow import DAG
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from datetime import datetime

with DAG(
    dag_id="daily_orders_rollup",
    start_date=datetime(2024, 1, 1),
    schedule="0 6 * * *",
    catchup=False,
) as dag:
    rollup_orders = SnowflakeOperator(
        task_id="rollup_orders",
        snowflake_conn_id="snowflake_analytics",
        sql="INSERT INTO ANALYTICS.PUBLIC.ORDERS_DAILY SELECT * FROM RAW.ORDERS",
    )
