from dagster import Definitions, EnvVar
from dagster_slack import SlackResource, make_slack_on_run_failure_sensor

# Only the bot token varies by environment; the channel itself is fixed.
slack_on_failure = make_slack_on_run_failure_sensor(
    channel="#eng-oncall",
    slack_token=EnvVar("SLACK_BOT_TOKEN"),
    text_fn=lambda ctx: f"Pipeline {ctx.dagster_run.job_name} failed — check Orchestra logs.",
)

defs = Definitions(
    sensors=[slack_on_failure],
    resources={"slack": SlackResource(token=EnvVar("SLACK_BOT_TOKEN"))},
)
