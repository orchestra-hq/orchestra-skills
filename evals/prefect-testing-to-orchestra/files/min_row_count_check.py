from prefect import flow, task
from google.cloud import bigquery


@task
def load_daily_events():
    print("Loading today's events into analytics.events_raw")


@task
def check_daily_event_volume():
    client = bigquery.Client()
    query_job = client.query(
        "SELECT COUNT(*) AS row_count FROM analytics.events_raw WHERE load_date = CURRENT_DATE()"
    )
    count = list(query_job.result())[0]["row_count"]
    if count < 5000:
        raise ValueError(f"Only {count} events loaded today — expected at least 5000")


@flow
def events_quality_flow():
    load_future = load_daily_events.submit()
    check_daily_event_volume.submit(wait_for=[load_future])
