from dagster import asset


@asset
def cleaned_orders():
    import pandas as pd

    df = pd.read_csv("s3://raw-data-bucket/orders/orders.csv")
    df = df.dropna(subset=["order_id", "customer_id"])
    df["order_total"] = df["quantity"] * df["unit_price"]
    df = df[df["order_total"] > 0]

    df.to_parquet("s3://curated-data-bucket/orders/cleaned_orders.parquet", index=False)
    print(f"Wrote {len(df)} cleaned orders")
