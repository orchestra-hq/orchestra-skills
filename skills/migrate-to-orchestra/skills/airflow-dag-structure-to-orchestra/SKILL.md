---
name: airflow-dag-structure-to-orchestra
description: "Use this skill when converting any Airflow DAG to Orchestra YAML to handle DAG-level configuration. Triggers: any Airflow DAG definition containing schedule_interval, default_args, max_active_runs, catchup, params, start_date, or DAG-level tags. Must be applied before converting individual tasks — it establishes the pipeline root fields that wrap all task conversions."
---

# Airflow DAG Structure → Orchestra Pipeline Root

## Overview

Every Airflow DAG has a set of top-level configuration fields that control scheduling, retries, concurrency, and metadata. These don't map to tasks — they map to root-level fields on the Orchestra pipeline YAML. This skill must be applied first, before any task-level conversion, to establish the correct pipeline skeleton.

---

## Field Mapping Reference

### `schedule_interval` → `schedule:`

| Airflow | Orchestra | Notes |
|---|---|---|
| `schedule_interval='@daily'` | `cron: '0 0 ? * * *'` | Expand shorthand, then convert to Orchestra's 6-field AWS EventBridge cron |
| `schedule_interval='@hourly'` | `cron: '0 * * * ? *'` | |
| `schedule_interval='@weekly'` | `cron: '0 0 ? * 1 *'` | AWS EventBridge day-of-week is 1-7 (1=SUN), not Airflow's 0-6 (0=SUN) |
| `schedule_interval='@monthly'` | `cron: '0 0 1 * ? *'` | |
| `schedule_interval='0 4 * * *'` | `cron: '0 4 * * ? *'` | Airflow's 5-field cron is NOT copied verbatim — append `?`/year, see below |
| `schedule_interval=None` | _(omit `schedule:`)_ | Manual trigger only — use `webhook: {enabled: true}` instead |
| `schedule_interval=timedelta(hours=6)` | `cron: '0 */6 * * ? *'` | Convert timedelta to nearest cron equivalent |

**Orchestra requires a 6-field AWS EventBridge cron, not standard 5-field cron.** Airflow's `schedule_interval` (and Dagster's `cron_schedule`, Prefect's `CronSchedule`) use standard 5-field cron (`minute hour day-of-month month day-of-week`). Orchestra's `cron:` field is 6-field: `minute hour day-of-month month day-of-week year`, and — like AWS EventBridge — exactly one of `day-of-month`/`day-of-week` must be `?` while the other carries the real value (or both wildcarded, with `day-of-week` set to `?`). The API rejects a 5-field string with "Incorrect number of values ... 6 required, 5 provided." Always append the `?`/year fields when converting; never copy the source cron string verbatim.

Orchestra `ScheduleModel` full structure:

```yaml
schedule:
  - cron: '0 4 * * ? *'        # required — 6-field AWS EventBridge cron (minute hour dom month dow year)
    timezone: UTC             # optional — IANA timezone (default UTC)
    name: daily-4am           # optional — human label
    run_inputs: {}            # optional — input values for this schedule trigger
    exclude: []               # optional — list of YYYY-MM-DD dates to skip
```

Multiple schedules are supported — add one entry per cron.

### `default_args` → `configuration:` + `alerts:`

| Airflow `default_args` key | Orchestra field | Notes |
|---|---|---|
| `retries` | `configuration.retries` | Integer |
| `retry_delay` (timedelta) | `configuration.retry_delay` | Integer MINUTES — `timedelta(minutes=5)` → `5`, `timedelta(seconds=90)` → `2` (round up). **Capped at 120 minutes** — clamp longer delays and flag with a comment |
| `execution_timeout` (timedelta) | `configuration.timeout` | Integer seconds |
| `email_on_failure: True` | `alerts:` block with `integration: EMAIL` | See alerts section below |
| `email_on_retry: True` | _(no equivalent)_ | Drop with comment |
| `email` (list) | `alerts.destinations.destination` | The email address(es) to notify |
| `on_failure_callback` | `alerts:` block with `statuses: [FAILED]` | See slack-airflow-to-orchestra skill |
| `on_success_callback` | `alerts:` block with `statuses: [SUCCEEDED]` | |
| `sla_miss_callback` | _(no equivalent)_ | Drop with comment — see Gotchas below and `airflow-alerts-to-orchestra` |
| `owner` | _(no equivalent)_ | Drop — use `meta:` if you need to preserve it |
| `depends_on_past` | _(no equivalent)_ | Orchestra is stateless per run — drop with comment |
| `start_date` | _(no equivalent)_ | Drop — activate the schedule in Orchestra UI |
| `end_date` | _(no equivalent)_ | Drop — deactivate in Orchestra UI |
| `pool` / `priority_weight` / `queue` | _(no equivalent)_ | See dedicated section below — don't silently drop these without flagging |

