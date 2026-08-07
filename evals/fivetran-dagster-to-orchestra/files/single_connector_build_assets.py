from dagster import Definitions, EnvVar
from dagster_fivetran import FivetranResource, build_fivetran_assets

fivetran_instance = FivetranResource(
    api_key=EnvVar("FIVETRAN_API_KEY"),
    api_secret=EnvVar("FIVETRAN_API_SECRET"),
)

salesforce_assets = build_fivetran_assets(
    connector_id="brightly_typical",
    destination_tables=["salesforce.accounts", "salesforce.opportunities"],
    poll_interval=15,
    poll_timeout=600,
)

defs = Definitions(
    assets=salesforce_assets,
    resources={"fivetran": fivetran_instance},
)
