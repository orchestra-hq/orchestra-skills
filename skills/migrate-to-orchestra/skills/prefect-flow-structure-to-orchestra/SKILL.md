---
name: prefect-flow-structure-to-orchestra
description: "Use this skill when converting any Prefect flow to Orchestra YAML to handle flow-level configuration. Triggers: any Prefect flow definition containing @flow, schedule= (CronSchedule, IntervalSchedule, RRuleSchedule), retries=, timeout_seconds=, flow.deploy() or flow.serve() deployment config, flow parameters (typed function args), or flow-level tags. Must be applied before converting individual tasks — it establishes the pipeline root fields that wrap all task conversions."
---

## Overview

This skill handles conversion of Prefect `@flow`-level constructs into Orchestra pipeline root fields. Apply it first, before converting individual tasks. It covers scheduling, retries, timeouts, typed parameters, tags, concurrency, and deployment config.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `@flow(name="my-flow")` | `name: my-flow` | kebab-case recommended |
| `CronSchedule(cron="0 2 * * *", timezone="UTC")` | `schedule: [{cron: "0 2 * * ? *", timezone: UTC}]` | Prefect's cron is standard 5-field — convert to Orchestra's 6-field AWS EventBridge cron, do NOT copy verbatim |
| `IntervalSchedule(interval=timedelta(hours=6))` | `schedule: [{cron: "0 */6 * * ? *"}]` | Non-clean intervals → MANUAL note |
| `RRuleSchedule(...)` | MANUAL note | No rrule support in Orchestra |
| `def my_flow(env: str = "prod")` | `inputs: {env: {type: string, default: prod}}` | int/float→number, str→string, bool→boolean |
| `@flow(retries=2, retry_delay_seconds=300)` | `configuration: {retries: 2, retry_delay: 5}` | Orchestra's `retry_delay` is MINUTES — convert seconds/60 (round up); **cap at 120** — clamp and flag if larger |
| `@flow(timeout_seconds=3600)` | `configuration: {timeout: 3600}` | |
| tag-based concurrency limit | `configuration: {concurrency: {max_active: 1}}` | + MANUAL note |
| `@flow(log_prints=True)` | drop | No equivalent; omit |
| `@flow(tags=["elt"])` | `tags: [elt]` on each task individually (NOT on the group — `TaskGroupModel` has no `tags` field) | |
| `SecretStr` params | → `prefect-secrets-to-orchestra` | never inline |

## Orchestra YAML Structure

```yaml
version: v1
name: nightly-elt
schedule:
  - cron: '0 2 * * ? *'
    timezone: UTC
configuration:
  retries: 2
  retry_delay: 5
  timeout: 3600
inputs:
  target_env:
    type: string
    default: prod
  row_limit:
    type: number
    default: 0
    optional: true
pipeline:
  # ... tasks with tags: [elt]
```

## Conversion Steps

- [ ] Extract `@flow(name=...)` → `name:` (kebab-case)
- [ ] Extract schedule from `.serve()` or `.deploy()` call → `schedule:` array
- [ ] Map `CronSchedule` → convert 5-field cron to Orchestra's 6-field AWS EventBridge cron + timezone; `IntervalSchedule` → approximate cron or MANUAL note; `RRuleSchedule` → MANUAL note
- [ ] Extract typed function params → `inputs:` (str→string, int/float→number, bool→boolean, dict→dict, list→list)
- [ ] Map `retries=`, `retry_delay_seconds=` → `configuration.retries`, `configuration.retry_delay` (convert seconds to minutes)
- [ ] Map `timeout_seconds=` → `configuration.timeout`
- [ ] Map `tags=` → propagate to each task's `tags:` field
- [ ] Drop `log_prints`, `persist_result`, `result_storage` (no Orchestra equivalent)
- [ ] Flag `SecretStr` params for `prefect-secrets-to-orchestra`
- [ ] Flag `on_failure`/`on_completion` hooks for `prefect-alerts-to-orchestra`

## Before / After Example

### Prefect (before)

```python
from prefect import flow
from prefect.schedules import CronSchedule

@flow(name="nightly-elt", retries=2, retry_delay_seconds=300, timeout_seconds=3600, tags=["elt"])  # retry_delay_seconds=300 -> retry_delay: 5 (minutes)
def nightly_elt(target_env: str = "prod", row_limit: int = 0):
    ...

if __name__ == "__main__":
    nightly_elt.serve(schedule=CronSchedule(cron="0 2 * * *", timezone="UTC"))
```

### Orchestra YAML (after)

```yaml
version: v1
name: nightly-elt
schedule:
  - cron: '0 2 * * ? *'
    timezone: UTC
configuration:
  retries: 2
  retry_delay: 5
  timeout: 3600
inputs:
  target_env:
    type: string
    default: prod
  row_limit:
    type: number
    default: 0
    optional: true
pipeline:
  # ... tasks with tags: [elt]
```

## Gotchas

- `IntervalSchedule` with non-standard intervals has no clean cron equivalent — add `# MANUAL:` comment
- `RRuleSchedule` → always MANUAL; Orchestra has no rrule support
- `retry_delay_seconds` is in seconds but Orchestra's `retry_delay` field is MINUTES despite the similar name — divide by 60 (round up), don't pass the raw seconds value. Orchestra caps `retry_delay` at 120 (minutes); clamp and flag longer values. Passing a seconds value unconverted (e.g. `300`) will be read as 300 minutes and rejected by the API with "Delay between retries cannot be greater than 120 minutes."
- `CronSchedule.cron` is standard 5-field — Orchestra's `cron:` is 6-field AWS EventBridge syntax (`minute hour day-of-month month day-of-week year`, one of dom/dow must be `?`). Copying it verbatim fails with "6 required, 5 provided."
- `on_failure`/`on_completion` hooks → route to `prefect-alerts-to-orchestra`
- One Prefect deployment = one Orchestra pipeline; multiple deployments of the same flow → multiple pipelines
- `SecretStr` parameters must never be inlined — route to `prefect-secrets-to-orchestra`
- `@flow(log_prints=True)` and `persist_result` have no Orchestra equivalent; drop silently
- **`tags` on a stage fails real validation** — confirmed by calling Orchestra's actual `/pipelines/schema` endpoint — `TaskGroupModel` rejects any `tags` key with `"extra_forbidden"`. Always put `tags:` on each `TaskModel`, never on the stage wrapping it.

## References

- [Orchestra pipeline schema](https://docs.getorchestra.io/docs/core-concepts/pipelines/schema)
- [Prefect flows](https://docs.prefect.io/v3/develop/write-flows)
- [Prefect schedules](https://docs.prefect.io/v3/automate/add-schedules)
- [Prefect deployments](https://docs.prefect.io/v3/deploy/index)

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
