import os

import tableau_server_client as TSC
from prefect import flow, task


@task
def refresh_sales_dashboard():
    tableau_auth = TSC.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_TOKEN"],
        site_id="salesteam",
    )
    server = TSC.Server("https://10ax.online.tableau.com")
    with server.auth.sign_in(tableau_auth):
        # Sales Dashboard lives in the Sales project
        workbook = server.workbooks.filter(name="Sales Dashboard").pop()
        server.workbooks.refresh(workbook)


@flow
def refresh_sales_flow():
    refresh_sales_dashboard()
