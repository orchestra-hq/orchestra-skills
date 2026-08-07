import os

from prefect import flow, task


@task(retries=3, retry_delay_seconds=90, timeout_seconds=300)
def sync_region_metrics(region: str, lookback_days: int):
    import requests

    api_key = os.environ["METRICS_API_KEY"]
    resp = requests.get(
        f"https://metrics.internal.acme.com/api/v1/regions/{region}/summary",
        params={"lookback_days": lookback_days},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    resp.raise_for_status()
    print(f"Synced {region} metrics for last {lookback_days} days: {resp.json()}")


@flow
def region_metrics_flow(region: str = "us-east-1", lookback_days: int = 7):
    sync_region_metrics(region=region, lookback_days=lookback_days)
