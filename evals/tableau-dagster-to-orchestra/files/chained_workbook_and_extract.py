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
    site_name="marketingteam",
    pod_name="us-east-1",
)

tableau_specs = load_tableau_asset_specs(tableau_workspace)

# "Marketing Dashboard" is built directly on top of the "Marketing Extract"
# datasource, so dagster-tableau's own lineage makes the dashboard asset
# depend on the extract asset.
marketing_extract_refresh = build_tableau_materializable_assets_definition(
    resource_key="tableau_workspace",
    specs=[s for s in tableau_specs if s.metadata.get("name") == "Marketing Extract"],
)

marketing_dashboard_refresh = build_tableau_materializable_assets_definition(
    resource_key="tableau_workspace",
    specs=[s for s in tableau_specs if s.metadata.get("name") == "Marketing Dashboard"],
)

defs = Definitions(
    assets=[marketing_extract_refresh, marketing_dashboard_refresh, *tableau_specs],
    resources={"tableau_workspace": tableau_workspace},
)
