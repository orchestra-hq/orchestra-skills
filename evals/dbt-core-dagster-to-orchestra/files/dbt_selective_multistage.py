from pathlib import Path

from dagster import Definitions
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# This is a monorepo: the dbt project lives under repo/transform, and that
# subdirectory ships its own pyproject.toml + poetry.lock for Python deps.
dbt_project = DbtProject(project_dir=Path("repo") / "transform")
dbt = DbtCliResource(project_dir=dbt_project)


@dbt_assets(manifest=dbt_project.manifest_path, select="tag:marts")
def marts_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["seed"], context=context).stream()
    yield from dbt.cli(
        ["run", "--select", "tag:marts", "--target", "prod"], context=context
    ).stream()
    yield from dbt.cli(["test", "--select", "tag:marts"], context=context).stream()


defs = Definitions(
    assets=[marts_dbt_assets],
    resources={"dbt": dbt},
)
