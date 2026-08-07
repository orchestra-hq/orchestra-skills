from dagster import op, job, DynamicOut, DynamicOutput, Out, Output


@op(out=DynamicOut())
def list_regions(context):
    for region in ["us", "eu", "apac"]:
        yield DynamicOutput(region, mapping_key=region)


@op
def sync_region(context, region: str):
    print(f"Syncing regional extract for {region}")
    return region


@op(out={"has_failures": Out(is_required=False), "all_clean": Out(is_required=False)})
def check_sync_results(context, results):
    failed = [r for r in results if r is None]
    if failed:
        yield Output(failed, "has_failures")
    else:
        yield Output(True, "all_clean")


@op
def send_failure_alert(_, failed_regions):
    print(f"Regions failed to sync: {failed_regions}")


@job
def region_sync_job():
    regions = list_regions()
    results = regions.map(sync_region).collect()
    failures = check_sync_results(results)
    send_failure_alert(failures)
