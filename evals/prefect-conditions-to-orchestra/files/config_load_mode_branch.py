from prefect import flow, task


@task
def run_backfill():
    print("Running full historical backfill of the warehouse load")


@task
def run_incremental():
    print("Running incremental warehouse load since last watermark")


@flow
def warehouse_load_flow(full_refresh: bool = False):
    # Decision is made from a flow parameter supplied at trigger time,
    # not from anything computed during the run.
    if full_refresh:
        run_backfill.submit()
    else:
        run_incremental.submit()
