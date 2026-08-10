# Orchestra sensors — shared reference

Canonical Orchestra-side syntax for the `sensors:` block, shared by `airflow-sensors-to-orchestra`
and `dagster-sensors-to-orchestra`. Each of those skills covers the source-specific mapping (which
Airflow sensor operator / Dagster `@sensor` pattern produces which `SensorChecksEnum` value, and
how to recognize one in source); this file is the Orchestra side only — the part that's identical
regardless of source orchestrator.

There is no `prefect-sensors-to-orchestra` skill — Prefect's equivalent polling/reactive patterns
are covered by `prefect-automations-to-orchestra`, which models them through Orchestra's
`trigger_events:`/alerting surface rather than this `sensors:` block, so it isn't a consumer of
this reference.

**Not covered here — stays in each skill, deliberately not shared:** the per-sensor-type mapping
(which Airflow operator class or Dagster `@sensor`/decorator pattern maps to which `sensor_type`),
since the source vocabulary genuinely differs per orchestrator; the per-source "how do I recognize
this pattern in source" test; the full before/after DAG/job examples; and the Gotchas sections,
which read similarly but each carry source-specific caveats (e.g. Airflow's `TimeSensor`/
`TimeDeltaSensor` having no equivalent, Dagster's `minimum_interval_seconds` → `frequency_secs`
mapping) that don't cleanly collapse into one shared list.

The schema below (`SensorModel` / `SensorCheckModel` / `SensorChecksEnum`) is live-verified against
the real Orchestra backend via the `validate_pipeline` MCP tool — not a cached schema file or
docs-page rendering, both of which can drift or be mis-rendered. Re-verify the same way if this
ever needs updating.

## SensorModel schema

Sensors are **pipeline triggers**, not pipeline tasks — they live in the `sensors:` block at the
pipeline root (not inside `pipeline:`). When all checks in a sensor pass, the pipeline run is
triggered automatically.

```yaml
sensors:
  <sensor-id>:
    name: My Sensor                  # required, max 100 chars
    cron: '0 8 * * ? *'              # required — when the check window opens
    timezone: UTC                    # required — IANA timezone
    timeout_mins: 60                 # required — max 7200; must be < cron interval
    frequency_secs: 60               # optional — polling interval (60–600, default 60)
    exclude: []                      # optional — YYYY-MM-DD dates to skip
    run_inputs: {}                   # optional — inputs to pass when the sensor triggers

    checks:                          # required — dict of SensorCheckModel
      <check-id>:
        integration: SNOWFLAKE       # IntegrationsEnum
        sensor_type: SNOWFLAKE_QUERY # SensorChecksEnum — see below
        connection: my_snowflake_12345
        parameters:
          query: "SELECT COUNT(*) FROM daily_files WHERE date = CURRENT_DATE"
        map_outputs:                 # optional — pipe check results to pipeline inputs
          file_count: "result"       # pipeline input name → check output field

    alerts:                          # optional — sensor-level alerts, same AlertModel as elsewhere
      - name: sensor-timed-out
        statuses: [FAILED]
        destinations:
          - integration: SLACK
            destination: '#data-alerts'
```

Notes that apply regardless of source orchestrator:

- **`cron` is 6-field AWS EventBridge syntax**, not a standard 5-field cron string —
  `minute hour day-of-month month day-of-week year`, with exactly one of day-of-month/day-of-week
  set to `?`. A 5-field string fails validation with "6 required, 5 provided."
- **`timeout_mins` must be shorter than the `cron` interval** — e.g. a daily cron window with
  `timeout_mins: 1500` would exceed 24 hours; cap it appropriately.
- **All checks under one sensor are AND'd together** — every check must pass for the sensor to
  fire. Use separate sensors for OR logic.
- **`map_outputs`** pipes a check's result into the pipeline's own `inputs:` — the pipeline must
  declare a matching `inputs:` entry for `${{ inputs.key }}` to resolve.

## SensorChecksEnum values

| `sensor_type` | Integration | What it checks |
|---|---|---|
| `AWS_S3_FILE` | `AWS_S3` | File exists at S3 prefix |
| `ADLS_FILE` | `AZURE_DATA_LAKE_STORAGE` | File exists in ADLS container |
| `SFTP_FILE` | `SFTP` | File exists on SFTP server |
| `CLICKHOUSE_QUERY` | `CLICKHOUSE` | SQL query returns at least one row |
| `SNOWFLAKE_QUERY` | `SNOWFLAKE` | SQL query returns at least one row |
| `POSTGRES_QUERY` | `POSTGRES` | SQL query returns at least one row |
| `GCP_BIG_QUERY_QUERY` | `GCP_BIG_QUERY` | SQL query returns at least one row |
| `SQL_SERVER_QUERY` | `SQL_SERVER` | SQL query returns at least one row |
| `DATABRICKS_QUERY` | `DATABRICKS` | SQL query returns at least one row |
| `FABRIC_SYNAPSE_QUERY` | `FABRIC_SYNAPSE` | SQL query returns at least one row |
| `ORCHESTRA_PIPELINE_STATUS` | `ORCHESTRA` | Another pipeline completed with a given status |
| `ORCHESTRA_WEBHOOK_EVENT` | `ORCHESTRA` | Webhook event received |

For the SQL-based checks, the check passes once the query returns at least one row — write a query
that only returns a row when the condition you're waiting on is actually met.

## Waiting on another pipeline

When the thing being waited on is another Orchestra pipeline's completion, prefer `trigger_events:`
over a polling sensor — it's event-driven rather than poll-based:

```yaml
trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-upstream-pipeline"
    statuses: [SUCCEEDED, WARNING]
```

If you need poll-based semantics instead (e.g. to combine it with other checks in the same
sensor), use an `ORCHESTRA_PIPELINE_STATUS` check:

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

## References

- Orchestra sensors: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- SensorChecksEnum: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema#sensorchecksmodel
