---
name: dagster-alerts-to-orchestra
description: "Use this skill when a Dagster project sends notifications: @run_failure_sensor, @run_status_sensor, make_email_on_run_failure_sensor, make_slack_on_run_failure_sensor, PagerDuty/Teams/Datadog resources used in hooks or sensors, or @failure_hook/@success_hook. Covers all six Orchestra alert destination types: SLACK, EMAIL, PAGER_DUTY, MICROSOFT_TEAMS, WEBHOOK, and DATADOG. Read alongside slack-dagster-to-orchestra for complete notification coverage."
---

# Dagster Alerts -> Orchestra Alerts (All Destinations)

## Overview

Dagster notifications are spread across **run-status sensors** (`@run_failure_sensor`, `@run_status_sensor`), **prebuilt factories** (`make_slack_on_run_failure_sensor`, `make_email_on_run_failure_sensor`, `make_teams_on_run_failure_sensor`), **op hooks** (`@failure_hook`, `@success_hook`), and **integration resources** (`PagerDutyService`, `MSTeamsResource`, `DatadogResource`). Orchestra consolidates all of these into a single `alerts:` block.

For the Orchestra-side syntax (full `AlertModel` schema, all six destination types, status enum, pipeline-level vs task-level placement, gotchas) see the shared reference: [`../../references/alerts.md`](../../references/alerts.md). This skill covers only the Dagster-specific mapping.

---

## Status Values — Dagster equivalent

| Orchestra status | Dagster equivalent | When it fires |
|---|---|---|
| `FAILED` | `@run_failure_sensor` / `RunStatusSensor(FAILURE)` / `@failure_hook` | Pipeline/task failed |
| `SUCCEEDED` | `RunStatusSensor(SUCCESS)` / `@success_hook` | Pipeline/task succeeded |
| `WARNING` | asset check warn / soft failure | Finished with warnings |
| `CANCELLED` | run canceled | Manually cancelled |
| `SKIPPED` | _(no direct equivalent)_ | Skipped due to condition |
| `ANY_COMPLETED` | success + failure sensors | Any terminal state |

---

## Dagster Pattern -> Orchestra Alert

### `@run_failure_sensor` (whole job)

```python
@run_failure_sensor
def slack_on_failure(context):
    ...
```

```yaml
alerts:
  - name: pipeline-failed
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Pipeline failed — check Orchestra logs.'
```

### `make_email_on_run_failure_sensor`

```python
email_sensor = make_email_on_run_failure_sensor(
    email_from="alerts@example.com", email_to=["data-team@example.com"],
)
```

```yaml
alerts:
  - name: completion-email
    statuses: [FAILED]
    destinations:
      - integration: EMAIL
        destination: 'data-team@example.com'
    custom_message: 'Pipeline failed.'
```

### `PagerDutyService` in a `@run_failure_sensor`

```python
@run_failure_sensor
def pagerduty_on_failure(context, pagerduty: PagerDutyService):
    pagerduty.get_session().trigger_incident(summary=..., severity="critical")
```

```yaml
alerts:
  - name: pagerduty-on-failure
    statuses: [FAILED]
    destinations:
      - integration: PAGER_DUTY
        connection_id: pagerduty_prod_12345
    custom_message: 'Pipeline failed — oncall required.'
```

### `@failure_hook` / `@success_hook` on a single op -> task-level alert

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

---

## Gotchas (Dagster-specific)

- **`@run_failure_sensor` / `@run_status_sensor` -> pipeline-level alert** — `RUN_FAILURE` -> `[FAILED]`, `RUN_SUCCESS` -> `[SUCCEEDED]`.
- **op-scoped `@failure_hook`/`@success_hook` -> task-level alert**.
- **`make_*_on_run_failure_sensor` factories -> alerts block** with the matching destination.
- **Freshness/SLA sensors** — `build_sensor_for_freshness_checks` / `FreshnessPolicy` have no direct alert mapping; use external monitoring or model as an Orchestra test/sensor.

See the shared reference for Orchestra-side gotchas (`connection_id` format, `custom_message` length, alert name uniqueness, etc.).

## References

- Shared Orchestra alerts syntax: [`../../references/alerts.md`](../../references/alerts.md)
- Orchestra Slack alerts: https://docs.getorchestra.io/docs/alerts/slack
- Dagster run status sensors: https://docs.dagster.io/concepts/automation/sensors#run-status-sensors
- Dagster hooks: https://docs.dagster.io/concepts/ops-jobs-graphs/op-hooks
