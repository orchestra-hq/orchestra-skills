---
name: slack-prefect-to-orchestra
description: "Use this skill when the user wants to convert Prefect Slack notifications into an equivalent Orchestra pipeline alert or task. This covers both hook-based notifications — SlackWebhook block, @flow on_failure/on_completion hooks, Prefect Automation Slack notifications — AND explicit mid-flow Slack messages, including a plain @task that calls the Slack Web API directly (slack_sdk, WebClient, chat_postMessage) rather than going through prefect_slack. Triggers: any mention of migrating or rewriting Prefect Slack notifications to Orchestra; any Prefect flow code importing from prefect_slack; on_failure= or on_completion= flow arguments posting to Slack; send_incoming_webhook_message(); or any @task whose body's entire purpose is posting a message to Slack (via slack_sdk.WebClient(...).chat_postMessage(...) or similar) and is called explicitly as a step in the @flow body, not just from a callback."
---

## Overview

Prefect Slack notifications come in two forms:

1. **Hooks / Automations** (`on_failure=`, `on_completion=`, Prefect Automation Slack actions) — fire when the flow changes status; not pipeline steps.
2. **Explicit messages inside a task** (`SlackWebhook.notify()`, `send_incoming_webhook_message()`, or a plain `@task` calling `slack_sdk.WebClient(...).chat_postMessage(...)` directly) — a message sent at a specific point in the flow, called from the `@flow` body like any other task.

Watch for form 2 even when the task doesn't import `prefect_slack` at all — a task that just wraps `slack_sdk.WebClient` and is invoked as an explicit step (e.g. `notify_slack(status)` after an upstream task completes) is still a Slack notification, not generic Python. Converting it as a plain `PYTHON_EXECUTE_SCRIPT` task loses the Orchestra Slack connection wiring and the pipeline visibility of `SLACK` tasks.

In Orchestra these map to:
1. **`alerts:` block** (pipeline-level) — fires on status change; no pipeline slot consumed. Use for hooks/Automations.
2. **`SLACK` pipeline task** (`integration: SLACK`, `integration_job: SEND_SLACK_MESSAGE`) — fires at a specific position, when content depends on runtime logic or ordering matters. Use for explicit mid-flow messages, including raw `slack_sdk` calls.

**`SLACK` IS a valid `integration` value and `SEND_SLACK_MESSAGE` IS a valid `integration_job`** — Slack notifications should use one of these two native paths, not a generic `HTTP_REQUEST` task. Reach for `HTTP_REQUEST` only if the message is genuinely going to some other non-Slack webhook.

## Parameter Mapping

| Prefect pattern | Orchestra equivalent |
|---|---|
| `@flow(on_failure=[slack_fn])` | `alerts:` block, `statuses: [FAILED]`, `integration: SLACK` |
| `@flow(on_completion=[slack_fn])` | `alerts:` block, `statuses: [SUCCEEDED]` |
| Prefect Automation → Slack on failure | `alerts:` block, `statuses: [FAILED]` |
| `send_incoming_webhook_message()` mid-flow | `SLACK` + `SEND_SLACK_MESSAGE` pipeline task |
| `SlackWebhook.notify()` at flow end | `alerts:` block, `statuses: [SUCCEEDED]` (or a `SLACK` task if it needs a runtime-computed message) |
| Plain `@task` calling `slack_sdk.WebClient(...).chat_postMessage(...)` mid-flow | `SLACK` + `SEND_SLACK_MESSAGE` pipeline task, wired via `depends_on` |
| `channel=`/`channel_name=` argument | `destinations[].destination:` (alerts) or `parameters.channel_name` (task) | e.g. `'#data-alerts'` |
| Message text / f-string body | `custom_message:` (alerts, max 200 chars) or `parameters.text` (task) |
| `SlackWebhook.load("...")` webhook URL, or `SLACK_BOT_TOKEN` env var | Orchestra Slack connection (Connectors → Slack → Connect) | Never put tokens/URLs in YAML |

## Orchestra YAML Structure

**Option 1 — Alert-based (on_failure / on_completion / Automations):**

```yaml
alerts:
  - name: slack-on-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Pipeline failed.'
```

**Option 2 — Explicit Slack pipeline task (mid-flow message, incl. raw slack_sdk calls):**

Required parameter: `channel_name`; at least one of `text`, `blocks`, or `attachments`.

```yaml
integration: SLACK
integration_job: SEND_SLACK_MESSAGE
name: notify_slack
connection: slack_prod_12345
parameters:
  channel_name: '#alert-demos'
  text: ':bar_chart: Power BI dashboard refreshed — status: Completed.'
depends_on: [task-001]
condition: null
tags: []
```

**Full pipeline example with both patterns:**

```yaml
version: v1
name: my-flow
alerts:
  - name: slack-on-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#incidents'
    custom_message: 'Pipeline failed — check Orchestra logs.'
pipeline:
  stage-001:
    tasks:
      task-001:
        # ... main work task
      task-002:
        integration: SLACK
        integration_job: SEND_SLACK_MESSAGE
        name: notify_slack
        connection: slack_prod_12345
        parameters:
          channel_name: '#data-team'
          text: 'Main task complete.'
        depends_on: [task-001]
        condition: null
        tags: []
```

## Conversion Steps

