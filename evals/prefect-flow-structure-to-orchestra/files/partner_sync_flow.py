import os

import httpx
from prefect import flow, task


@task
def sync_table(table: str, target_env: str):
    api_key = os.environ["PARTNER_API_KEY"]
    httpx.post(
        f"https://partner.example.com/sync/{table}",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"env": target_env},
    )


@flow(name="partner-sync")
def partner_sync(target_env: str = "prod", table: str = "orders"):
    sync_table(table=table, target_env=target_env)


# No .serve()/.deploy() call with a schedule — this flow is only ever triggered
# manually or kicked off by an upstream automation, never on a cron.
if __name__ == "__main__":
    partner_sync()
