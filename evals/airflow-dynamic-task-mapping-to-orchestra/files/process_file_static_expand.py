from airflow.decorators import dag, task
from airflow.utils.dates import days_ago


@dag(schedule_interval="@daily", start_date=days_ago(1), catchup=False)
def process_files_static_expand():

    @task
    def process_file(filename: str, region: str):
        print(f"Processing file {filename} for region {region}")

    # Airflow computes the cross product of filename x region at parse time,
    # so this fans out into 3 x 2 = 6 mapped task instances.
    process_file.expand(
        filename=["a.csv", "b.csv", "c.csv"],
        region=["us-east", "eu-central"],
    )


process_files_static_expand()