- [ ] Identify the Prefect Slack pattern (on_failure hook, on_completion hook, Automation, mid-flow `send_incoming_webhook_message()`/`SlackWebhook.notify()`, or a plain `@task` wrapping `slack_sdk.WebClient`)
- [ ] For **on_failure / on_completion hooks** and **Automations**: add an `alerts:` block at pipeline root level with the appropriate `statuses`
- [ ] For **any explicit mid-flow Slack message** — including a `@task` that calls `slack_sdk.WebClient(...).chat_postMessage(...)` directly and is invoked as a step in the `@flow` body — add a `SLACK` + `SEND_SLACK_MESSAGE` task at the correct position, wired with `depends_on:`
- [ ] Set the channel: `destinations[].destination:` (alerts) or `parameters.channel_name` (task) to the Slack channel name (e.g. `'#incidents'`)
- [ ] Move the Slack bot token / webhook URL to the Orchestra Slack connection (Connectors → Slack → Connect) — resolved via `connection:`, never inlined
- [ ] Write `custom_message:` (alerts, ≤200 chars) or `parameters.text` (task) from the original message body/f-string
- [ ] Double check no Slack notification task was left converted as a plain `PYTHON_EXECUTE_SCRIPT` task — if a task's only job is posting to Slack, it belongs on `integration: SLACK`, not `PYTHON`

## Before / After Examples

### Example 1 — hook-based

**Prefect (before):**

```python
from prefect import flow
from prefect_slack import SlackWebhook

def post_failure_to_slack(flow, flow_run, state):
    SlackWebhook.load("data-alerts").notify(
        body=f"Flow {flow.name} failed.",
        channel="#incidents"
    )

@flow(on_failure=[post_failure_to_slack])
def my_flow():
    ...
```

**Orchestra YAML (after):**

```yaml
version: v1
name: my-flow
alerts:
  - name: slack-on-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#incidents'
    custom_message: 'Pipeline failed — check Orchestra logs.'
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: main_task
        connection: my_python_conn_12345
        parameters:
          command: 'python scripts/main.py'
          python_version: '3.12'
          package_manager: PIP
        depends_on: []
        condition: null
        tags: []
```

### Example 2 — explicit task using raw slack_sdk (not prefect_slack)

**Prefect (before):**

```python
from prefect import flow, task
from slack_sdk import WebClient

@task
def refresh_dataset() -> str:
    ...
    return "Completed"

@task
def notify_slack(status: str) -> None:
    WebClient(token=os.environ["SLACK_BOT_TOKEN"]).chat_postMessage(
        channel="#alert-demos",
        text=f":bar_chart: Dashboard refreshed — status: {status}.",
    )

@flow
def my_flow():
    status = refresh_dataset()
    notify_slack(status)
```

This task never imports `prefect_slack` and isn't a hook — it's called as a normal step in the flow body. It still belongs on `integration: SLACK`, not `PYTHON`, because its entire purpose is sending a Slack message.

**Orchestra YAML (after):**

```yaml
version: v1
name: my-flow
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: refresh_dataset
        connection: null
        parameters:
          source: INLINE
          code: |
            # refresh_dataset body
          python_version: '3.12'
        depends_on: []
        condition: null
        tags: []
      task-002:
        integration: SLACK
        integration_job: SEND_SLACK_MESSAGE
        name: notify_slack
        connection: slack_prod_12345
        parameters:
          channel_name: '#alert-demos'
          text: ":bar_chart: Dashboard refreshed — status: ${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-001'].OUTPUTS['status'] }}."
        depends_on: [task-001]
        condition: null
        tags: []
```

Note the runtime status value flows through `${{ ORCHESTRA.PIPELINE_RUN_TASKS['task_id'].OUTPUTS['key'] }}` from the upstream task's `set_output()` call (see `prefect-data-passing-to-orchestra`) rather than through Python string formatting — the message content now lives on the `SLACK` task's `text` parameter, not in code.

## Gotchas

- **`SLACK` IS a valid pipeline task `integration` value, and `SEND_SLACK_MESSAGE` IS a valid `integration_job`** — don't route Slack messages through `HTTP_REQUEST` just because the source code called a raw HTTP/Web API client; if the call's purpose is posting to Slack, use the native `SLACK` task.
- **A task doesn't need to import `prefect_slack` to be a Slack notification** — `slack_sdk.WebClient`, `requests.post` to a `hooks.slack.com` or `slack.com/api/chat.postMessage` URL, or any function whose sole job is formatting and sending a Slack message all count. Don't let the absence of `prefect_slack` make this look like generic Python.
- The `SlackWebhook.load()` webhook URL, or a `SLACK_BOT_TOKEN`/`SLACK_WEBHOOK_URL` env var, belongs on the **Orchestra Slack connection** (Connectors → Slack → Connect), not in any YAML field or task code.
- `destinations[].destination` (alerts) / `parameters.channel_name` (task) is **required** — omitting it causes a silent failure or validation error.
- **Use the literal channel name directly when it's known** — if the source resolves to a concrete channel (a literal string, or an `os.getenv`/block value with nothing actually varying it), put the real channel straight into `destination`/`channel_name`. Don't route it through `${{ ENV.* }}` just because it happened to be read from an env var — only do that when the flow genuinely needs the channel to vary (e.g. real per-environment selection).
- `custom_message` (alerts) has a **200-character limit** — truncate or simplify Prefect message templates. `parameters.text` (task) has no such limit.
- Reach for `HTTP_REQUEST` only when the destination genuinely isn't Slack (some other generic webhook) — not as a default fallback for Slack messages.

## References

- https://docs.getorchestra.io/docs/integrations/slack
- https://prefecthq.github.io/prefect-slack/
- https://api.slack.com/methods/chat.postMessage

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
