from dagster import op, job, Definitions
from dagster_ssh import SSHResource

remote_server = SSHResource(
    remote_host="etl-box.internal",
    username="etl_svc",
    password=None,  # key-based auth is configured on the host
)


@op
def sync_extract_files(context, ssh: SSHResource):
    ssh.execute_remote_command(
        "cd /data/extracts && ./run_sync.sh --mode incremental"
    )


@job
def nightly_extract_sync():
    sync_extract_files()


defs = Definitions(jobs=[nightly_extract_sync], resources={"ssh": remote_server})
