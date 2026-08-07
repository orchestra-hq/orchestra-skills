---
name: prefect-cross-flow-to-orchestra
description: "Use this skill when a Prefect flow triggers another deployment using run_deployment(), or when a flow is called as a subflow from a parent @flow. Triggers: any Prefect code with run_deployment(), await run_deployment(), or a @flow function called inside another @flow (subflow pattern)."
---

## Overview

Prefect cross-flow coordination uses two patterns: `run_deployment()` (trigger a separate deployment, optionally waiting for completion) and subflows (calling one `@flow` from inside another). In Orchestra, both patterns become separate pipelines. The recommended approach for cross-pipeline triggering is `trigger_events:` on the downstream pipeline, which fires when an upstream pipeline reaches a given status.

**Important schema note:** `TRIGGER_PIPELINE` does not appear in the verified `IntegrationJobsEnum`. For cross-pipeline triggering, use `trigger_events:` on the downstream pipeline root. If your Orchestra version does support `TRIGGER_PIPELINE` as a task job, verify against your instance's schema before using it.

## Parameter Mapping

| Prefect construct | Orchestra equivalent | Notes |
|---|---|---|
| `run_deployment("name/deployment")` — fire and wait | `trigger_events:` on downstream pipeline | downstream waits for upstream SUCCEEDED |
| `run_deployment(..., timeout=0)` — fire and forget | `trigger_events:` on downstream pipeline | set `statuses: [SUCCEEDED]` on upstream |
| Prefect Automation: on parent SUCCEEDED → run child | `trigger_events:` at child pipeline root | |
| `child_flow()` called inside `parent_flow()` (subflow) | child → separate Orchestra pipeline; `trigger_events:` | no inline subpipeline concept |
| `run_deployment(..., parameters={...})` | `trigger_events: [{..., run_inputs: {...}}]` | |
| Sequential `run_deployment` calls | chain via `trigger_events:` with `pipeline_id` of each upstream | |
| `await run_deployment(...)` (async) | same as sync — `trigger_events:` | Orchestra handles async natively |

## Orchestra YAML Structure

```yaml
# On the DOWNSTREAM (child) pipeline:
version: v1
name: downstream-pipeline

trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-upstream-pipeline"   # UUID from Orchestra UI pipeline URL
    run_inputs:                                  # optional — equivalent to run_deployment parameters
      env: prod
      date: '{{ run_date }}'
```

Multiple upstream triggers (OR logic — any entry fires the pipeline):

```yaml
trigger_events:
  - type: pipeline
    pipeline_id: "uuid-of-pipeline-a"
  - type: pipeline
    pipeline_id: "uuid-of-pipeline-b"
```

For AND logic (both must complete before downstream runs), create a parent "coordinator" pipeline that sequences the upstreams, then use a single `trigger_events:` entry pointing at the coordinator.

## Conversion Steps

- [ ] Identify every `run_deployment()` call and every subflow invocation (`child_flow()` inside `parent_flow()`)
- [ ] For each triggered deployment / subflow: confirm it has (or create) a corresponding Orchestra pipeline
- [ ] Note the Orchestra pipeline UUID from the UI URL for each upstream pipeline
- [ ] On each downstream pipeline: add a `trigger_events:` block with `type: pipeline` and the upstream `pipeline_id`
- [ ] If `run_deployment(..., parameters={...})` passes params: add `run_inputs:` under the trigger_event entry
- [ ] For sequential chains (A → B → C): add `trigger_events:` on B pointing to A, and on C pointing to B
- [ ] For AND-logic fan-in: create a coordinator pipeline; have it run after all upstreams; point final downstream at coordinator
- [ ] Remove `run_deployment()` calls from the parent flow body — parent pipeline no longer needs to call child
- [ ] If the Prefect parent flow does work AFTER `run_deployment()` returns: keep that work in the parent; only the trigger moves to `trigger_events:`
- [ ] Do NOT use `TRIGGER_PIPELINE` as an `integration_job` unless verified in your Orchestra instance schema

## Before / After Example

### Prefect (before)

```python
@flow
def child_report_flow(env: str = "prod"):
    # generate daily report
    ...

@flow
def orchestrator_flow():
    # trigger nightly ELT and wait
    run_deployment("nightly-elt/prod", timeout=300)
    # then trigger report with parameters
    run_deployment(
        "daily-report/prod",
        parameters={"env": "prod"},
        timeout=300,
    )

# Subflow pattern
@flow
def parent_flow():
    child_report_flow(env="prod")
```

### Orchestra YAML (after)

```yaml
# nightly-elt pipeline — runs on its own schedule, no changes needed
# (abbreviated)
version: v1
name: nightly-elt
schedule:
  - cron: '0 2 * * ? *'
pipeline:
  {}

---

# daily-report pipeline — triggered by nightly-elt completing
version: v1
name: daily-report

trigger_events:
  - type: pipeline
    pipeline_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"   # UUID of nightly-elt
    run_inputs:
      env: prod

pipeline:
  stage-report:
    tasks:
      {}

---

# child-report pipeline — triggered by parent-flow completing
version: v1
name: child-report

trigger_events:
  - type: pipeline
    pipeline_id: "b2c3d4e5-f6a7-8901-bcde-f12345678901"   # UUID of parent-flow
    run_inputs:
      env: prod

pipeline:
  {}
```

## Gotchas

- `pipeline_id` is a UUID from the Orchestra UI pipeline URL — **never** the pipeline name string
- `TRIGGER_PIPELINE` is not in the verified `IntegrationJobsEnum` — use `trigger_events:` instead; verify before using as task job
- Prefect subflows become **separate** Orchestra pipelines — there is no inline sub-pipeline concept
- `trigger_events:` uses OR logic — any entry firing starts the pipeline; for AND logic, use a coordinator pipeline
- `run_deployment` parameters → `run_inputs` under the trigger_event entry
- If the parent flow does work both before and after `run_deployment()`, split into separate pipelines connected via `trigger_events:`
- `timeout=0` (fire-and-forget) in Prefect → still use `trigger_events:` in Orchestra; Orchestra manages the async execution
- Prefect `await run_deployment()` is equivalent to sync `run_deployment()` — same Orchestra pattern

## References

- https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- https://docs.prefect.io/v3/deploy/run-flows-in-local-processes

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
