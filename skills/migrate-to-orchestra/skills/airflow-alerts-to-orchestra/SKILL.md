---
name: airflow-alerts-to-orchestra
description: "Use this skill when an Airflow DAG uses on_failure_callback, on_success_callback, on_retry_callback, sla_miss_callback, EmailOperator, PagerDutyEventsHook, or any notification/alerting pattern. Covers all six Orchestra alert destination types: SLACK, EMAIL, PAGER_DUTY, MICROSOFT_TEAMS, WEBHOOK, and DATADOG. Read this skill alongside slack-airflow-to-orchestra for complete notification coverage."
---

# Airflow Alerts → Orchestra Alerts (All Destinations)

## Overview

Airflow notifications are spread across callbacks (`on_failure_callback`, `on_success_callback`), dedicated operator tasks (`EmailOperator`, `SlackWebhookOperator`), and hooks (`PagerDutyEventsHook`). Orchestra consolidates all of these into a single `alerts:` block.

For the Orchestra-side syntax (full `AlertModel` schema, all six destination types, status enum, pipeline-level vs task-level placement, gotchas) see the shared reference: [`../../references/alerts.md`](../../references/alerts.md). This skill covers only the Airflow-specific mapping.

---

## Status Values — Airflow equivalent

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

### `on_failure_callback` on an individual task → task-level alert

```yaml
pipeline:
  stage-001:
    tasks:
      critical-task:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        alerts:
          - name: dbt-task-failed
            statuses: [FAILED]
            destinations:
              - integration: PAGER_DUTY
                connection_id: pagerduty_prod_12345
```

Use task-level when different Airflow tasks register different callbacks — mirror that with
per-task `alerts:` instead of one pipeline-level block.

---

## Gotchas (Airflow-specific)

- **`sla_miss_callback`** — no Orchestra equivalent. SLA monitoring must be handled via external monitoring tools or a time-based sensor.
- **`on_retry_callback`** — closest is `WARNING` status, but Orchestra's WARNING fires on quality test warnings, not on task retries. No direct equivalent for retry-specific notifications.

See the shared reference for Orchestra-side gotchas (`connection_id` format, `custom_message` length, alert name uniqueness, etc.).

## References

- Shared Orchestra alerts syntax: [`../../references/alerts.md`](../../references/alerts.md)
- Orchestra Slack alerts: https://docs.getorchestra.io/docs/alerts/slack
