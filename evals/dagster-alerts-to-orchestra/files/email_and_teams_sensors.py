from dagster import Definitions
from dagster import make_email_on_run_failure_sensor

email_sensor = make_email_on_run_failure_sensor(
    email_from="alerts@example.com",
    email_to=["data-team@example.com"],
)

# Separately, a Microsoft Teams webhook is posted to on the same failure via a custom
# run status sensor wrapping MSTeamsResource — omitted here for brevity, but the target
# webhook connection is `teams_webhook_54321`.

defs = Definitions(sensors=[email_sensor])
