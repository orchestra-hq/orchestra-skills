from dagster import EnvVar, HookContext, job, op, success_hook
from dagster_slack import SlackResource


@success_hook(required_resource_keys={"slack"})
def notify_on_load_success(context: HookContext):
    context.resources.slack.get_client().chat_postMessage(
        channel="#warehouse-notifications",
        text=f"{context.op.name} succeeded for run {context.run_id}.",
    )


@op
def extract_data():
    ...


@op(hooks={notify_on_load_success})
def load_warehouse(_):
    ...


@job(resource_defs={"slack": SlackResource(token=EnvVar("SLACK_BOT_TOKEN"))})
def nightly_warehouse_job():
    load_warehouse(extract_data())
