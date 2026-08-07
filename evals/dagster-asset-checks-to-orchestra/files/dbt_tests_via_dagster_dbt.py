from dagster import Definitions
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

analytics_project = DbtProject(project_dir="analytics_dbt")


@dbt_assets(manifest=analytics_project.manifest_path)
def analytics_dbt_assets(context, dbt: DbtCliResource):
    # Builds the models then runs dbt's built-in test suite (schema + custom SQL tests)
    # against them in the same invocation.
    yield from dbt.cli(["build"], context=context).stream()


defs = Definitions(
    assets=[analytics_dbt_assets],
    resources={"dbt": DbtCliResource(project_dir=analytics_project)},
)
