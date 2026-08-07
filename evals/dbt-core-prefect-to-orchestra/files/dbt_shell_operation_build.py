from prefect import flow
from prefect_shell import ShellOperation

# No lockfile, pyproject.toml, or requirements.txt is visible anywhere in this
# repo, so there's no signal for which Python package manager Orchestra should use.


@flow
def dbt_build_flow():
    with ShellOperation(
        commands=["dbt build --select tag:nightly"],
        working_dir="transform",
    ) as shell_op:
        shell_op.run()


if __name__ == "__main__":
    dbt_build_flow()
