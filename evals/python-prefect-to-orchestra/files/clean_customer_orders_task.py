from prefect import flow, task


@task
def clean_customer_orders():
    import pandas as pd

    df = pd.read_csv("s3://raw-landing-bucket/orders/daily_orders.csv")
    df = df.drop_duplicates(subset=["order_id"])
    df["net_amount"] = df["gross_amount"] - df["discount_amount"]
    df = df[df["net_amount"] >= 0]

    df.to_parquet("s3://curated-bucket/orders/clean_daily_orders.parquet", index=False)
    print(f"Wrote {len(df)} cleaned orders")


@flow
def daily_orders_flow():
    clean_customer_orders()
