---
name: dagster-sensors-to-orchestra
description: "Use this skill when a Dagster project contains sensors that watch external state and trigger runs: @sensor, @asset_sensor, @multi_asset_sensor, build_sensor_for_freshness_checks, or sensors polling S3/files/tables. Triggers: any @sensor that yields RunRequest based on external state (a file arriving, a row appearing), any @asset_sensor watching upstream materializations, any freshness/observation sensor. Note: @run_status_sensor / @run_failure_sensor are handled by dagster-cross-job-to-orchestra and dagster-alerts-to-orchestra."
---

# Dagster Sensors -> Orchestra Sensors Block

## Overview

Dagster sensors are functions evaluated on a tick interval that inspect external state and `yield RunRequest(...)` to launch a run when a condition is met (or `SkipReason` otherwise). In Orchestra, sensors are **pipeline triggers** — they live in the `sensors:` block at the pipeline root (not inside `pipeline:`). When all of a sensor's checks pass, the pipeline run is triggered automatically.

Key difference: Dagster sensors run arbitrary Python every tick. Orchestra sensors use a **cron window + polling interval** model with **declarative checks** drawn from `SensorChecksEnum`.

---

## SensorModel Structure

```yaml
sensors:
  <sensor-id>:
    name: My Sensor
    cron: '0 8 * * ? *'               # when the check window opens
    timezone: UTC
    timeout_mins: 60                 # max 7200; must be < cron interval
    frequency_secs: 60               # polling interval (60-600)
    exclude: []
    run_inputs: {}

    checks:
      <check-id>:
        integration: SNOWFLAKE
        sensor_type: SNOWFLAKE_QUERY
        connection: my_snowflake_12345
        parameters:
          query: "SELECT COUNT(*) FROM daily_files WHERE date = CURRENT_DATE"
        map_outputs:
          file_count: "result"

    alerts:
      - name: sensor-timed-out
        statuses: [FAILED]
        destinations:
          - integration: SLACK
            destination: '#data-alerts'
```

---

## Valid SensorChecksEnum Values

| `sensor_type` | Integration | What it checks |
|---|---|---|
| `AWS_S3_FILE` | `AWS_S3` | File exists at S3 prefix |
| `ADLS_FILE` | `AZURE_DATA_LAKE_STORAGE` | File exists in ADLS container |
| `SFTP_FILE` | `SFTP` | File exists on SFTP server |
| `SNOWFLAKE_QUERY` | `SNOWFLAKE` | SQL query returns rows |
| `POSTGRES_QUERY` | `POSTGRES` | SQL query returns rows |
| `GCP_BIG_QUERY_QUERY` | `GCP_BIG_QUERY` | SQL query returns rows |
| `SQL_SERVER_QUERY` | `SQL_SERVER` | SQL query returns rows |
| `DATABRICKS_QUERY` | `DATABRICKS` | SQL query returns rows |
| `FABRIC_SYNAPSE_QUERY` | `FABRIC_SYNAPSE` | SQL query returns rows |
| `ORCHESTRA_PIPELINE_STATUS` | `ORCHESTRA` | Another pipeline completed with a status |
| `ORCHESTRA_WEBHOOK_EVENT` | `ORCHESTRA` | Webhook event received |

---

## Dagster Sensor -> Orchestra Mapping

### S3-polling `@sensor` -> `AWS_S3_FILE`

```python
# Dagster
@sensor(job=transform_job, minimum_interval_seconds=60)
def s3_file_sensor(context, s3: S3Resource):
    keys = s3.get_client().list_objects_v2(Bucket="my-bucket", Prefix="data/")
    if keys.get("KeyCount", 0) > 0:
        yield RunRequest(run_key="data-arrived")
    else:
        yield SkipReason("no file yet")
```

```yaml
# Orchestra
sensors:
  wait-for-s3-file:
    name: Wait for daily orders file
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
          prefix: data/
```

### SQL-polling `@sensor` -> `SNOWFLAKE_QUERY`

