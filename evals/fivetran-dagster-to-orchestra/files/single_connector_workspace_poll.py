from dagster import AssetExecutionContext, Definitions, EnvVar
from dagster_fivetran import FivetranWorkspace, fivetran_assets

fivetran_workspace = FivetranWorkspace(
    account_id=EnvVar("FIVETRAN_ACCOUNT_ID"),
    api_key=EnvVar("FIVETRAN_API_KEY"),
    api_secret=EnvVar("FIVETRAN_API_SECRET"),
)


@fivetran_assets(
    connector_id="calmly_effective",
    name="stripe_sync",
    group_name="fivetran",
    workspace=fivetran_workspace,
)
def stripe_fivetran_assets(context: AssetExecutionContext, fivetran: FivetranWorkspace):
    yield from fivetran.sync_and_poll(context=context)


defs = Definitions(
    assets=[stripe_fivetran_assets],
    resources={"fivetran": fivetran_workspace},
)