### `max_active_runs` → `configuration.concurrency.max_active`

```yaml
# Airflow
with DAG(..., max_active_runs=1):

# Orchestra
configuration:
  concurrency:
    max_active: 1    # 0 or null = no limit
```

### `catchup` → _(drop)_

Orchestra has no backfill/catchup concept. DAGs always run from the time they are activated. Drop `catchup=True/False` entirely and note it in a comment.

### `TaskGroup` → Orchestra stage (flat — Orchestra stages don't nest)

Airflow's `TaskGroup` (`from airflow.utils.task_group import TaskGroup`, used as `with TaskGroup("group_id") as tg: ...`) is a purely visual/organizational grouping — it doesn't change scheduling semantics, just how tasks are drawn in the UI and namespaced (`group_id.task_id`). Orchestra's equivalent container is the `TaskGroupModel` under `pipeline.<stage-id>`, but — confirmed against Orchestra's live JSONSchema — **`TaskGroupModel` has no nested-stage field, only a flat `tasks:` dict.** A Airflow `TaskGroup` therefore maps to **one Orchestra stage containing all of that group's tasks**, not a nested stage-within-a-stage.

```python
# Airflow
with TaskGroup("extract_and_load") as extract_and_load:
    extract = PythonOperator(task_id="extract", ...)
    load = SnowflakeOperator(task_id="load", ...)
    extract >> load
```

```yaml
# Orchestra — group's tasks become one stage; group_id becomes the stage id
pipeline:
  extract-and-load:            # from TaskGroup("extract_and_load")
    tasks:
      extract:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: extract
        depends_on: []
        ...
      load:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        name: load
        depends_on: [extract]   # intra-group ordering preserved via depends_on
        ...
    depends_on: []
```

**Nested `TaskGroup`s** (a `TaskGroup` inside another `TaskGroup`) have no direct Orchestra equivalent either, since stages can't nest. Flatten every level into a single stage per top-level group, and preserve the original nesting order purely through each task's `depends_on:` chain — the Orchestra stage id can still borrow the dotted naming (`outer.inner`) as a human-readable label even though structurally it's flat.

**`default_args` set at the `TaskGroup` level** (Airflow lets a `TaskGroup` override `default_args` for just its members) map to that stage's `configuration:` block, which already supports overriding pipeline-level `configuration:` per the `ConfigurationModel` section below — no new mechanism needed, just apply the DAG-structure mapping rules (retries, retry_delay, etc.) at the stage's `configuration:` instead of the pipeline root.

### `pool` / `priority_weight` / `queue` → _(no equivalent — drop, but don't do it silently)_

Airflow's resource-management knobs (`pool="snowflake_pool"`, `priority_weight=10`, `queue="high_mem"`) control worker-level scheduling and rate-limiting against Airflow's own executor. Orchestra has no resource-pool or priority-queue concept — there's nothing in the schema to map these onto.

```python
# Airflow
load_task = SnowflakeOperator(
    task_id="load_orders",
    pool="snowflake_pool",       # limits concurrent Snowflake connections across the whole Airflow deployment
    priority_weight=10,
    queue="high_mem",
    ...
)
```

```yaml
# Orchestra — pool/priority_weight/queue dropped; note original values in a comment
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_QUERY
  name: load_orders
  # MANUAL: source had pool='snowflake_pool', priority_weight=10, queue='high_mem' —
  # no Orchestra equivalent; if this pool existed to rate-limit concurrent warehouse
  # connections across many DAGs, that constraint is now unenforced and needs a
  # manual review (see Gotchas below).
  ...
```

