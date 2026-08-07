---
name: prefect-conditions-to-orchestra
description: "Use this skill when a Prefect flow contains conditional execution logic: tasks that only run based on the result of upstream tasks, if/else branches driven by task return values, allow_failure=True patterns, or conditional .submit() calls. Triggers: any Prefect flow with if/else branching on task outputs, any task called conditionally, any use of Prefect states to control downstream execution."
---

## Overview

This skill converts Prefect conditional execution patterns into Orchestra `condition:` expressions. It covers input-driven branches, runtime output-driven branches, `allow_failure` patterns, and always-run tasks.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| Default (no condition) | `condition: null` | Orchestra default |
| Input-driven branch | `condition: "${{ inputs.flag == true }}"` | Decision known at trigger time |
| `result = task.submit(); if result.result():` | upstream PYTHON task with `set_outputs: true` + downstream condition | Runtime decision via outputs |
| `allow_failure=True` | `treat_failure_as_warning: true` on upstream task | Downstream continues regardless |
| Skip if no data | `condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['id'].OUTPUTS['key'] > 0 }}"` | |
| Always run | `condition: "${{ True }}"` | Runs even if upstream failed |
| `.submit(wait_for=[other])` | `depends_on: [other-task-id]` | Dependency without data passing |
| `.map()` over list | `matrix:` block on TaskGroupModel | See `prefect-data-passing-to-orchestra` |

## Orchestra YAML Structure

```yaml
version: v1
name: conditional-pipeline
pipeline:
  stage-check:
    tasks:
      task-check-new-data:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        parameters:
          statement: "SELECT COUNT(*) AS row_count FROM staging.new_records"
        depends_on: []
        condition: null
        tags: []
    depends_on: []

  stage-process:
    tasks:
      task-process-records:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: python scripts/process_records.py
        depends_on: []
        condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-check-new-data'].OUTPUTS['row_count'] > 0 }}"
        tags: []
    depends_on:
      - stage-check

  stage-skip:
    tasks:
      task-log-skip:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: python scripts/log_skip.py
        depends_on: []
        condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-check-new-data'].OUTPUTS['row_count'] == 0 }}"
        tags: []
    depends_on:
      - stage-check
```

## Conversion Steps

- [ ] Identify all conditional branches in the Prefect flow
- [ ] Classify each branch: input-driven (known at trigger) vs. output-driven (known at runtime)
- [ ] For input-driven branches: write `condition: "${{ inputs.param == value }}"` directly
- [ ] For output-driven branches: ensure upstream task exposes outputs; write `condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-id'].OUTPUTS['key'] op value }}"`
- [ ] Replace `allow_failure=True` with `treat_failure_as_warning: true` on the upstream task
- [ ] Replace `.submit(wait_for=[...])` with `depends_on: [...]` on the downstream task/group
- [ ] Flag `.map()` calls for `prefect-data-passing-to-orchestra` (matrix pattern)

## Before / After Example

### Prefect (before)

```python
from prefect import flow, task

@task
def check_new_data() -> bool:
    count = run_query("SELECT COUNT(*) FROM staging.new_records")
    return count > 0

@task
def process_records():
    ...

@task
def log_skip():
    ...

@flow
def conditional_flow():
    has_data = check_new_data.submit()
    if has_data.result():
        process_records.submit(wait_for=[has_data])
    else:
        log_skip.submit(wait_for=[has_data])
```

### Orchestra YAML (after)

```yaml
version: v1
name: conditional-flow
pipeline:
  stage-check:
    tasks:
      task-check-new-data:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        parameters:
          statement: "SELECT COUNT(*) AS row_count FROM staging.new_records"
        depends_on: []
        condition: null
        tags: []
    depends_on: []

  stage-process:
    tasks:
      task-process-records:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: python scripts/process_records.py
        depends_on: []
        condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-check-new-data'].OUTPUTS['row_count'] > 0 }}"
        tags: []
    depends_on:
      - stage-check

  stage-skip:
    tasks:
      task-log-skip:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: python scripts/log_skip.py
        depends_on: []
        condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-check-new-data'].OUTPUTS['row_count'] == 0 }}"
        tags: []
    depends_on:
      - stage-check
```

## Gotchas

- Complex Python runtime branching requires an upstream PYTHON task whose script instantiates `OrchestraSDK` and calls `client.set_output()` to expose values — see `prefect-data-passing-to-orchestra` for the client setup
- `.submit(wait_for=[...])` is a dependency pattern, not a data-passing pattern — use `depends_on:`
- `allow_failure=True` → `treat_failure_as_warning: true` on the upstream task (downstream continues)
- `.map()` over a list is a matrix pattern — see `prefect-data-passing-to-orchestra`
- Task-level `condition` is evaluated after `depends_on` is satisfied; a skipped task does not fail the pipeline
- `${{ True }}` as a condition means always run, even if an upstream task failed

## References

- [Orchestra pipeline schema](https://docs.getorchestra.io/docs/core-concepts/pipelines/schema)
- [Prefect flows](https://docs.prefect.io/v3/develop/write-flows)

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
