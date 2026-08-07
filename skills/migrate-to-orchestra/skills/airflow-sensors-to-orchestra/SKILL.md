---
name: airflow-sensors-to-orchestra
description: "Use this skill when an Airflow DAG contains sensor operators: S3KeySensor, FileSensor, SqlSensor, ExternalTaskSensor, TimeSensor, or any *Sensor class. Triggers: any DAG with poke_interval, mode='reschedule', or sensor-based waiting patterns. Sensors in Orchestra are first-class pipeline triggers defined in a sensors: block, not pipeline tasks."
---

# Airflow Sensors → Orchestra Sensors Block

## Overview

Airflow sensors are tasks that poll an external system until a condition is met, then allow downstream tasks to proceed. In Orchestra, sensors are **pipeline triggers** — they live in the `sensors:` block at the pipeline root (not inside `pipeline:`). When all sensor checks pass, the pipeline run is triggered automatically.

Key difference: Airflow sensors are inline DAG steps. Orchestra sensors are external watchers that start pipeline runs. They use a cron window + polling interval model.

Sensor checks also carry a `connection:` field — for mapping the sensor's `aws_conn_id=`/`conn_id=` to the right Orchestra connection type, see `airflow-connections-to-orchestra`.

---

## SensorModel Structure

```yaml
sensors:
  <sensor-id>:
    name: My Sensor                  # required, max 100 chars
    cron: '0 8 * * ? *'               # required — when the check window opens
    timezone: UTC                    # required — IANA timezone
    timeout_mins: 60                 # required — max 7200; must be < cron interval
    frequency_secs: 60               # optional — polling interval (60–600, default 60)
    exclude: []                      # optional — YYYY-MM-DD dates to skip
    run_inputs: {}                   # optional — inputs to pass when sensor triggers

    checks:                          # required — dict of SensorCheckModel
      <check-id>:
        integration: SNOWFLAKE       # IntegrationsEnum
        sensor_type: SNOWFLAKE_QUERY # SensorChecksEnum (see table below)
        connection: my_snowflake_12345
        parameters:
          query: "SELECT COUNT(*) FROM daily_files WHERE date = CURRENT_DATE"
        map_outputs:                 # optional — pipe check results to pipeline inputs
          file_count: "result"       # pipeline input name → check output field

    alerts:                          # optional — sensor-level alerts
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
| `SNOWFLAKE_QUERY` | `SNOWFLAKE` | SQL query returns rows (or specific value) |
| `POSTGRES_QUERY` | `POSTGRES` | SQL query returns rows |
| `GCP_BIG_QUERY_QUERY` | `GCP_BIG_QUERY` | SQL query returns rows |
| `SQL_SERVER_QUERY` | `SQL_SERVER` | SQL query returns rows |
| `DATABRICKS_QUERY` | `DATABRICKS` | SQL query returns rows |
| `FABRIC_SYNAPSE_QUERY` | `FABRIC_SYNAPSE` | SQL query returns rows |
| `ORCHESTRA_PIPELINE_STATUS` | `ORCHESTRA` | Another pipeline completed with given status |
| `ORCHESTRA_WEBHOOK_EVENT` | `ORCHESTRA` | Webhook event received |

---

## Airflow Sensor → Orchestra Mapping

### S3KeySensor → `AWS_S3_FILE`

```python
# Airflow
S3KeySensor(
    task_id='wait_for_file',
    bucket_key='data/daily/{{ ds }}/orders.csv',
    bucket_name='my-data-bucket',
    aws_conn_id='aws_default',
    poke_interval=60,
    timeout=3600,
)
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
          bucket_name: my-data-bucket
          prefix: data/daily/
```

### SqlSensor (Snowflake) → `SNOWFLAKE_QUERY`

```python
# Airflow
SqlSensor(
    task_id='wait_for_data',
    conn_id='snowflake_prod',
    sql="SELECT COUNT(*) FROM orders WHERE created_date = '{{ ds }}'",
    poke_interval=300,
    timeout=7200,
)
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
          order_count: "result"   # passes row count to pipeline as input
```

### ExternalTaskSensor → `ORCHESTRA_PIPELINE_STATUS`

```python
# Airflow
ExternalTaskSensor(
    task_id='wait_for_upstream',
    external_dag_id='upstream_elt',
    external_task_id=None,   # wait for whole DAG
    poke_interval=60,
    timeout=3600,
)
```

```yaml
# Orchestra — use trigger_events for upstream pipeline completion
trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-upstream-elt-pipeline"
    statuses: [SUCCEEDED, WARNING]
```

Or use a sensor for polling-based wait:

```yaml
sensors:
  wait-for-upstream:
    name: Wait for upstream ELT
    cron: '0 5 * * ? *'
    timezone: UTC
    timeout_mins: 120
    checks:
      pipeline-check:
        integration: ORCHESTRA
        sensor_type: ORCHESTRA_PIPELINE_STATUS
        parameters:
          pipeline_id: "uuid-of-upstream-elt-pipeline"
          status: SUCCEEDED
```

### ADLS FileSensor → `ADLS_FILE`

```yaml
sensors:
  wait-for-adls-file:
    name: Wait for ADLS file
    cron: '0 7 * * ? *'
    timezone: UTC
    timeout_mins: 60
    checks:
      adls-check:
        integration: AZURE_DATA_LAKE_STORAGE
        sensor_type: ADLS_FILE
        connection: azure_adls_prod_12345
        parameters:
          container_name: raw-data
          prefix: orders/daily/
```

---

## Before / After Example

### Airflow DAG (before)

```python
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator

with DAG("daily_pipeline", schedule_interval="0 8 * * *") as dag:
    wait_file = S3KeySensor(
        task_id="wait_for_file",
        bucket_key="data/{{ ds }}/orders.csv",
        bucket_name="my-bucket",
        aws_conn_id="aws_default",
        poke_interval=60,
        timeout=3600,
    )
    transform = SnowflakeOperator(
        task_id="transform",
        snowflake_conn_id="snowflake_prod",
        sql="INSERT INTO orders_final SELECT * FROM orders_raw",
    )
    wait_file >> transform
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

- **Sensors are triggers, not tasks** — they live at the pipeline root under `sensors:`, not inside `pipeline:`. They trigger a pipeline run when checks pass; they don't run as pipeline steps.
- **`timeout_mins` must be shorter than the cron interval** — a daily cron (`0 8 * * ? *`) with `timeout_mins: 1500` would exceed 24 hours; cap it appropriately.
- **Sensor `cron` is 6-field AWS EventBridge syntax, not Airflow's 5-field `schedule_interval`** — `minute hour day-of-month month day-of-week year`, with exactly one of day-of-month/day-of-week set to `?`. A 5-field string fails with "6 required, 5 provided."
- **SQL check semantics** — the check passes when the query returns at least one row. Write queries that return a row only when the condition is met.
- **`map_outputs`** — maps sensor check results to pipeline `inputs:`. The pipeline must declare matching `inputs:` for the values to be accessible via `${{ inputs.key }}`.
- **`TimeSensor` / `TimeDeltaSensor`** — no Orchestra equivalent. Use cron scheduling with an appropriate start time offset instead.
- **Multiple checks** — all checks in a sensor must pass for the sensor to trigger the pipeline. Use multiple `checks:` entries for AND logic; create separate sensors for OR logic.
- **ExternalTaskSensor → prefer `trigger_events:`** — if the upstream pipeline is in Orchestra, `trigger_events:` is cleaner than a polling sensor.

## References

- Orchestra sensors: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- SensorChecksEnum: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema#sensorchecksmodel