```python
# Dagster
@sensor(job=process_job, minimum_interval_seconds=300)
def data_ready_sensor(context, snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        count = conn.cursor().execute(
            "SELECT COUNT(*) FROM orders WHERE created_date = CURRENT_DATE").fetchone()[0]
    if count > 0:
        yield RunRequest(run_key=str(context.cursor))
```

```yaml
# Orchestra
sensors:
  wait-for-snowflake-data:
    name: Wait for daily order data
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
          query: "SELECT COUNT(*) FROM orders WHERE created_date = CURRENT_DATE"
        map_outputs:
          order_count: "result"
```

### `@asset_sensor` on an upstream materialization -> prefer `trigger_events:`

If the upstream is another Orchestra pipeline, use `trigger_events:` rather than polling:

```yaml
trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-upstream-pipeline"
    statuses: [SUCCEEDED, WARNING]
```

Or a polling sensor:

```yaml
sensors:
  wait-for-upstream:
    name: Wait for upstream pipeline
    cron: '0 5 * * ? *'
    timezone: UTC
    timeout_mins: 120
    checks:
      pipeline-check:
        integration: ORCHESTRA
        sensor_type: ORCHESTRA_PIPELINE_STATUS
        parameters:
          pipeline_id: "uuid-of-upstream-pipeline"
          status: SUCCEEDED
```

---

## Before / After Example

### Dagster (before)

```python
from dagster import sensor, RunRequest, SkipReason, Definitions
from dagster_aws.s3 import S3Resource

@sensor(job=transform_job, minimum_interval_seconds=60)
def s3_file_sensor(context, s3: S3Resource):
    keys = s3.get_client().list_objects_v2(Bucket="my-bucket", Prefix="data/")
    if keys.get("KeyCount", 0) > 0:
        yield RunRequest(run_key="data-arrived")
    else:
        yield SkipReason("no file yet")

defs = Definitions(jobs=[transform_job], sensors=[s3_file_sensor])
```

### Orchestra YAML (after)

```yaml
version: v1
name: daily-pipeline

sensors:
  wait-for-orders-file:
    name: Wait for daily orders file
    cron: '0 6 * * ? *'
    timezone: UTC
    timeout_mins: 60
    frequency_secs: 60
    checks:
      s3-check:
        integration: AWS_S3
        sensor_type: AWS_S3_FILE
        connection: aws_default_12345
        parameters:
          bucket_name: my-bucket
          prefix: data/

pipeline:
  stage-transform:
    tasks:
      transform:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        name: transform
        connection: snowflake_prod_12345
        parameters:
          statement: 'INSERT INTO orders_final SELECT * FROM orders_raw'
        depends_on: []
```

---

## Gotchas

- **Sensors are triggers, not tasks** — they live at the pipeline root under `sensors:`.
- **Arbitrary Python -> declarative checks** — map complex `@sensor` logic to the closest `SensorChecksEnum`, or run a PYTHON task at the start of the pipeline.
- **`@asset_sensor` -> prefer `trigger_events:`** — if upstream is an Orchestra pipeline.
- **`timeout_mins` < cron interval** — a daily cron with `timeout_mins: 1500` exceeds 24h.
- **Sensor `cron` is 6-field AWS EventBridge syntax** — `minute hour day-of-month month day-of-week year`, one of dom/dow must be `?`. Don't copy Dagster's 5-field `cron_schedule` verbatim.
- **SQL check semantics** — passes when the query returns >= 1 row.
- **`map_outputs`** — declare matching `inputs:` to reference results.
- **`RunRequest(run_config=...)` -> `run_inputs`**.
- **`minimum_interval_seconds` -> `frequency_secs`** (clamped 60-600).
- **Pure cron `@schedule` is NOT a sensor** — that belongs in `schedule:`.

## References

- Orchestra sensors: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- SensorChecksEnum: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema#sensorchecksmodel
- Dagster sensors: https://docs.dagster.io/concepts/automation/sensors
- Dagster asset sensors: https://docs.dagster.io/concepts/automation/asset-sensors
