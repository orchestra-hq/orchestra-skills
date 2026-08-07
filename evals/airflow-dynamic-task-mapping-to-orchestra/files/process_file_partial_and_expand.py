from airflow.decorators import dag, task
from airflow.utils.dates import days_ago


@dag(schedule_interval="@daily", start_date=days_ago(1), catchup=False)
def process_files_partial_and_expand():

    @task
    def process_file(bucket: str, dry_run: bool, filename: str):
        print(f"Processing {filename} from {bucket} (dry_run={dry_run})")

    process_file.partial(bucket="my-bucket", dry_run=False).expand(
        filename=["a.csv", "b.csv"]
    )


process_files_partial_and_expand()
