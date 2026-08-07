---
name: slack-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that uses SlackAPIOperator, SlackWebhookOperator, or SlackAPIPostMessageOperator — or Airflow on_failure_callback / on_success_callback functions that send Slack messages — into an equivalent Orchestra pipeline alert or task. Also covers a plain PythonOperator (or @task) whose function body calls the Slack API directly via slack_sdk/WebClient/chat_postMessage rather than a dedicated Slack operator. Triggers: any mention of migrating or rewriting Slack notification Airflow tasks to Orchestra; Airflow DAG code using SlackAPIOperator, SlackWebhookOperator, SlackAPIPostMessageOperator, callback functions that fire SlackWebhookOperator, or a PythonOperator whose entire job is posting a Slack message via slack_sdk/WebClient."
---

# Slack: Airflow → Orchestra Conversion

## Overview

Airflow Slack notifications come in two forms:

1. **Callback functions** (`on_failure_callback`, `on_success_callback`) — not DAG tasks; fire when a task or DAG changes status.
2. **Explicit DAG tasks** (`SlackWebhookOperator`, `SlackAPIPostMessageOperator`, or a plain `PythonOperator`/`@task` that calls `slack_sdk.WebClient(...).chat_postMessage(...)` directly) — pipeline steps that send a message at a specific point. A task doesn't need to use a dedicated Slack operator to count here — if its whole job is formatting and posting a Slack message, treat it as form 2, not generic Python.

In Orchestra, Slack notifications are handled two ways:
1. **`alerts` block** (pipeline-level or task-level) — fires on status change; no pipeline slot consumed.
2. **`SLACK` pipeline task** (`integration: SLACK`, `integration_job: SEND_SLACK_MESSAGE`) — fires at a specific DAG position, useful when content depends on runtime logic or ordering matters.

---

## Decision Guide

| Airflow pattern | Orchestra equivalent |
|---|---|
| `on_failure_callback` / `on_success_callback` on `default_args` or task | Pipeline-level or task-level **`alerts` YAML block** |
| `SlackWebhookOperator` at the end of a DAG (completion notification) | Pipeline-level **`alerts` YAML block** |
| `SlackWebhookOperator` mid-DAG (status update between tasks) | `SLACK` + `SEND_SLACK_MESSAGE` pipeline task OR task-level `alerts` block |

---

## Option 1: Orchestra Alerts (YAML) — recommended for callbacks & completion notifications

Alerts live in the `alerts` key at the top level of the pipeline YAML. Orchestra fires them when the pipeline reaches any of the listed `statuses`.

### AlertModel schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | ✅ | Unique within the pipeline |
| `statuses` | array | ✅ | `FAILED`, `SUCCEEDED`, `CANCELLED`, `WARNING`, `SKIPPED` |
| `destinations` | array | ✅ | One entry per channel/target |
| `custom_message` | string | ❌ | Appended to the standard Orchestra alert message |

### AlertDestinationModel schema

| Field | Value / notes |
|---|---|
| `integration` | `SLACK`, `EMAIL`, `PAGER_DUTY`, `WEBHOOK`, or `MICROSOFT_TEAMS` |
| `destination` | Channel name (e.g. `#data-alerts`) — **required for Slack** |
| `connection_id` | Orchestra connection name — required for PagerDuty, Teams, Webhook |

### Orchestra YAML — alerts block

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

  - name: on-success-slack
    statuses:
      - SUCCEEDED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

pipeline:
  stage-001:
    tasks:
      task-001:
        # ... your tasks here