Don't just quietly drop these — the closest available mechanism is `configuration.concurrency.max_active` (already documented above), but it caps concurrency *within a single pipeline*, not *across pipelines sharing a scarce resource* the way an Airflow `pool` does. If the source DAG's `pool` usage looks load-bearing (e.g. genuinely rate-limiting a warehouse or API with a hard connection cap), flag it as a manual-review item rather than treating the drop as a no-op.

### `params` / Jinja `{{ var.value.x }}` → `inputs:`

Airflow DAG `params` and `Variable.get()` calls become Orchestra `inputs:` declarations. Reference them in tasks with `${{ inputs.name }}`.

```yaml
# Airflow
params = {"env": "prod", "table": "orders"}
# or Variable.get("my_table")

# Orchestra
inputs:
  env:
    type: string
    default: prod
  table:
    type: string
    default: orders
    optional: true    # true = not required at trigger time
```

Valid `type` values: `string`, `number`, `boolean`, `dict`, `list`.

Reference in task parameters: `${{ inputs.env }}`, `${{ inputs.table }}`.

**Don't over-apply this to every `os.getenv()` call.** This rule is for Airflow's actual `params`/`Variable.get()` mechanism — values genuinely meant to be tunable per trigger. A plain `os.getenv("SLACK_CHANNEL", "#analytics")` used just to read a static config value (a Slack channel, a workspace ID, any other destination-style value) isn't the same thing — if the value is known/available and nothing in the DAG actually varies it, put the resolved literal directly in the YAML (e.g. `channel_name: '#analytics'`) instead of routing it through `inputs:` or `${{ ENV.* }}`. Only use `inputs:`/`${{ ENV.* }}` for these when the source pipeline explicitly needs the value to vary (per environment, per branch, etc.) — see `slack-airflow-to-orchestra` for the concrete case.

### `tags` → task-level `tags:` only (not on the group)

```yaml
# Airflow
with DAG(..., tags=["elt", "daily"]):

# Orchestra — add to EVERY task individually; TaskGroupModel (the stage) has no tags field
pipeline:
  stage-001:
    tasks:
      task-001:
        tags:
          - elt
          - daily
```

**Confirmed live against Orchestra's `/pipelines/schema` validator:** putting `tags:` directly on a stage (`pipeline.<stage-id>.tags`) is rejected with `"extra_forbidden"` — `tags` only exists on `TaskModel`, not `TaskGroupModel`. DAG-level tags must be copied onto every task in the pipeline, not set once on the enclosing stage.

### `email_on_failure` → `alerts:` block

```yaml
alerts:
  - name: email-on-failure
    statuses:
      - FAILED
    destinations:
      - integration: EMAIL
        destination: 'data-team@example.com'
    custom_message: 'Pipeline failed — check Orchestra logs.'
```

Multiple email recipients: add one `destinations` entry per address.

---

## Conversion Checklist

Work through these in order before converting any tasks:

- [ ] `schedule_interval` → `schedule:` block with `cron:` and `timezone:`
- [ ] `max_active_runs` → `configuration.concurrency.max_active`
- [ ] `retries` + `retry_delay` → `configuration.retries` + `configuration.retry_delay` (minutes, not seconds)
- [ ] `execution_timeout` → `configuration.timeout` (seconds)
- [ ] `email_on_failure` / `email` → `alerts:` block with `integration: EMAIL`
- [ ] `on_failure_callback` / `on_success_callback` → `alerts:` block (see slack skill)
- [ ] `params` / `Variable.get()` → `inputs:` block
- [ ] `tags` → preserve on every task individually — NOT on the enclosing stage (`TaskGroupModel` has no `tags` field)
- [ ] `TaskGroup` → flatten into one Orchestra stage per top-level group (no nested stages)
- [ ] `pool` / `priority_weight` / `queue` → drop with a `# MANUAL:` comment; flag as manual review if load-bearing
- [ ] Drop: `catchup`, `start_date`, `end_date`, `depends_on_past`, `owner`, `email_on_retry`, `sla_miss_callback`
- [ ] `schedule_interval=None` → omit `schedule:`, set `webhook: {enabled: true}` if HTTP-triggered
- [ ] Dynamic task mapping (`.expand()`/`.partial()`)? → see `airflow-dynamic-task-mapping-to-orchestra` instead, not covered by this skill

---

## Full Before / After Example

### Airflow DAG (before)

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.models import Variable

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
    "email_on_failure": True,
    "email_on_retry": False,
    "email": ["data-alerts@example.com"],
    "on_failure_callback": slack_fail_alert,
}

