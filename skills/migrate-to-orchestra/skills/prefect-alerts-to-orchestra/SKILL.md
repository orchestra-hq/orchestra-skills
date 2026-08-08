---
name: prefect-alerts-to-orchestra
description: "Use this skill when a Prefect project sends notifications: @flow(on_failure=...) or @flow(on_completion=...) hooks, Prefect Automation notification actions (Slack, email, Teams, PagerDuty), SlackWebhook block notifications, or MicrosoftTeamsWebhook block notifications. Covers all six Orchestra alert destination types: SLACK, EMAIL, PAGER_DUTY, MICROSOFT_TEAMS, WEBHOOK, and DATADOG. Read alongside prefect-automations-to-orchestra for complete notification coverage."
---

## Overview

Prefect notifications live in three places: `@flow(on_failure=...)` / `@flow(on_completion=...)` hooks, `@task(on_failure=...)` hooks, and Prefect Automation notification actions. All three map to Orchestra's `alerts:` block, placed at pipeline level (for flow-level hooks) or task level (for task-level hooks).

For the Orchestra-side syntax (full `AlertModel` schema, all six destination types, status enum, pipeline-level vs task-level placement, gotchas) see the shared reference: [`../../references/alerts.md`](../../references/alerts.md). This skill covers only the Prefect-specific mapping.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `@flow(on_failure=[slack_hook])` | `statuses: [FAILED]` + SLACK destination | pipeline-level `alerts:` |
| `@flow(on_completion=[slack_hook])` | `statuses: [SUCCEEDED]` + SLACK | pipeline-level |
| `@flow(on_crashed=[hook])` | `statuses: [FAILED]` | no CRASHED status in Orchestra |
| `@flow(on_cancellation=[hook])` | `statuses: [CANCELLED]` | |
| `@task(on_failure=[hook])` | task-level `alerts:` on that specific task | |
| Prefect Automation → Slack notification | `statuses: [FAILED/SUCCEEDED]` + SLACK | |
| Prefect Automation → email notification | `statuses: [...]` + EMAIL | |
| Prefect Automation → PagerDuty action | `statuses: [...]` + PAGER_DUTY | requires `connection_id` |
| Prefect Automation → Teams notification | `statuses: [...]` + MICROSOFT_TEAMS | requires `connection_id` |
| `SlackWebhook.load("x").notify(...)` | SLACK destination with `destination` field | channel from `notify(channel=...)` |
| `MicrosoftTeamsWebhook.load("x").notify(...)` | MICROSOFT_TEAMS with `connection_id` | |

## Conversion Steps

- [ ] Find all `@flow(on_failure=...)`, `@flow(on_completion=...)`, `@flow(on_crashed=...)`, `@flow(on_cancellation=...)` hooks
- [ ] Find all `@task(on_failure=...)` hooks
- [ ] Find all Prefect Automation notification actions (Slack, email, PagerDuty, Teams)
- [ ] Find all `SlackWebhook.load(...).notify(...)` and `MicrosoftTeamsWebhook.load(...).notify(...)` calls
- [ ] For each flow-level hook → add entry to pipeline-level `alerts:` block
- [ ] For each task-level hook → add `alerts:` block inside that task's YAML
- [ ] Map `on_crashed` → `FAILED` status (no CRASHED in Orchestra); add comment noting this
- [ ] Map `on_cancellation` → `CANCELLED` status
- [ ] For SLACK: extract channel from `notify(channel=...)` or Prefect block config → `destination`
- [ ] For EMAIL: extract address → `destination`
- [ ] For PAGER_DUTY / MICROSOFT_TEAMS / WEBHOOK / DATADOG: find or create Orchestra connection → `connection_id`
- [ ] Ensure `connection_id` values include the 5-digit Orchestra suffix
- [ ] Ensure all alert names are unique within their scope
- [ ] Keep `custom_message` under ~200 chars

## Before / After Example

### Prefect (before)

```python
from prefect_slack import SlackWebhook
from prefect.blocks.notifications import MicrosoftTeamsWebhook

def post_failure_to_slack(flow, flow_run, state):
    SlackWebhook.load("data-alerts").notify(
        body=f"Flow {flow.name} failed.",
        channel="#incidents"
    )

def send_pagerduty_on_failure(flow, flow_run, state):
    # calls PagerDuty API directly
    requests.post(PAGERDUTY_URL, json={"routing_key": PD_KEY, "event_action": "trigger"})

def notify_teams_on_success(flow, flow_run, state):
    MicrosoftTeamsWebhook.load("teams-data-channel").notify(body="Pipeline succeeded!")

@flow(
    on_failure=[post_failure_to_slack, send_pagerduty_on_failure],
    on_completion=[notify_teams_on_success],
)
def critical_pipeline():
    ...

@task(on_failure=[post_failure_to_slack])
def critical_task():
    ...
```

### Orchestra YAML (after)

```yaml
version: v1
name: critical-pipeline

alerts:
  - name: slack-on-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#incidents'
    custom_message: 'Critical pipeline failed — immediate attention required.'

  - name: pagerduty-on-failure
    statuses: [FAILED]
    destinations:
      - integration: PAGER_DUTY
        connection_id: pagerduty_prod_12345
    custom_message: 'Pipeline down — SLA at risk.'

  - name: teams-on-success
    statuses: [SUCCEEDED]
    destinations:
      - integration: MICROSOFT_TEAMS
        connection_id: teams_data_channel_67890
    custom_message: 'Pipeline succeeded!'

pipeline:
  stage-main:
    tasks:
      critical-task:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_QUERY
        connection: snowflake_prod_12345
        parameters:
          query: 'SELECT 1'
        depends_on: []
        alerts:
          - name: task-slack-on-failure
            statuses: [FAILED]
            destinations:
              - integration: SLACK
                destination: '#incidents'
```

## Gotchas (Prefect-specific)

- `on_crashed` maps to `FAILED` — Orchestra has no CRASHED status; add a comment so reviewers know
- `on_cancellation` maps to `CANCELLED`
- Task-level `on_failure` → task-level `alerts:` block, not pipeline-level
- Multiple hooks on one decorator become multiple entries in the `alerts:` list
- Prefect Automations that trigger flow runs (not just notify) are NOT alerts → use sensors or trigger_events

See the shared reference for Orchestra-side gotchas (`connection_id` format, `custom_message` length, alert name uniqueness, etc.).

## References

- Shared Orchestra alerts syntax: [`../../references/alerts.md`](../../references/alerts.md)
- https://prefecthq.github.io/prefect-slack/

## Adding Alerts

For sensor/trigger patterns (not just notifications), see `prefect-automations-to-orchestra`.
