# This deployment keeps every warehouse credential in AWS Secrets Manager, under
# "prod/snowflake/analytics". Nothing is stored in Dagster's own config: the
# resource reads the secret at run time and feeds it to SnowflakeResource.

from dagster import ConfigurableResource, Definitions, asset
from dagster_aws.secretsmanager import SecretsManagerResource
from dagster_snowflake import SnowflakeResource
import json


class AnalyticsWarehouse(ConfigurableResource):
    secrets: SecretsManagerResource

    def snowflake(self) -> SnowflakeResource:
        raw = self.secrets.get_client().get_secret_value(
            SecretId="prod/snowflake/analytics"
        )["SecretString"]
        secret = json.loads(raw)
        return SnowflakeResource(
            account=secret["account"],
            user=secret["user"],
            password=secret["password"],
            warehouse="ANALYTICS_WH",
            database="ANALYTICS",
        )


@asset
def orders_daily(warehouse: AnalyticsWarehouse):
    with warehouse.snowflake().get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO ANALYTICS.PUBLIC.ORDERS_DAILY SELECT * FROM RAW.ORDERS"
        )


defs = Definitions(
    assets=[orders_daily],
    resources={
        "warehouse": AnalyticsWarehouse(
            secrets=SecretsManagerResource(region_name="eu-west-2")
        )
    },
)
