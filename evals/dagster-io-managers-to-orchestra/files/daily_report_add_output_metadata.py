from dagster import op, job
import boto3


@op
def export_daily_report(context) -> str:
    rows = generate_report_rows()
    key = f"reports/daily/{context.run.run_id}.csv"
    boto3.client("s3").put_object(Bucket="analytics-reports", Key=key, Body=to_csv(rows))

    context.add_output_metadata({
        "s3_key": key,
        "row_count": len(rows),
    })
    return key


@op
def notify_report_ready(report_key: str):
    print(f"Report ready at s3://analytics-reports/{report_key}")


@job
def daily_report_job():
    notify_report_ready(export_daily_report())
