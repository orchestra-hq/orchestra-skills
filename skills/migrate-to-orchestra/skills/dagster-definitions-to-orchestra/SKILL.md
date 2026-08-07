---
name: dagster-definitions-to-orchestra
description: "Use this skill when converting any Dagster job/schedule/Definitions to Orchestra YAML to handle top-level configuration. Triggers: any Dagster code containing ScheduleDefinition, @schedule, build_schedule_from_partitioned_job, RetryPolicy, op/run concurrency limits, run tags (dagster/max_runtime), Config classes, EnvVar, or Definitions. Must be applied before converting individual assets/ops — it establishes the pipeline root fields that wrap all task conversions."
---

# Dagster Definitions / Job Structure -> Orchestra Pipeline Root

## Overview

A Dagster project is described by a `Definitions` object that groups assets, jobs, schedules, sensors, and resources. Scheduling, retries, concurrency, and timeouts are set on jobs (via tags and `RetryPolicy`) and on `ScheduleDefinition` objects. None of these map to individual Orchestra tasks — they map to root-level fields on the Orchestra pipeline YAML. Apply this skill first, before any asset/op-level conversion, to establish the correct pipeline skeleton.

A useful rule of thumb: **one Dagster job (or one cohesive asset selection driven by a schedule) -> one Orchestra pipeline**.

---

## Field Mapping Reference

### `ScheduleDefinition` / `@schedule` -> `schedule:`

| Dagster | Orchestra | Notes |
|---|---|---|
| `cron_schedule="0 2 * * *"` | `cron: '0 2 * * ? *'` | Dagster's cron is standard 5-field — convert to Orchestra's 6-field AWS EventBridge cron, do NOT copy verbatim |
| `cron_schedule="@daily"` | `cron: '0 0 ? * * *'` | Expand shorthand, then convert to 6-field |
| `execution_timezone="Europe/London"` | `timezone: Europe/London` | IANA timezone |
| `ScheduleDefinition(job=...)` | one `schedule:` entry | The schedule targets a job -> the pipeline |
| `@schedule` returning `RunRequest(run_config=...)` | `schedule[].run_inputs` | Map run config values to inputs |
| no schedule (manual / sensor only) | _(omit `schedule:`)_ | Use `webhook: {enabled: true}` or `sensors:`/`trigger_events:` |

**Orchestra requires a 6-field AWS EventBridge cron** (`minute hour day-of-month month day-of-week year`), not Dagster's standard 5-field `cron_schedule`. Exactly one of day-of-month/day-of-week must be `?`. Passing a 5-field string fails validation with "Incorrect number of values ... 6 required, 5 provided."

Orchestra `ScheduleModel`:

```yaml
schedule:
  - cron: '0 2 * * ? *'
    timezone: UTC
    name: nightly
    run_inputs: {}
    exclude: []
```

### Job tags + `RetryPolicy` -> `configuration:`

| Dagster | Orchestra field | Notes |
|---|---|---|
| `RetryPolicy(max_retries=N)` | `configuration.retries` | Integer |
| `RetryPolicy(delay=N)` | `configuration.retry_delay` | Integer MINUTES — Dagster's `delay` is seconds, so convert: `N / 60` (round up). **Capped at 120 minutes** — clamp and flag with a comment if larger |
| `dagster/max_runtime` run tag (seconds) | `configuration.timeout` | Run-termination timeout |
| `Backoff.*` / `Jitter.*` | _(no equivalent)_ | Flat `retry_delay` only — note the simplification |
| op-level vs job-level `RetryPolicy` | pipeline `configuration` or per-task `configuration` | Per-op retries -> per-task `configuration` override |

### Concurrency -> `configuration.concurrency.max_active`

```python
# Dagster (job tag / instance config)
@job(tags={"dagster/concurrency_key": "elt", "dagster/max_concurrent": 1})
def my_job(): ...
```

```yaml
# Orchestra
configuration:
  concurrency:
    max_active: 1     # 0 or null = no limit
```

### Partitions / backfills -> _(drop)_

Dagster `PartitionsDefinition`, partitioned schedules, and backfills have **no Orchestra equivalent** — Orchestra runs from activation forward and does not backfill. Convert only the cron; flag partition/backfill semantics as a manual review item.

### `Config` classes / `RunConfig` / `EnvVar` -> `inputs:`

```python
# Dagster
from dagster import Config

class ELTConfig(Config):
    target_env: str = "prod"
    table: str = "orders"
```

```yaml
# Orchestra
inputs:
  target_env:
    type: string
    default: prod
  table:
    type: string
    default: orders
    optional: true
```

Valid `type` values: `string`, `number`, `boolean`, `dict`, `list`. Reference in task parameters as `${{ inputs.target_env }}`.

`EnvVar("SECRET")` for credentials does **not** become an input — it becomes part of the Orchestra connection (see `dagster-connections-to-orchestra`).

### Asset/op group + run tags -> task-level `tags:` only (not on the group)

