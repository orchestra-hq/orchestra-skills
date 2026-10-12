from prefect import flow
from prefect_dbt.cli.commands import DbtCoreOperation
from prefect_snowflake.credentials import SnowflakeCredentials


@flow
def analytics_dbt_build():
    # profiles.yml reads DBT_SF_* env vars, filled from the Snowflake block that
    # other flows in this project already use.
    sf = SnowflakeCredentials.load("snowflake-prod")
    DbtCoreOperation(
        commands=["dbt build --select tag:daily"],
        project_dir="warehouse/dbt",
        profiles_dir="warehouse/dbt",
        env={
            "DBT_SF_ACCOUNT": sf.account,
            "DBT_SF_USER": sf.user,
            "DBT_SF_PASSWORD": sf.password.get_secret_value(),
        },
    ).run()
