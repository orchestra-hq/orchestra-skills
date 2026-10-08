---
name: setup-incident-slack-summary
description: Set up a scheduled Orchestra pipeline that has an agent summarise the workspace's incidents (filtered by status, severity, name and a lookback window) and post them to a Slack channel as a formatted table. Use whenever someone asks to "Setup Scheduled Incident Slack Summary Pipeline", wants a weekly/daily incident digest, report or roundup in Slack, or asks for open incidents to be posted to a channel on a schedule — even if they don't say "pipeline".
---

# Set up the scheduled incident Slack summary pipeline

You deploy one Orchestra pipeline into the user's workspace from the template in `assets/pipeline.yml`. It has two tasks:

1. **Run Agent** — an Orchestra agent lists incidents with the pipeline's filter inputs, keeps those created inside the lookback window, and sets two outputs: `results` (a one-line plain-text fallback) and `blocks` (Slack Block Kit JSON: a header plus a table with severity emoji, linked incident name, status, created and last updated).
2. **Send Slack message** — posts `blocks` (with `results` as the notification text) to the `slack_channel` input.

The pipeline's inputs (`slack_channel`, `lookback_days`, `statuses`, `severities`, `name_contains`) are what scheduled runs use by default, and anyone can override them on a manual run. So the defaults you set here are the user's standing filter.

## Step 1 — Gather settings

Ask for anything the user hasn't given, in one message, offering the defaults:

| Setting | Default | Notes |
|---|---|---|
| Slack channel | none, must ask | e.g. `#data-incidents` |
| Schedule | Mondays 09:00 Europe/London | Convert to a 6-field AWS EventBridge cron (see below) |
| Lookback window | 7 days | Whole days |
| Statuses | `OPEN,INVESTIGATING` | Valid: `OPEN`, `INVESTIGATING`, `RESOLVED`, `DISMISSED`. "Open" means `OPEN,INVESTIGATING` (anything not yet resolved or dismissed) |
| Severities | `CRITICAL,HIGH,MEDIUM,LOW` | Any subset |
| Name filter | none | Substring match on incident name, e.g. `dbt` |

If the user said something like "just set it up", use the defaults and only ask for the channel.

**Cron:** Orchestra needs 6 fields (`minute hour day-of-month month day-of-week year`), and exactly one of day-of-month / day-of-week must be `?`. Examples: weekly Monday 9am `0 9 ? * MON *`; daily 8am `0 8 * * ? *`; weekdays 9am `0 9 ? * MON-FRI *`. A 5-field cron fails validation. Set `__SCHEDULE_NAME__` to a readable label such as `Mondays at 9am (Europe/London)`.

## Step 2 — Resolve the agent and Slack connection

**Agent ID.** The Run Agent task runs you: this skill ships with a dedicated incident agent, so use your own agent ID from your session context or environment. If the user names a different agent, use theirs instead.

**Slack connection.** Call `list_integration_connections` with `integration=SLACK`, keeping those with `authStatus=SUCCEEDED`. Use the `connectionId` (e.g. `default_00000`), not the display name. One connection: use it. Several: prefer `isDefault`, or ask. None: stop and tell the user to connect Slack in Orchestra first.

## Step 3 — Fill the template, validate, deploy

This skill only ever creates a new pipeline, named `Slack Incidents Digest`. Never update or modify an existing pipeline, even one that looks similar: other digests in the workspace belong to someone else and repointing them silently breaks their alerts.

Read `assets/pipeline.yml` and replace every `__PLACEHOLDER__`:

`__AGENT_ID__`, `__SLACK_CONNECTION_ID__`, `__SLACK_CHANNEL__` (used twice: the input default and the failure alert), `__LOOKBACK_DAYS__`, `__STATUSES__`, `__SEVERITIES__`, `__SCHEDULE_NAME__`, `__CRON__`, `__TIMEZONE__`.

If the user gave a name filter, add `default: <filter>` under the `name_contains` input (keep `optional: true`). With no filter, leave it with no default.

Leave every `${{ ... }}` expression untouched. Orchestra resolves those at run time, and the agent prompt depends on them.

Leave the agent prompt alone too unless the user asks for a format change. Each line of it exists because something broke without it:
- "Never leave a cell text empty": Slack rejects the whole message (`invalid_blocks`) if any table cell is empty.
- "Set two string outputs": the Slack task reads `OUTPUTS['results']` and `OUTPUTS['blocks']` by exactly those names.
- The emoji mapping keeps CRITICAL (🚨) visually distinct from HIGH (🔴).

Then:
1. Convert the YAML to the JSON document the tools expect and call `validate_pipeline`. Fix only what it reports; don't regenerate.
2. Call `create_pipeline` with `published: true`.

Gotchas:
- Never give `name_contains` an empty-string default. That makes the save fail with "Input 'name_contains' is required but is not present in schedule inputs".
- Wrap the cron and channel in quotes. `?`, `*` and a leading `#` are special characters in YAML.

## Step 4 — Hand over

Before offering a test run, remind the user that the Orchestra Slack app must be in the channel (`/invite @orchestra`), or the Slack task fails.

Offer a test run (`start_pipeline`). It posts a real message to their channel, so ask first. If they agree, poll `get_pipeline_run_status` (the agent task usually takes 1–2 minutes). If it fails, `list_task_runs_for_pipeline_run` shows each task's `externalMessage`:
- `invalid_blocks`: the agent produced bad Block Kit JSON. Check the `blocks` parameter for empty cells or a non-array value.
- `not_in_channel` / `channel_not_found`: the app isn't invited, or the channel name is wrong.

Finish with the pipeline link `https://app.getorchestra.io/pipelines/<id>`, the schedule in plain words, and the default filters. Mention that they can change filters per run, or edit the input defaults in the pipeline to change what the schedule uses.
