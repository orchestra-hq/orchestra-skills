from prefect import flow
from prefect_dbt.cli import DbtCoreOperation

# .python-version pins this project to 3.13, and pyproject.toml declares
# requires-python = ">=3.13". Deps are managed with uv (uv.lock at the root).


@flow
def warehouse_dbt_flow():
    with DbtCoreOperation(
        commands=["dbt build --select tag:nightly"],
        project_dir="analytics",
    ) as dbt_op:
        dbt_op.run()


if __name__ == "__main__":
    warehouse_dbt_flow()
