import os

import boto3
from dagster import Config, op


class UploadConfig(Config):
    bucket_name: str
    prefix: str


@op
def upload_report_to_s3(config: UploadConfig):
    client = boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    local_path = "/tmp/weekly_report.csv"
    key = f"{config.prefix}/weekly_report.csv"
    client.upload_file(local_path, config.bucket_name, key)
    print(f"Uploaded to s3://{config.bucket_name}/{key}")
