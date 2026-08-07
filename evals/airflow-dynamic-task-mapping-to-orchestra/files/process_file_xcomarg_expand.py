from airflow.decorators import dag, task
from airflow.utils.dates import days_ago


@dag(schedule_interval="@daily", start_date=days_ago(1), catchup=False)
def process_files_dynamic_expand():

    @task
    def list_files() -> list[str]:
        import boto3

        s3 = boto3.client("s3")
        response = s3.list_objects_v2(Bucket="my-bucket", Prefix="incoming/")
        return [obj["Key"] for obj in response.get("Contents", [])]

    @task
    def process_file(filename: str):
        print(f"Processing file {filename}")

    files = list_files()
    process_file.expand(filename=files)


process_files_dynamic_expand()
