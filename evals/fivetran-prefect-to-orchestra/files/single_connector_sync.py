from prefect import flow
from prefect_fivetran import FivetranConnector
from prefect_fivetran.fivetran import trigger_sync_and_wait_for_completion


@flow
def fivetran_flow():
    # The "fivetran-prod" block stores api_key/api_secret plus this connector's
    # slug: connector_id=bronzing_regularly (Salesforce connector).
    connector = FivetranConnector.load("fivetran-prod")
    result = trigger_sync_and_wait_for_completion(fivetran_connector=connector)
    return result


if __name__ == "__main__":
    fivetran_flow()
