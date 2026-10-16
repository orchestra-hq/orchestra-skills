from prefect import flow, task
from prefect_azure import AzureKeyVaultSecretReference
from prefect_snowflake import SnowflakeCredentials
import snowflake.connector


@task
def load_warehouse_rows():
    # The Snowflake password already lives in Azure Key Vault, in the
    # "analytics-prod" vault, under the secret name "snowflake-analytics".
    secret_ref = AzureKeyVaultSecretReference.load("snowflake-analytics-ref")
    password = secret_ref.get_secret()

    creds = SnowflakeCredentials(
        account="acme-analytics",
        user="ETL_SERVICE",
        password=password,
    )
    conn = snowflake.connector.connect(**creds.dict())
    conn.cursor().execute("INSERT INTO ANALYTICS.PUBLIC.ORDERS SELECT * FROM RAW.ORDERS")


@flow
def load_orders():
    load_warehouse_rows()
