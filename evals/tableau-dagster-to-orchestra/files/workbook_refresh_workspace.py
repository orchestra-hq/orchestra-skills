from dagster import Definitions, EnvVar
from dagster_tableau import (
    TableauCloudWorkspace,
    load_tableau_asset_specs,
    build_tableau_materializable_assets_definition,
)

tableau_workspace = TableauCloudWorkspace(
    connected_app_client_id=EnvVar("TABLEAU_CLIENT_ID"),
    connected_app_secret_id=EnvVar("TABLEAU_SECRET_ID"),
    connected_app_secret_value=EnvVar("TABLEAU_SECRET_VALUE"),
    username=EnvVar("TABLEAU_USERNAME"),
    site_name="salesteam",
    pod_name="10ax",
)

tableau_specs = load_tableau_asset_specs(tableau_workspace)

sales_dashboard_refresh = build_tableau_materializable_assets_definition(
    resource_key="tableau_workspace",
    specs=[spec for spec in tableau_specs if spec.metadata.get("name") == "Sales Dashboard"],
)

defs = Definitions(
    assets=[sales_dashboard_refresh, *tableau_specs],
    resources={"tableau_workspace": tableau_workspace},
)
