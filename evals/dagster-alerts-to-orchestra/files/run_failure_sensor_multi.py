from dagster import run_failure_sensor, RunFailureSensorContext
from dagster_pagerduty import PagerDutyService


@run_failure_sensor
def critical_pipeline_failure(context: RunFailureSensorContext, pagerduty: PagerDutyService):
    pagerduty.get_session().trigger_incident(
        summary=f"Pipeline {context.dagster_run.job_name} failed",
        severity="critical",
    )
    # Also posts to #incidents via a separate Slack integration configured on the sensor.
