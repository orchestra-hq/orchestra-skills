from dagster import EnvVar, OpExecutionContext, job, op
from dagster_slack import SlackResource


@op
def run_dbt_build():
    ...


@op(required_resource_keys={"slack"})
def notify_dbt_complete(context: OpExecutionContext):
    context.resources.slack.get_client().chat_postMessage(
        channel="#data-team",
        text="dbt build complete — starting downstream loads.",
    )


@op
def load_downstream(_):
    ...


@job(resource_defs={"slack": SlackResource(token=EnvVar("SLACK_BOT_TOKEN"))})
def nightly_pipeline():
    load_downstream(notify_dbt_complete(run_dbt_build()))
