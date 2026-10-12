from dagster import Definitions, EnvVar, asset
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

dbt_project = DbtProject(project_dir="warehouse/dbt")

# profiles.yml reads DBT_SF_* env vars; the same Snowflake credentials are already
# configured as a Dagster resource used by other assets in this code location.
dbt_resource = DbtCliResource(
    project_dir=dbt_project,
    profiles_dir="warehouse/dbt",
    global_config_flags=[],
)


@dbt_assets(manifest=dbt_project.manifest_path)
def analytics_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build", "--select", "tag:daily"], context=context).stream()


defs = Definitions(
    assets=[analytics_dbt_assets],
    resources={
        "dbt": dbt_resource,
        "snowflake_account": EnvVar("DBT_SF_ACCOUNT"),
        "snowflake_user": EnvVar("DBT_SF_USER"),
        "snowflake_password": EnvVar("DBT_SF_PASSWORD"),
    },
)
