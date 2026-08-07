import os

import requests
from dagster import ConfigurableResource, Definitions, job, op


class TableauRestResource(ConfigurableResource):
    """Hand-rolled Tableau REST client — dagster-tableau has no dataflow-style
    extract-only refresh helper, so this calls the REST API directly."""

    server_url: str
    site_content_url: str
    pat_name: str
    pat_secret: str

    def _auth_token(self) -> str:
        resp = requests.post(
            f"{self.server_url}/api/3.21/auth/signin",
            json={
                "credentials": {
                    "personalAccessTokenName": self.pat_name,
                    "personalAccessTokenSecret": self.pat_secret,
                    "site": {"contentUrl": self.site_content_url},
                }
            },
        )
        resp.raise_for_status()
        return resp.json()["credentials"]["token"]

    def refresh_datasource(self, project_name: str, datasource_name: str):
        token = self._auth_token()
        headers = {"X-Tableau-Auth": token}
        # datasource_id lookup by project_name/datasource_name omitted for brevity
        requests.post(
            f"{self.server_url}/api/3.21/sites/{self.site_content_url}/datasources/refresh",
            headers=headers,
            json={"project_name": project_name, "datasource_name": datasource_name},
        )


tableau_rest = TableauRestResource(
    server_url="https://10ax.online.tableau.com",
    site_content_url="financeteam",
    pat_name=os.environ["TABLEAU_PAT_NAME"],
    pat_secret=os.environ["TABLEAU_PAT_SECRET"],
)


@op
def refresh_finance_extract(tableau: TableauRestResource):
    tableau.refresh_datasource(project_name="Finance", datasource_name="Finance Extract")


@job
def finance_extract_job():
    refresh_finance_extract()


defs = Definitions(jobs=[finance_extract_job], resources={"tableau": tableau_rest})
