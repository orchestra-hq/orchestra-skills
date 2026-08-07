from airflow import DAG
from airflow.providers.ssh.operators.ssh import SSHOperator

with DAG("remote_warehouse_sync", schedule_interval="@hourly", catchup=False) as dag:
    sync_extract_files = SSHOperator(
        task_id="sync_extract_files",
        ssh_conn_id="etl_box",
        command="cd /data/extracts && ./warehouse_sync.sh --mode incremental",
    )
