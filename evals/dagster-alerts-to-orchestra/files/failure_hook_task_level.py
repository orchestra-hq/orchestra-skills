from dagster import op, job, failure_hook, HookContext
from dagster_datadog import DatadogResource


@failure_hook(required_resource_keys={"datadog"})
def page_on_critical_task_failure(context: HookContext):
    datadog: DatadogResource = context.resources.datadog
    datadog.get_client().event(
        title=f"{context.op.name} failed",
        text="Critical transformation step failed — immediate attention required.",
        alert_type="error",
        priority="normal",
    )


@op(hooks={page_on_critical_task_failure})
def critical_transform():
    ...


@op
def downstream_report(_):
    ...


@job
def revenue_pipeline():
    downstream_report(critical_transform())
