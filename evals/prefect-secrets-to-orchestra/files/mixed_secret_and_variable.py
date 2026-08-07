from prefect import task, flow
from prefect.blocks.system import Secret
from prefect.variables import Variable


@task
def extract_from_partner_api():
    api_key = Secret.load("partner-api-key").get()
    database_var = Variable.get("DATABASE_VAR")  # non-sensitive config, e.g. "analytics_prod"

    response = fetch_partner_data(api_key=api_key, database=database_var)
    return response


@flow
def partner_extract_flow():
    extract_from_partner_api()
