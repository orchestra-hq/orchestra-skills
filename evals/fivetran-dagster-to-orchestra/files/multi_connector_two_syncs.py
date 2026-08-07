from dagster import AssetExecutionContext, Definitions, EnvVar
from dagster_fivetran import FivetranWorkspace, fivetran_assets

fivetran_workspace = FivetranWorkspace(
    account_id=EnvVar("FIVETRAN_ACCOUNT_ID"),
    api_key=EnvVar("FIVETRAN_API_KEY"),
    api_secret=EnvVar("FIVETRAN_API_SECRET"),
)


@fivetran_assets(
    connector_id="deeply_current",
    name="hubspot_sync",
    group_name="fivetran",
    workspace=fivetran_workspace,
)
def hubspot_fivetran_assets(context: AssetExecutionContext, fivetran: FivetranWorkspace):
    yield from fivetran.sync_and_poll(context=context)


@fivetran_assets(
    connector_id="loosely_secondary",
    name="netsuite_sync",
    group_name="fivetran",
    workspace=fivetran_workspace,
)
def netsuite_fivetran_assets(context: AssetExecutionContext, fivetran: FivetranWorkspace):
    yield from fivetran.sync_and_poll(context=context)


defs = Definitions(
    assets=[hubspot_fivetran_assets, netsuite_fivetran_assets],
    resources={"fivetran": fivetran_workspace},
)
