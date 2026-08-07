from dagster import op, job, Output, MetadataValue
import pandas as pd


@op
def extract_customers() -> Output[str]:
    df = pd.read_sql("SELECT * FROM customers", con=get_source_conn())
    path = "/tmp/customers.parquet"
    df.to_parquet(path)
    return Output(
        path,
        metadata={
            "num_rows": MetadataValue.int(len(df)),
            "preview": MetadataValue.md(df.head().to_markdown()),
        },
    )


@op
def load_customers(customers_path: str):
    df = pd.read_parquet(customers_path)
    df.to_sql("stg_customers", con=get_warehouse_conn(), if_exists="replace")


@job
def customer_sync_job():
    load_customers(extract_customers())
