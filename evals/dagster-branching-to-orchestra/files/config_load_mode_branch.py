from dagster import op, job, Out, Output, Config


class BackfillConfig(Config):
    full_refresh: bool = False


@op(out={"backfill": Out(is_required=False), "incremental": Out(is_required=False)})
def choose_load_mode(config: BackfillConfig):
    if config.full_refresh:
        yield Output(True, "backfill")
    else:
        yield Output(True, "incremental")


@op
def run_backfill(_, ready):
    print("Running full historical backfill of the warehouse load")


@op
def run_incremental(_, ready):
    print("Running incremental warehouse load since last watermark")


@job
def warehouse_load_job():
    backfill, incremental = choose_load_mode()
    run_backfill(backfill)
    run_incremental(incremental)
