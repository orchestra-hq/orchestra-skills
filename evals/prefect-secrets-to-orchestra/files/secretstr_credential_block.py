from prefect import task, flow
from prefect.blocks.core import Block
from pydantic import SecretStr


class PostgresCredentials(Block):
    host: str
    username: str
    password: SecretStr


@task
def load_customer_dim():
    creds = PostgresCredentials.load("warehouse-prod")
    conn = connect(
        host=creds.host,
        user=creds.username,
        password=creds.password.get_secret_value(),
    )
    conn.execute("INSERT INTO dim_customer SELECT * FROM stg_customer")


@flow
def customer_dim_load_flow():
    load_customer_dim()
