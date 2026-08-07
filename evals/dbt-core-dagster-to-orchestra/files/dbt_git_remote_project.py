import subprocess
from pathlib import Path

from dagster import Definitions
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# The dbt project lives in a separate git repo, one folder ("dbt") in from its
# root. Its root also ships a requirements.txt for its Python dependencies.
DBT_REPO_URL = "git@github.com:acme-co/analytics-dbt.git"
DBT_REPO_BRANCH = "main"
LOCAL_CLONE_DIR = Path("/tmp/analytics-dbt")

if not LOCAL_CLONE_DIR.exists():
    subprocess.run(
        ["git", "clone", "--branch", DBT_REPO_BRANCH, DBT_REPO_URL, str(LOCAL_CLONE_DIR)],
        check=True,
    )

dbt_project = DbtProject(project_dir=LOCAL_CLONE_DIR / "dbt")
dbt_resource = DbtCliResource(project_dir=dbt_project)


@dbt_assets(manifest=dbt_project.manifest_path)
def warehouse_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(
        ["build", "--select", "tag:nightly", "--exclude", "tag:deprecated"],
        context=context,
    ).stream()


defs = Definitions(
    assets=[warehouse_dbt_assets],
    resources={"dbt": dbt_resource},
)