```

---

## Option 2: Explicit Slack Pipeline Task — for mid-pipeline messages

**`SLACK` IS a valid `integration` value** — use `integration: SLACK` + `integration_job: SEND_SLACK_MESSAGE` to send a Slack message as an explicit pipeline step.

Required parameter: `channel_name`. At least one of `text`, `blocks`, or `attachments` must be provided.

### Orchestra YAML — explicit Slack task

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

**When to use a task vs an alert:**
- Use an **alert** (`alerts:` block) when the message should fire on pipeline/task *status* (FAILED, SUCCEEDED, etc.) — no task slot needed.
- Use a **SLACK task** when the message must fire at a specific *position* in the DAG and the content depends on runtime logic.

---

## Conversion Steps

1. **Identify Slack usage** — distinguish callbacks (`on_failure_callback` / `on_success_callback`) from explicit DAG tasks.
2. **Callbacks → pipeline-level alerts block** — add an `alerts:` section at the top level of the pipeline YAML. Map `on_failure_callback` → `statuses: [FAILED]`, `on_success_callback` → `statuses: [SUCCEEDED]`.
3. **End-of-DAG `SlackWebhookOperator` → pipeline-level alerts block** — if it fires on overall completion, use a pipeline-level alert.
4. **Mid-DAG `SlackWebhookOperator` → task-level `alerts` block** — add an `alerts:` block directly on the upstream task to fire when that specific task reaches the target status.
5. **Create the Orchestra Slack connection** — in Orchestra Settings → Connections, add a Slack connection (Bot Token `xoxb-...` or Incoming Webhook URL).

---

## Before / After Example

### Airflow DAG (before) — callback pattern

```python
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.hooks.base_hook import BaseHook

SLACK_CONN_ID = 'slack'

def task_fail_slack_alert(context):
    slack_webhook_token = BaseHook.get_connection(SLACK_CONN_ID).password
    channel = BaseHook.get_connection(SLACK_CONN_ID).login
    slack_msg = f":x: Task Failed. *Task*: {context.get('task_instance').task_id}"
    slack_alert = SlackWebhookOperator(
        task_id='slack_fail',
        webhook_token=slack_webhook_token,
        message=slack_msg,
        channel=channel,
        http_conn_id=SLACK_CONN_ID
    )
    return slack_alert.execute(context=context)

def task_succeed_slack_alert(context):
    # ... same pattern for success

default_args = {
    'on_failure_callback': task_fail_slack_alert,
    'on_success_callback': task_succeed_slack_alert,
}
```

### Orchestra YAML (after) — alerts block

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
    custom_message: 'Task failed — check Orchestra logs.'

  - name: slack-on-success
    statuses:
      - SUCCEEDED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

pipeline:
  stage-001:
    tasks:
      # ... tasks unchanged
```

---

## Gotchas

- **`alerts` is a list** — multiple alert entries are supported; each needs a unique `name`.
- **`destination` is required for Slack** — it's the channel name (e.g. `#data-alerts`). Omitting it will fail validation.
- **Use the literal channel name directly when it's known** — if the source resolves to a concrete channel (a literal string, or an `os.getenv("SLACK_CHANNEL", "#data-alerts")` with nothing in the DAG actually varying it), put `#data-alerts` straight into `destination`/`channel_name`. Don't route it through `${{ ENV.* }}` or an `inputs:` entry just because it happened to be read from an env var — only do that when the DAG genuinely needs the channel to vary (e.g. real per-environment or per-branch selection).
- **`connection_id` is not needed for Slack** — Orchestra resolves the Slack workspace from the workspace-level Slack connection; `destination` is sufficient.
- **Bot Token vs Webhook** — Orchestra supports both. Bot Token (`xoxb-...`) allows `chat.postMessage`; Incoming Webhook is simpler but channel-locked.
- **Jinja templates in messages** — Airflow allows `{{ ds }}` in message text. In Orchestra use static strings or `custom_message` for context.
- **`statuses` available**: `FAILED`, `SUCCEEDED`, `CANCELLED`, `WARNING`, `SKIPPED` — map `on_failure_callback` → `FAILED`, `on_success_callback` → `SUCCEEDED`.
- **Pipeline-level alerts fire on overall pipeline status.** For per-task notifications, use task-level `alerts` blocks OR an explicit `SLACK` task downstream.

## References

- Orchestra Slack alerts: https://docs.getorchestra.io/docs/alerts/slack
- Orchestra pipeline YAML schema: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Airflow Slack provider: https://airflow.apache.org/docs/apache-airflow-providers-slack/stable/
