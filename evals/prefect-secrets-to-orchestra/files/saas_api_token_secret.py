from prefect.blocks.system import Secret
from prefect import task, flow
import requests


@task
def call_billing_api():
    token = Secret.load("billing-api-token").get()
    response = requests.get(
        "https://api.billingprovider.com/v1/invoices",
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()


@flow
def sync_billing_invoices():
    call_billing_api()
