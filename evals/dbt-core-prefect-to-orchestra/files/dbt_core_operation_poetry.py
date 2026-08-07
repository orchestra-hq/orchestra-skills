from prefect import flow
from prefect_dbt.cli import DbtCoreOperation

# This project ships a pyproject.toml + poetry.lock at its root, so Python deps
# are managed with Poetry rather than pip or uv.


@flow
def dbt_flow():
    with DbtCoreOperation(
        commands=["dbt seed", "dbt run --select tag:daily --target prod", "dbt test --select tag:daily"],
        project_dir="dbt_project",
    ) as dbt_op:
        dbt_op.run()


if __name__ == "__main__":
    dbt_flow()
