---
name: airflow-alerts-to-orchestra
description: "Use this skill when an Airflow DAG uses on_failure_callback, on_success_callback, on_retry_callback, sla_miss_callback, EmailOperator, PagerDutyEventsHook, or any notification/alerting pattern. Covers all six Orchestra alert destination types: SLACK, EMAIL, PAGER_DUTY, MICROSOFT_TEAMS, WEBHOOK, and DATADOG. Read this skill alongside slack-airflow-to-orchestra for complete notification coverage."
---

# Airflow Alerts → Orchestra Alerts (All Destinations)

## Overview

Airflow notifications are spread across callbacks (`on_failure_callback`, `on_success_callback`), dedicated operator tasks (`EmailOperator`, `SlackWebhookOperator`), and hooks (`PagerDutyEventsHook`). Orchestra consolidates all of these into a single `alerts:` block that can appear at the **pipeline root** (fires on overall pipeline status) or on individual **TaskModel** objects (fires on that specific task's status).

---

## AlertModel — Full Schema

```yaml
alerts:
  - name: unique-alert-name       # required, unique within scope
    statuses:                     # required, at least one
      - FAILED                    # FAILED | SUCCEEDED | CANCELLED | WARNING | SKIPPED | ANY_COMPLETED
    destinations:                 # required, at least one
      - integration: SLACK        # NotificationTypesEnum — see table below
        destination: '#channel'   # required for SLACK and EMAIL
        connection_id: null       # required for PAGER_DUTY, TEAMS, WEBHOOK, DATADOG
        parameters: null          # optional — DATADOG priority, WEBHOOK body
    custom_message: null          # optional string, max 200 chars
```

---

## Destination Types — Full Reference

### SLACK
```yaml
destinations:
  - integration: SLACK
    destination: '#data-alerts'    # channel name or member ID — required
    # connection_id not needed — resolved from workspace-level Slack connection
```

### EMAIL
```yaml
destinations:
  - integration: EMAIL
    destination: 'data-team@example.com'   # email address — required
    # connection_id not needed — uses Orchestra's email connection
```

### PAGER_DUTY
```yaml
destinations:
  - integration: PAGER_DUTY
    connection_id: pagerduty_conn_12345    # Orchestra PagerDuty connection — required
    # destination not used
```

### MICROSOFT_TEAMS
```yaml
destinations:
  - integration: MICROSOFT_TEAMS
    connection_id: teams_webhook_12345     # Orchestra Teams connection — required
    # destination not used
```

### WEBHOOK
```yaml
destinations:
  - integration: WEBHOOK
    connection_id: my_webhook_12345        # Orchestra Webhook connection — required
    parameters:
      body:                               # optional — custom JSON body
        event: "pipeline_failed"
        pipeline: "my-pipeline"
```

### DATADOG
```yaml
destinations:
  - integration: DATADOG
    connection_id: datadog_conn_12345      # Orchestra Datadog connection — required
    parameters:
      priority: 3                         # optional — integer 1 (highest) to 5 (lowest)
```

---

## Status Values

| Orchestra status | Airflow equivalent | When it fires |
|---|---|---|
| `FAILED` | `on_failure_callback` | Pipeline/task failed |
| `SUCCEEDED` | `on_success_callback` | Pipeline/task succeeded |
| `WARNING` | `on_retry_callback` (partial) | Task finished with warnings (e.g. test threshold hit) |
| `CANCELLED` | _(no equivalent)_ | Pipeline was manually cancelled |
| `SKIPPED` | _(no equivalent)_ | Task was skipped due to condition |
| `ANY_COMPLETED` | `on_failure_callback` + `on_success_callback` | Fires on any terminal state |

---

## Airflow Pattern → Orchestra Alert

### `on_failure_callback` + `on_success_callback`

```python
# Airflow
default_args = {
    "on_failure_callback": slack_fail_alert,
    "on_success_callback": slack_success_alert,
}
```

```yaml
# Orchestra — pipeline-level alerts
alerts:
  - name: pipeline-failed
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Pipeline failed — check Orchestra logs.'

  - name: pipeline-succeeded
    statuses: [SUCCEEDED]
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
```

### `EmailOperator` task

```python
# Airflow
send_email = EmailOperator(
    task_id="send_completion_email",
    to="data-team@example.com",
    subject="Pipeline complete",
    html_content="Daily ELT finished successfully.",
)
```

```yaml
# Orchestra — pipeline-level alert (no task needed)
alerts:
  - name: completion-email
    statuses: [SUCCEEDED]
    destinations:
      - integration: EMAIL
        destination: 'data-team@example.com'
    custom_message: 'Daily ELT finished successfully.'
```

### `PagerDutyEventsHook` in a callback

```python
# Airflow
def pagerduty_alert(context):
    hook = PagerdutyEventsHook(pagerduty_conn_id="pagerduty")
    hook.send_event(summary=f"Pipeline failed: {context['dag'].dag_id}")
```

```yaml
# Orchestra
alerts:
  - name: pagerduty-on-failure
    statuses: [FAILED]
    destinations:
      - integration: PAGER_DUTY
        connection_id: pagerduty_prod_12345
    custom_message: 'Pipeline failed — oncall required.'
```

### Multiple destinations on one alert

```yaml
# Fire both Slack AND PagerDuty on failure
alerts:
  - name: critical-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#incidents'
      - integration: PAGER_DUTY
        connection_id: pagerduty_prod_12345
    custom_message: 'Critical pipeline failure — immediate attention required.'
```

### Multiple alerts with different statuses and destinations

```yaml
alerts:
  - name: notify-slack-on-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

  - name: page-oncall-on-failure
    statuses: [FAILED]
    destinations:
      - integration: PAGER_DUTY
        connection_id: pagerduty_prod_12345
    custom_message: 'Data pipeline down — SLA at risk.'

  - name: email-on-success
    statuses: [SUCCEEDED]
    destinations:
      - integration: EMAIL
        destination: 'stakeholders@example.com'
    custom_message: 'Daily report data is ready.'

  - name: webhook-any-completion
    statuses: [ANY_COMPLETED]
    destinations:
      - integration: WEBHOOK
        connection_id: monitoring_webhook_12345
```

---

## Pipeline-Level vs Task-Level Alerts

**Pipeline-level** — in the `alerts:` key at the top of the YAML. Fires based on the overall pipeline run status.

```yaml
version: v1
name: my-pipeline
alerts:           # ← pipeline-level
  - name: ...
pipeline:
  ...
```

**Task-level** — in the `alerts:` key on a specific `TaskModel`. Fires when that individual task reaches the status.

```yaml
pipeline:
  stage-001:
    tasks:
      critical-task:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        alerts:        # ← task-level
          - name: dbt-task-failed
            statuses: [FAILED]
            destinations:
              - integration: PAGER_DUTY
                connection_id: pagerduty_prod_12345
```

Use task-level when you need different alert routing per task (e.g. page on-call only for the most critical transformation, not every step).

---

## Gotchas

- **`sla_miss_callback`** — no Orchestra equivalent. SLA monitoring must be handled via external monitoring tools or a time-based sensor.
- **`on_retry_callback`** — closest is `WARNING` status, but Orchestra's WARNING fires on quality test warnings, not on task retries. No direct equivalent for retry-specific notifications.
- **`connection_id` format** — must be the full Orchestra connection name including 5-digit suffix (e.g. `pagerduty_prod_12345`), not just the connection type.
- **SLACK requires `destination`** — omitting the channel name will fail schema validation.
- **PAGER_DUTY/TEAMS/WEBHOOK/DATADOG require `connection_id`** — `destination` is not used for these types.
- **`custom_message` max 200 chars** — longer messages are truncated or rejected.
- **Alert names must be unique** — within their scope (pipeline-level or per-task). Two pipeline-level alerts cannot share a name.

## References

- Orchestra alerts schema: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Orchestra Slack alerts: https://docs.getorchestra.io/docs/alerts/slack
