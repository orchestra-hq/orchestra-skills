# Orchestra alerts — shared reference

Canonical Orchestra-side syntax for the `alerts:` block, shared by `airflow-alerts-to-orchestra`,
`dagster-alerts-to-orchestra`, and `prefect-alerts-to-orchestra`. Each of those skills covers the
source-specific mapping (which Airflow/Dagster/Prefect construct produces which alert); this file
is the Orchestra side only — the part that's identical regardless of source orchestrator.

Source of truth for the enums below: `AlertModel` / `AlertLevelTypes` / `NotificationTypesEnum` in
the pipeline schema (`skills/orchestra/references/orchestra/schemas/pipeline_schema.json`).

## AlertModel — full schema

```yaml
alerts:
  - name: unique-alert-name       # required, unique within scope
    statuses:                     # required, at least one
      - FAILED                    # ANY_COMPLETED | CANCELLED | FAILED | SUCCEEDED | WARNING | SKIPPED
    destinations:                 # required, at least one
      - integration: SLACK        # NotificationTypesEnum — see below
        destination: '#channel'   # required for SLACK and EMAIL
        connection_id: null       # required for PAGER_DUTY, MICROSOFT_TEAMS, WEBHOOK, DATADOG
        parameters: null          # optional — DATADOG priority, WEBHOOK body
    custom_message: null          # optional string, max 200 chars
```

Can appear at the **pipeline root** (fires on overall pipeline run status) or on an individual
**TaskModel** (fires on that task's status only) — see [Placement](#pipeline-level-vs-task-level).

## Status values

| Status | Fires on |
|---|---|
| `FAILED` | Pipeline/task failed |
| `SUCCEEDED` | Pipeline/task succeeded |
| `WARNING` | Finished with warnings (e.g. a quality test threshold hit) |
| `CANCELLED` | Manually cancelled |
| `SKIPPED` | Skipped due to a condition |
| `ANY_COMPLETED` | Any terminal state (success, failure, cancelled, or skipped) |

## Destination types — full reference

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

## Pipeline-level vs task-level

**Pipeline-level** — in the `alerts:` key at the top of the YAML. Fires based on the overall
pipeline run status.

```yaml
version: v1
name: my-pipeline
alerts:           # ← pipeline-level
  - name: ...
pipeline:
  ...
```

**Task-level** — in the `alerts:` key on a specific `TaskModel`. Fires when that individual task
reaches the status.

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

Use task-level when you need different alert routing per task (e.g. page on-call only for the
most critical transformation, not every step).

## Examples

Multiple destinations on one alert:

```yaml
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

Multiple alerts with different statuses and destinations:

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

## Gotchas

- **`connection_id` format** — must be the full Orchestra connection name including the 5-digit
  suffix (e.g. `pagerduty_prod_12345`), not just the connection type.
- **SLACK/EMAIL require `destination`** — omitting it fails schema validation.
- **PAGER_DUTY/MICROSOFT_TEAMS/WEBHOOK/DATADOG require `connection_id`** — `destination` is not
  used for these types.
- **`custom_message` max 200 chars** — longer messages are rejected.
- **Alert names must be unique** within their scope (pipeline-level or per-task) — two
  pipeline-level alerts cannot share a name.

## References

- Orchestra alerts schema: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Orchestra Slack alerts: https://docs.getorchestra.io/docs/alerts/slack
