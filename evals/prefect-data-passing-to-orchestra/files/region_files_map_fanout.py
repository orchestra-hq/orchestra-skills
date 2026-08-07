from prefect import task, flow


@task
def process_region_file(region: str) -> str:
    path = f"/tmp/{region}_report.csv"
    print(f"Processing extract for region {region}, writing to {path}")
    return path


@task
def combine_region_reports(paths: list[str]):
    print(f"Combining {len(paths)} region reports into a single summary")


@flow
def regional_reports_flow():
    regions = ["us-east", "us-west", "eu-central", "ap-southeast"]
    futures = process_region_file.map(regions)
    paths = [f.result() for f in futures]
    combine_region_reports(paths)
