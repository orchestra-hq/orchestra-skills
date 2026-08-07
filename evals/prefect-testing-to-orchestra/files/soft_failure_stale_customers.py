from prefect import flow, task, get_run_logger
from prefect_sqlalchemy import SqlAlchemyConnector


@task
def sync_customers():
    print("Syncing customers table from the CRM source")


@task
def check_customers_freshness():
    logger = get_run_logger()
    connector = SqlAlchemyConnector.load("pg-prod")
    with connector.get_connection() as conn:
        hours = conn.execute(
            "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) / 3600 FROM customers"
        ).scalar()
    # Soft check: just warn, don't fail the flow, if the table is more than a day stale.
    if hours > 24:
        logger.warning(f"Customers table is {hours} hours stale")


@flow
def customers_quality_flow():
    sync_future = sync_customers.submit()
    check_customers_freshness.submit(wait_for=[sync_future])