```yaml
pipeline:
  stage-001:
    tasks:
      task-001:
        tags:
          - elt
          - nightly
```

**Confirmed live against Orchestra's `/pipelines/schema` validator:** `tags:` directly on a stage (`pipeline.<stage-id>.tags`) is rejected with `"extra_forbidden"` — `tags` only exists on `TaskModel`, not `TaskGroupModel`. Copy Dagster's job/op-group tags onto every task, not once onto the enclosing stage.

---

## Conversion Checklist

- [ ] `ScheduleDefinition.cron_schedule` -> `schedule:` block with `cron:` and `timezone:`
- [ ] concurrency limits -> `configuration.concurrency.max_active`
- [ ] `RetryPolicy(max_retries, delay)` -> `configuration.retries` + `configuration.retry_delay` (minutes — convert Dagster's seconds `delay` by dividing by 60)
- [ ] `dagster/max_runtime` tag -> `configuration.timeout` (seconds)
- [ ] failure/success notifications (run status sensors, hooks) -> `alerts:` block (see dagster-alerts-to-orchestra)
- [ ] `Config` / `RunConfig` non-secret values -> `inputs:` block
- [ ] `EnvVar` secrets -> Orchestra connection (never inline)
- [ ] tags -> preserve on every task individually — NOT on the enclosing stage (`TaskGroupModel` has no `tags` field)
- [ ] Drop: partitions, backfills, `Backoff`/`Jitter` strategies
- [ ] no schedule -> omit `schedule:`, set `webhook: {enabled: true}` if event-triggered

---

## Full Before / After Example

### Dagster (before)

```python
from dagster import Definitions, job, op, ScheduleDefinition, RetryPolicy, Backoff

default_retry = RetryPolicy(max_retries=2, delay=300, backoff=Backoff.LINEAR)

@op(retry_policy=default_retry)
def extract(): ...

@op(retry_policy=default_retry)
def load(extracted): ...

@job(tags={"dagster/max_runtime": 3600, "team": "data-team"})
def nightly_elt():
    load(extract())

nightly_schedule = ScheduleDefinition(
    job=nightly_elt, cron_schedule="0 2 * * *", execution_timezone="UTC",
)

defs = Definitions(jobs=[nightly_elt], schedules=[nightly_schedule])
```

### Orchestra YAML root (after)

```yaml
version: v1
name: nightly-elt

# ScheduleDefinition(cron_schedule="0 2 * * *", execution_timezone="UTC")
schedule:
  - cron: '0 2 * * ? *'
    timezone: UTC

# RetryPolicy(max_retries=2, delay=300 seconds -> 5 minutes) + dagster/max_runtime=3600
configuration:
  retries: 2
  retry_delay: 5
  timeout: 3600

# Notifications converted from run status sensors / hooks
alerts:
  - name: slack-on-failure
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

# Dropped: Backoff.LINEAR strategy, team tag (use meta: if needed)
pipeline:
  # ... extract -> load tasks below, each with tags: [elt, nightly] (task-level only)
```

---

## Gotchas

- **`RetryPolicy.delay` is seconds, but `retry_delay` is minutes** — Orchestra's field is integer MINUTES despite the name, so divide Dagster's `delay` by 60 (round up), don't just cast to int. No timedelta conversion (that is the Airflow trap, not Dagster). Cap at `120` minutes regardless.
- **`cron_schedule` is 5-field, Orchestra's `cron` is 6-field** — never copy verbatim; append `?`/year per the AWS EventBridge rule above.
- **`Backoff` / `Jitter`** — Orchestra `retry_delay` is a flat integer. Backoff/jitter strategies have no equivalent; use the base delay and note the simplification.
- **Partitions / backfills** — `PartitionsDefinition`, partitioned schedules and backfills have no Orchestra equivalent. Convert the cron only and flag the partition logic.
- **`Definitions` with multiple jobs** — each Dagster job typically becomes its own Orchestra pipeline (separate YAML), not multiple stages in one pipeline.
- **`RunConfig` / `Config`** — op/asset run config becomes Orchestra `inputs:` referenced via `${{ inputs.x }}`.
- **`EnvVar`** — non-secret values map to `inputs:`; secrets map to the Orchestra connection, never inline.
- **Concurrency** — op/run concurrency limits map to `configuration.concurrency.max_active`.
- **`tags` on a stage fails real validation** — confirmed by calling Orchestra's actual `/pipelines/schema` endpoint — `TaskGroupModel` rejects any `tags` key with `"extra_forbidden"`. Always put `tags:` on each `TaskModel`, never on the stage wrapping it.

## References

- Orchestra schedule docs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Dagster schedules: https://docs.dagster.io/concepts/automation/schedules
- Dagster RetryPolicy: https://docs.dagster.io/concepts/ops-jobs-graphs/op-retries
- Dagster run config: https://docs.dagster.io/concepts/configuration/config-schema
