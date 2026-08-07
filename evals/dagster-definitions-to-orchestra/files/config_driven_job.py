from dagster import Definitions, job, op, Config, EnvVar, ResourceParam
import requests


class ELTConfig(Config):
    target_env: str = "prod"
    table: str = "orders"


@op
def sync_table(config: ELTConfig, api_key: str = EnvVar("PARTNER_API_KEY")):
    requests.post(
        f"https://partner.example.com/sync/{config.table}",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"env": config.target_env},
    )


@job
def partner_sync_job():
    sync_table()


# No ScheduleDefinition — this job is only ever triggered manually or by an upstream
# asset sensor, never on a cron.
defs = Definitions(jobs=[partner_sync_job])
