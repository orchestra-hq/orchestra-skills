# Automation (configured in the Prefect UI, not Python):
#   Trigger type: Webhook
#   "POST to this deployment's webhook whenever the upstream 'raw-orders-etl'
#    Orchestra pipeline (pipeline_id 4b71c930-9999-4a11-8888-abcdef654321)
#    completes successfully -> run build-revenue-report/prod"
#
# raw-orders-etl was migrated off Prefect into Orchestra already; it now
# calls this deployment's webhook URL from an Orchestra WEBHOOK alert
# configured on that pipeline's SUCCEEDED status. There is no polling or
# file/row check here — the webhook only exists as a bridge to the
# now-migrated upstream job.

from prefect import flow, task


@task
def build_revenue_report():
    ...


@flow(name="build-revenue-report")
def build_revenue_report_flow():
    build_revenue_report()
