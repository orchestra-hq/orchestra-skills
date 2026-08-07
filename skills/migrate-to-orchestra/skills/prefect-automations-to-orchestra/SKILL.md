---
name: prefect-automations-to-orchestra
description: "Use this skill when a Prefect project uses Automations to trigger flow runs based on external events — storage events (S3/GCS file arrivals), database polling, scheduled automations, or webhook-triggered deployments. Triggers: any Prefect Automation watching external state, any flow.serve() with event-based triggers, any Prefect event webhook trigger, or any polling pattern that decides whether to start a flow run."
---

## Overview

Prefect Automations react to external events (file arrivals, database state, webhook calls, or schedules) and trigger flow runs. In Orchestra, the equivalent is the `sensors:` block — a set of named checks that poll external systems on a cron schedule and gate the pipeline run. Automations that fire on flow state changes (failed/succeeded) are **not** sensors; those become `alerts:` (see `prefect-alerts-to-orchestra`).

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| Automation: S3 object created event → trigger | `sensors.checks` with `sensor_type: AWS_S3_FILE` | `integration: AWS_S3` |
| Automation: scheduled (cron) | `schedule:` at pipeline root | see `prefect-flow-structure-to-orchestra` |
| Automation: webhook trigger | `webhook: {enabled: true}` at pipeline root | |
| `@flow` polling a DB table (Snowflake) | `sensors.checks` with `sensor_type: SNOWFLAKE_QUERY` | |
| `@flow` polling SQL Server | `sensors.checks` with `sensor_type: SQL_SERVER_QUERY` | |
| Automation: upstream flow completion → trigger | `trigger_events:` at pipeline root | see `prefect-cross-flow-to-orchestra` |
| Automation: flow failed → notify | `alerts:` block | NOT a sensor |
| `SensorModel.timeout_mins` | max 1440 (24 h) | Prefect has no equivalent cap |
| `map_outputs` | pipes sensor query result to pipeline `inputs:` | declare matching key in pipeline `inputs:` |

Valid `sensor_type` values (SensorChecksEnum — exactly 9):
`AWS_S3_FILE`, `ADLS_FILE`, `SFTP_FILE`, `SNOWFLAKE_QUERY`, `SQL_SERVER_QUERY`, `DATABRICKS_QUERY`, `FABRIC_SYNAPSE_QUERY`, `ORCHESTRA_PIPELINE_STATUS`, `ORCHESTRA_WEBHOOK_EVENT`

> **POSTGRES_QUERY and GCP_BIG_QUERY_QUERY are NOT valid sensor types.**

## Orchestra YAML Structure

```yaml
version: v1
name: pipeline-name

sensors:
  <sensor-key>:
    name: <human-readable name>
    cron: '<cron expression>'
    timezone: UTC
    timeout_mins: 60          # max 1440
    frequency_secs: 60        # how often checks are polled within the window
    checks:
      <check-key>:
        integration: <INTEGRATION>
        sensor_type: <SensorChecksEnum value>
        connection: <connection_name>
        parameters:
          <integration-specific params>
        map_outputs:           # optional — pipe result to pipeline inputs
          <input_key>: result

pipeline:
  <stages and tasks>
```

### Webhook trigger

```yaml
version: v1
name: webhook-triggered-pipeline
webhook:
  enabled: true

pipeline:
  {}
```

## Conversion Steps

- [ ] Identify every Prefect Automation and classify: external event trigger vs. state-change notification
- [ ] For state-change notifications (on_failure, on_completion) → use `prefect-alerts-to-orchestra` instead
- [ ] For S3 triggers: map bucket + prefix to `AWS_S3_FILE` check; set `connection` to Orchestra AWS connection name
- [ ] For Snowflake/DB polling tasks: extract the SQL query; invert any assertion logic; set `error_threshold_expression` if using `SNOWFLAKE_RUN_TEST` (testing skill); for sensors just use `SNOWFLAKE_QUERY`
- [ ] For webhook triggers: add `webhook: {enabled: true}` at pipeline root; remove trigger logic from flow body
- [ ] For scheduled Automations: move cron to `schedule:` at pipeline root
- [ ] For upstream-flow triggers: use `trigger_events:` (see `prefect-cross-flow-to-orchestra`)
- [ ] Set `timeout_mins` — never exceed 1440
- [ ] If sensor result feeds downstream logic, declare `map_outputs` and a matching `inputs:` key at pipeline root
- [ ] Verify `sensor_type` is one of the 9 valid enum values

## Before / After Example

### Prefect (before)

```python
# Automation: "When S3 object is created in s3://my-bucket/data/daily/ → run nightly-elt/prod"
# (Configured in Prefect UI — no Python code needed for the trigger itself)

# Separately, a polling flow:
@task
def wait_for_snowflake_data():
    connector = SnowflakeConnector.load("sf-prod")
    with connector.get_connection() as conn:
        while True:
            count = conn.cursor().execute(
                "SELECT COUNT(*) FROM orders WHERE created_date = CURRENT_DATE"
            ).fetchone()[0]
            if count > 0:
                return count
            time.sleep(300)

@flow
def nightly_elt():
    order_count = wait_for_snowflake_data()
    # ... rest of pipeline
```

### Orchestra YAML (after)

```yaml
version: v1
name: nightly-elt

sensors:
  wait-for-s3-file:
    name: Wait for daily S3 file
    cron: '0 6 * * ? *'
    timezone: UTC
    timeout_mins: 60
    frequency_secs: 60
    checks:
      s3-file-check:
        integration: AWS_S3
        sensor_type: AWS_S3_FILE
        connection: aws_default_12345
        parameters:
          bucket_name: my-bucket
          prefix: data/daily/

  wait-for-snowflake-data:
    name: Wait for daily order records
    cron: '0 4 * * ? *'
    timezone: UTC
    timeout_mins: 120
    frequency_secs: 300
    checks:
      row-check:
        integration: SNOWFLAKE
        sensor_type: SNOWFLAKE_QUERY
        connection: snowflake_prod_12345
        parameters:
          query: 'SELECT COUNT(*) FROM orders WHERE created_date = CURRENT_DATE'
        map_outputs:
          order_count: result

inputs:
  order_count:
    type: integer
    default: 0

pipeline:
  stage-main:
    tasks:
      {}
```

## Gotchas

- `SensorChecksEnum` has exactly 9 values — `POSTGRES_QUERY` and `GCP_BIG_QUERY_QUERY` are **NOT** valid; use `SNOWFLAKE_QUERY` or `SQL_SERVER_QUERY` instead
- Prefect Automations that fire on flow state changes (failed/succeeded) are **NOT** sensors — they map to `alerts:` → see `prefect-alerts-to-orchestra`
- `timeout_mins` max is 1440 (24 hours); Prefect has no enforced cap
- `map_outputs` pipes sensor query results to pipeline inputs — you must declare matching keys in the pipeline `inputs:` block
- Webhook trigger: set `webhook: {enabled: true}` at pipeline root; no sensor block needed
- Multiple checks under one sensor use AND logic — all must pass before the pipeline runs
- `frequency_secs` controls polling interval within the sensor window; `cron` controls when the window opens

## References

- https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- https://docs.prefect.io/v3/automate/events/automations-triggers

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
