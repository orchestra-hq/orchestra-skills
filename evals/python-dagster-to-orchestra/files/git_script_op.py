import subprocess

from dagster import op


@op
def run_external_etl_script():
    subprocess.run(
        ["git", "clone", "https://github.com/acme-data/etl-scripts.git", "/tmp/etl-scripts"],
        check=True,
    )
    subprocess.run(
        ["python", "/tmp/etl-scripts/transform/reconcile_inventory.py", "--env", "prod"],
        check=True,
    )