with DAG(
    "nightly_elt",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["elt", "nightly"],
    params={"target_env": "prod"},
) as dag:
    ...
```

### Orchestra YAML root (after)

```yaml
version: v1
name: nightly-elt

# schedule_interval='0 2 * * *'
schedule:
  - cron: '0 2 * * ? *'
    timezone: UTC

# max_active_runs=1
# retries=2, retry_delay=5min, execution_timeout=1hr
configuration:
  retries: 2
  retry_delay: 5
  timeout: 3600
  concurrency:
    max_active: 1

# params={"target_env": "prod"}
inputs:
  target_env:
    type: string
    default: prod

# email_on_failure + on_failure_callback
alerts:
  - name: email-on-failure
    statuses:
      - FAILED
    destinations:
      - integration: EMAIL
        destination: 'data-alerts@example.com'
    custom_message: 'nightly-elt pipeline failed.'

  - name: slack-on-failure
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

# Dropped: owner, depends_on_past, catchup, start_date, email_on_retry
# tags added to each task/group below

pipeline:
  # ... tasks with tags: [elt, nightly]
```

---

## Gotchas

- **`timedelta` → integers, but units differ by field**: `execution_timeout`/`timeout` is integer SECONDS (`timedelta(hours=1)` = `3600`), while `retry_delay` is integer MINUTES (`timedelta(minutes=5)` = `5`, not `300`). Don't pass timedelta objects, and don't apply the seconds conversion to `retry_delay`.
- **`retry_delay` max is 120 minutes**: the API rejects anything longer with "Delay between retries cannot be greater than 120 minutes." If Airflow's `retry_delay` exceeds this, clamp to `120` and add a `# MANUAL:` comment noting the original value. A value that looks small in seconds (e.g. `300`) is huge if mistakenly passed as minutes — always convert to minutes first.
- **`cron` is 6-field, not 5-field**: Orchestra's cron uses AWS EventBridge syntax (`minute hour day-of-month month day-of-week year`). Copying Airflow's 5-field `schedule_interval` string verbatim fails validation with "Incorrect number of values ... 6 required, 5 provided." Always append `?` to one of day-of-month/day-of-week and a trailing `*` for year.
- **`catchup=True`**: Orchestra has no backfill. Note this as a manual process and drop the field.
- **`depends_on_past=True`**: No Orchestra equivalent. If the DAG relies on this for correctness, flag it as a manual review item.
- **Multiple schedules**: Orchestra supports a list under `schedule:` — each entry is a separate cron that independently triggers the pipeline.
- **`Variable.get()` in operator args**: these are runtime values in Airflow. Convert to `inputs:` with appropriate defaults, then reference as `${{ inputs.var_name }}` in task `parameters:`.
- **`start_date`**: drop entirely — activate the pipeline in Orchestra's UI or set `schedule[].exclude` for specific skip dates.
- **`TaskGroup`s don't nest in Orchestra**: confirmed against the live JSONSchema, `TaskGroupModel` only has a flat `tasks:` dict, no nested-group field. A nested Airflow `TaskGroup` structure must flatten to one Orchestra stage per top-level group; preserve nesting order via `depends_on:` between tasks, not via structure.
- **`pool`/`priority_weight`/`queue` have no Orchestra equivalent**: don't silently drop them. If a `pool` was rate-limiting concurrent access to a scarce resource (a warehouse connection cap, a rate-limited API), that constraint disappears on conversion — flag it as a manual review item rather than treating the drop as free.
- **`sla_miss_callback` has no Orchestra equivalent**: SLA monitoring must move to an external monitoring tool. See `airflow-alerts-to-orchestra`'s gotchas for the same note — repeated here since a converter processing `default_args` is looking at this skill, not necessarily the alerts one.
- **`tags` on a stage fails real validation**: confirmed by calling Orchestra's actual `/pipelines/schema` endpoint — `TaskGroupModel` rejects any `tags` key with `"extra_forbidden"`. This looks plausible (Airflow's own DAG-level `tags` naturally maps to "the group"), which is exactly why it shipped as a bug in this skill before being caught against the live API — always put `tags:` on each `TaskModel`, never on the stage wrapping it.

## References

- Orchestra schedule docs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Orchestra inputs docs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema#pipelineinputmodel
