from prefect import flow, task

# This repo's .python-version pins 3.14, and the task relies on it:
# the body uses PEP 750 t-strings, which are 3.14-only syntax.


@task
def refresh_forecast():
    import httpx

    region = "eu-west-1"
    resp = httpx.get(t"https://metrics.internal/forecast?region={region}", timeout=30)
    resp.raise_for_status()
    rows = resp.json()["rows"]

    print(f"Refreshed {len(rows)} forecast rows for {region}")


@flow
def forecast_flow():
    refresh_forecast()
