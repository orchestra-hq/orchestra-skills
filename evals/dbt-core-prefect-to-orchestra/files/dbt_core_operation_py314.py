from prefect import flow
from prefect_dbt.cli import DbtCoreOperation

# .python-version pins this project to 3.14, and pyproject.toml declares
# requires-python = ">=3.14". Deps are installed from requirements.txt.


@flow
def hourly_dbt_flow():
    with DbtCoreOperation(
        commands=["dbt build --select tag:hourly"],
        project_dir="warehouse",
    ) as dbt_op:
        dbt_op.run()


if __name__ == "__main__":
    hourly_dbt_flow()
