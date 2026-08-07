from prefect import flow, task
import datadog


def page_datadog_on_task_failure(task, task_run, state):
    datadog.api.Event.create(
        title=f"{task.name} failed",
        text="Critical transformation step failed — immediate attention required.",
        alert_type="error",
        priority="normal",
    )


@task(on_failure=[page_datadog_on_task_failure])
def critical_transform():
    ...


@task
def downstream_report(data):
    ...


@flow
def revenue_pipeline():
    result = critical_transform()
    downstream_report(result)
