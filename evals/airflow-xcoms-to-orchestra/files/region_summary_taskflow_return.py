from airflow.decorators import dag, task
from airflow.utils.dates import days_ago


@dag(schedule_interval="@daily", start_date=days_ago(1), catchup=False)
def region_summary_taskflow():

    @task
    def extract_region_file() -> str:
        path = "/tmp/us-east_report.csv"
        print(f"Writing region extract to {path}")
        return path

    @task
    def summarize_region_file(path: str):
        print(f"Summarizing region report at {path}")

    summarize_region_file(extract_region_file())


region_summary_taskflow()
