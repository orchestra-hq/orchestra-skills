import os

import tableau_server_client as TSC
from prefect import flow, task


@task
def refresh_finance_extract():
    tableau_auth = TSC.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_PAT_NAME"],
        personal_access_token=os.environ["TABLEAU_PAT_SECRET"],
        site_id="financeteam",
    )
    server = TSC.Server("https://10ax.online.tableau.com")
    with server.auth.sign_in(tableau_auth):
        # Finance Extract datasource lives in the Finance project
        datasource = server.datasources.filter(name="Finance Extract").pop()
        server.datasources.refresh(datasource)


@flow
def refresh_finance_extract_flow():
    refresh_finance_extract()
