---
name: slack-dagster-to-orchestra
description: "Use this skill when the user wants to convert Dagster Slack notifications — SlackResource, make_slack_on_run_failure_sensor, make_slack_on_freshness_policy_status_change_sensor, or op success/failure hooks that post to Slack — into an equivalent Orchestra pipeline alert or task. Triggers: any mention of migrating or rewriting Dagster Slack notifications to Orchestra; Dagster code importing from dagster_slack, or @success_hook/@failure_hook functions that send Slack messages."
---

# Slack: Dagster -> Orchestra Conversion

## Overview

Dagster Slack notifications come in two forms:

1. **Run-status sensors / hooks** (`make_slack_on_run_failure_sensor`, `@failure_hook`, `@success_hook`) — fire when a run or op changes status; not pipeline steps.
2. **Explicit messages inside an op** (`context.resources.slack.get_client().chat_postMessage(...)`) — a message sent at a specific point in the run.

In Orchestra these map to:
1. **`alerts` block** (pipeline-level or task-level) — fires on status change; no pipeline slot consumed.
2. **`SLACK` pipeline task** (`integration: SLACK`, `integration_job: SEND_SLACK_MESSAGE`) — fires at a specific position, when content depends on runtime logic or ordering matters.

---

## Decision Guide

| Dagster pattern | Orchestra equivalent |
|---|---|
| `make_slack_on_run_failure_sensor` | Pipeline-level **`alerts`** block (`statuses: [FAILED]`) |
| `@failure_hook` / `@success_hook` on whole job | Pipeline-level `alerts` block |
| `@failure_hook` / `@success_hook` on a single op | Task-level `alerts` block on that task |
| `SlackResource.chat_postMessage` inside an op (mid-run) | `SLACK` + `SEND_SLACK_MESSAGE` task |
| Slack message at end of job | Pipeline-level `alerts` block (`statuses: [SUCCEEDED]`) |

---

## Option 1: Orchestra Alerts (YAML) — recommended for sensors & hooks

### AlertModel schema

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Unique within scope |
| `statuses` | yes | `FAILED`, `SUCCEEDED`, `CANCELLED`, `WARNING`, `SKIPPED` |
| `destinations` | yes | One entry per channel/target |
| `custom_message` | no | Appended to the standard Orchestra alert message |

### AlertDestinationModel

| Field | Value / notes |
|---|---|
| `integration` | `SLACK`, `EMAIL`, `PAGER_DUTY`, `WEBHOOK`, `MICROSOFT_TEAMS` |
| `destination` | Channel name (e.g. `#data-alerts`) — **required for Slack** |
| `connection_id` | Required for PagerDuty, Teams, Webhook |

```yaml
version: v1
name: my-pipeline

alerts:
  - name: on-failure-slack
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Check the logs and rerun from the failed task.'

pipeline:
  stage-001:
    tasks:
      task-001:
        # ... your tasks here
```

---

## Option 2: Explicit Slack Pipeline Task — for mid-run messages

**`SLACK` IS a valid `integration`** — use `integration: SLACK` + `integration_job: SEND_SLACK_MESSAGE`. Required parameter: `channel_name`; at least one of `text`, `blocks`, or `attachments`.

```yaml
version: v1
name: my-pipeline
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        name: dbt_run
        connection: my_dbt_conn_12345
        parameters:
          commands: 'dbt build;'
          python_version: '3.12'
        depends_on: []
        condition: null
        tags: []

      task-002:
        integration: SLACK
        integration_job: SEND_SLACK_MESSAGE
        name: notify_mid_pipeline
        connection: slack_prod_12345
        parameters:
          channel_name: '#data-team'
          text: 'dbt build complete — starting downstream loads.'
        depends_on:
          - task-001
        condition: null
        tags: []
```

---

## Conversion Steps

1. **Identify Slack usage** — distinguish run-status sensors/hooks from explicit in-op messages.
2. **Sensors / job-level hooks -> pipeline-level alerts** — map `make_slack_on_run_failure_sensor` and job-level `@failure_hook` to `statuses: [FAILED]`; success hooks to `statuses: [SUCCEEDED]`.
3. **Op-level hooks -> task-level alerts** — attach an `alerts:` block to the specific task.
4. **In-op messages -> SLACK task** — convert `chat_postMessage` calls to `SEND_SLACK_MESSAGE` tasks positioned via `depends_on`.
5. **Create the Orchestra Slack connection** — Settings -> Connections -> Slack (Bot Token `xoxb-...` or Incoming Webhook).

## Before / After Example

### Dagster (before)

```python
from dagster import Definitions, EnvVar
from dagster_slack import SlackResource, make_slack_on_run_failure_sensor

slack_on_failure = make_slack_on_run_failure_sensor(
    channel="#data-alerts",
    slack_token=EnvVar("SLACK_BOT_TOKEN"),
    text_fn=lambda ctx: f"Run failed: {ctx.dagster_run.job_name}",
)

defs = Definitions(
    sensors=[slack_on_failure],
    resources={"slack": SlackResource(token=EnvVar("SLACK_BOT_TOKEN"))},
)
```

### Orchestra YAML (after)

```yaml
version: v1
name: my-pipeline

alerts:
  - name: slack-on-failure
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Run failed — check Orchestra logs.'

pipeline:
  stage-001:
    tasks:
      # ... tasks unchanged
```

## Gotchas

- **`make_slack_on_run_failure_sensor` -> pipeline-level alert** — map to `statuses: [FAILED]`, not a task.
- **`@failure_hook`/`@success_hook` scope** — op-level -> task-level alert; job-level -> pipeline-level alert.
- **`SlackResource` inside an op -> SLACK task** — explicit mid-run messages become `SEND_SLACK_MESSAGE`.
- **`destination` is required for Slack** — the channel name; omitting it fails validation.
- **Use the literal channel name directly when it's known** — if the source resolves to a concrete channel (a literal string, or an `EnvVar`/`os.getenv` with nothing actually varying it), put the real channel straight into `destination`/`channel_name`. Don't route it through `${{ ENV.* }}` just because it happened to be read from an env var — only do that when the code genuinely needs the channel to vary (e.g. real per-environment selection).
- **`connection_id` not needed for Slack** — resolved from the workspace Slack connection.
- **Bot Token vs Webhook** — Orchestra supports both.
- **`text_fn` / blocks** — run-context interpolation has no direct equivalent; use `custom_message` or a SLACK task with `${{ }}` expressions.
- **Statuses** — failure sensors -> `FAILED`, success hooks -> `SUCCEEDED`.

## References

- Orchestra Slack alerts: https://docs.getorchestra.io/docs/alerts/slack
- Orchestra pipeline schema: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Dagster Slack: https://docs.dagster.io/integrations/libraries/slack
- dagster-slack API: https://docs.dagster.io/api/python-api/libraries/dagster-slack
