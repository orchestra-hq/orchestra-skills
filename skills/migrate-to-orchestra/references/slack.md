# Orchestra Slack pipeline task — shared reference

Canonical Orchestra-side syntax for sending a Slack message as an explicit pipeline step (`integration:
SLACK`, `integration_job: SEND_SLACK_MESSAGE`), shared by `slack-airflow-to-orchestra`,
`slack-dagster-to-orchestra`, and `slack-prefect-to-orchestra`. Each of those skills covers the
source-specific mapping (which Airflow/Dagster/Prefect construct becomes a mid-pipeline Slack task vs.
a status-driven notification, and how to recognize one in source); this file is the Orchestra side
only — the part of the *explicit task* that's identical regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:**
- The generic `alerts:` block itself (statuses, destinations, `custom_message`) — that's Orchestra's
  status-driven notification mechanism, not a pipeline task, and it's already the shared reference for
  `airflow-alerts-to-orchestra` / `dagster-alerts-to-orchestra` / `prefect-alerts-to-orchestra`. See
  [`alerts.md`](alerts.md) and the sibling `*-alerts-to-orchestra` skill for that content — it is not
  duplicated here even though each slack skill also shows an `alerts:` example for comparison.
- The per-source "how do I recognize a Slack notification in this code" test — this is always
  source-specific (a decorator, an operator class, a raw `slack_sdk` call, a hook) and never shared.
  See each skill's Decision Guide / Overview section.
- Any sentence naming another orchestrator or a sibling skill.
- Conversion checklists and Gotchas sections — kept per-skill since their content and phrasing genuinely
  differ per source orchestrator, not because the underlying Orchestra facts differ.

## Explicit Slack pipeline task

`SLACK` is a valid pipeline task `integration` value, and `SEND_SLACK_MESSAGE` is a valid
`integration_job` — use them to send a Slack message as an explicit step in the pipeline, positioned via
`depends_on` like any other task, rather than firing on pipeline/task status via `alerts:`.

| Field | Required | Notes |
|---|---|---|
| `parameters.channel_name` | ✅ | Slack channel name (e.g. `'#data-team'`) |
| `parameters.text` | at least one of `text` / `blocks` / `attachments` | Plain message text |
| `parameters.blocks` | at least one of `text` / `blocks` / `attachments` | Slack Block Kit payload |
| `parameters.attachments` | at least one of `text` / `blocks` / `attachments` | Legacy Slack attachments payload |
| `connection` | ✅ | Orchestra Slack connection name, e.g. `slack_prod_12345` |

### Example

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

## References

- Orchestra Slack alerts: https://docs.getorchestra.io/docs/alerts/slack
- Orchestra Slack integration: https://docs.getorchestra.io/docs/integrations/slack
- Orchestra pipeline YAML schema: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
