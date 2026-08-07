from pathlib import Path

from dagster import Definitions
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# No lockfile/pyproject/requirements.txt is visible anywhere in this repo, so there
# is no signal here for which Python package manager Orchestra should use.
dbt_project = DbtProject(project_dir=Path(__file__).parent / "dbt_project")
dbt_resource = DbtCliResource(project_dir=dbt_project)


@dbt_assets(manifest=dbt_project.manifest_path)
def analytics_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


defs = Definitions(
    assets=[analytics_dbt_assets],
    resources={"dbt": dbt_resource},
)
