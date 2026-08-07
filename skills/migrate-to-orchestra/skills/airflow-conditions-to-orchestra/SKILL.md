---
name: airflow-conditions-to-orchestra
description: "Use this skill when an Airflow DAG contains conditional execution logic: trigger_rule (all_done, one_failed, none_failed, one_success, none_skipped), BranchPythonOperator, ShortCircuitOperator, or LatestOnlyOperator. Triggers: any Airflow task with a non-default trigger_rule; any DAG using branching or short-circuit patterns; any task that should only run based on upstream status rather than simple success."
---

# Airflow Conditions → Orchestra Condition Expressions

## Overview

Airflow controls conditional task execution through `trigger_rule`, `BranchPythonOperator`, and `ShortCircuitOperator`. Orchestra replaces all of these with `condition:` — a string expression evaluated per task or task group using `${{ expression }}` syntax. The expression must evaluate to a truthy value for the task to run.

---

## `trigger_rule` Mapping

Airflow's `trigger_rule` controls when a task runs relative to its upstream tasks. In Orchestra, the equivalent is a `condition:` expression on the task or group.

| Airflow `trigger_rule` | Orchestra `condition:` | Notes |
|---|---|---|
| `all_success` (default) | `null` | Orchestra default — run only when all upstream succeed |
| `all_done` | _(see below)_ | Run when all upstream finish regardless of status |
| `all_failed` | `"${{ task_groups['upstream'].all().status == 'FAILED' }}"` | Rarely used |
| `one_success` | `"${{ task_groups['upstream'].any().status == 'SUCCEEDED' }}"` | |
| `one_failed` | `"${{ task_groups['upstream'].any().status == 'FAILED' }}"` | |
| `none_failed` | `"${{ task_groups['upstream'].all().status != 'FAILED' }}"` | Run unless something failed |
| `none_skipped` | `"${{ task_groups['upstream'].all().status != 'SKIPPED' }}"` | |
| `none_failed_min_one_success` | `"${{ task_groups['upstream'].any().status == 'SUCCEEDED' and task_groups['upstream'].all().status != 'FAILED' }}"` | |

### `all_done` — special case

`trigger_rule='all_done'` means "run after all upstream finish, regardless of their status." In Orchestra this is expressed by simply not adding a condition — but you need to ensure Orchestra doesn't gate on success. The closest pattern is relying on `depends_on` at the stage level with `treat_failure_as_warning: true` on upstream tasks:

```yaml
# Upstream task — mark failure as warning so downstream still runs
task-001:
  integration: AIRBYTE_CLOUD
  integration_job: AIRBYTE_CLOUD_JOB
  treat_failure_as_warning: true   # failure becomes WARNING, not FAILED
  ...

# Downstream task — no condition needed; runs after WARNING or SUCCESS
task-002:
  integration: DBT_CORE
  integration_job: DBT_CORE_EXECUTE
  depends_on:
    - task-001
  condition: null
  ...
```

Alternative if you don't want to change upstream: use `condition: "${{ True }}"` (always runs once deps are done).

---

## Condition Expression Reference

### Variable types available in expressions

| Variable | Type | Example |
|---|---|---|
| `task_groups['id'].all().status` | String | `== 'SUCCEEDED'` |
| `task_groups['id'].any().status` | String | `== 'FAILED'` |
| `inputs.my_input` | Any | `== 'prod'` |
| `ORCHESTRA.CURRENT_TIME` | Timestamp | `format_date(ORCHESTRA.CURRENT_TIME, '%H') == '04'` |
| `ORCHESTRA.PIPELINE_RUN_TASKS['task_id'].OUTPUTS['key']` | Any | `== 'expected_value'` |
| `matrix.input_name` | Any | Inside matrix task groups — see `airflow-dynamic-task-mapping-to-orchestra` for the full `matrix:` block schema (this is Orchestra's equivalent of Airflow's `.expand()`/dynamic task mapping) |

### Status values

`SUCCEEDED`, `FAILED`, `WARNING`, `SKIPPED`, `CANCELLED`, `RUNNING`, `CREATED`

### Built-in functions

| Function | Usage |
|---|---|
| `format_date(ts, fmt, tz?)` | `format_date(ORCHESTRA.CURRENT_TIME, '%d') == '01'` |
| `add_days(ts, delta)` | `add_days(ORCHESTRA.CURRENT_TIME, -1)` |
| `len(list)` | `len(inputs.items) > 0` |
| `int(value)` | `int(inputs.count) > 5` |
| `str(value)` | `str(inputs.flag) == 'True'` |

---

## `BranchPythonOperator` → Condition Expressions

Airflow's `BranchPythonOperator` calls a Python function that returns the `task_id` (or list of task_ids) to run next; other branches are skipped. In Orchestra, extract the branching logic into one of:

1. **`inputs:`-driven conditions** — if the branch decision is based on a runtime input value
2. **`condition:` expressions on each branch group** — each downstream group gets a mutually exclusive condition

### Pattern: input-driven branch

```python
# Airflow
def choose_branch(**context):
    env = context["params"]["env"]
    return "run_prod" if env == "prod" else "run_staging"

branch = BranchPythonOperator(
    task_id="choose_env",
    python_callable=choose_branch,
)
run_prod    = DbtRunOperator(task_id="run_prod", ...)
run_staging = DbtRunOperator(task_id="run_staging", ...)
branch >> [run_prod, run_staging]
```

```yaml
# Orchestra
inputs:
  env:
    type: string
    default: prod

pipeline:
  stage-prod:
    condition: "${{ inputs.env == 'prod' }}"
    depends_on: []
    tasks:
      run-prod:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        ...

  stage-staging:
    condition: "${{ inputs.env == 'staging' }}"
    depends_on: []
    tasks:
      run-staging:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        ...
```

### Pattern: output-driven branch

If the branch decision requires running a Python task first and using its output:

```yaml
pipeline:
  stage-decide:
    tasks:
      decide:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: 'python scripts/choose_branch.py'
          python_version: '3.12'
        # script sets Orchestra output: {"branch": "prod"}
        depends_on: []

  stage-prod:
    depends_on: [stage-decide]
    condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['decide'].OUTPUTS['branch'] == 'prod' }}"
    tasks:
      run-prod:
        ...

  stage-staging:
    depends_on: [stage-decide]
    condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['decide'].OUTPUTS['branch'] == 'staging' }}"
    tasks:
      run-staging:
        ...
```

The Python script must use the Orchestra SDK to set outputs — instantiate `OrchestraSDK` and call `.set_output()` on it, there's no bare `set_output()` function:
```python
import os
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))
client.set_output("branch", "prod")
```

---

## `ShortCircuitOperator` → Condition on Downstream

Airflow's `ShortCircuitOperator` runs a Python callable and skips all downstream tasks if it returns `False`. In Orchestra, extract the logic to a Python task that sets an output, then condition all downstream groups on that output.

```python
# Airflow
check = ShortCircuitOperator(
    task_id="check_new_data",
    python_callable=lambda: has_new_records(),
)
process = PythonOperator(task_id="process", ...)
check >> process
```

```yaml
# Orchestra
pipeline:
  stage-check:
    tasks:
      check-new-data:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: 'python scripts/check_new_data.py'
          python_version: '3.12'
          set_outputs: true   # required — without it, client.set_output() calls are silently ignored
        # script: OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY")).set_output("has_data", True/False)
        depends_on: []

  stage-process:
    depends_on: [stage-check]
    condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['check-new-data'].OUTPUTS['has_data'] == True }}"
    tasks:
      process:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: 'python scripts/process.py'
          python_version: '3.12'
```

---

## `LatestOnlyOperator` → Time-based Condition

`LatestOnlyOperator` skips downstream tasks on backfill runs (only runs on the most recent scheduled interval). Orchestra has no backfill, so this operator has no equivalent and should simply be dropped.

```yaml
# Drop LatestOnlyOperator entirely — Orchestra never backfills.
# Add a comment in the YAML:
# NOTE: LatestOnlyOperator dropped — Orchestra pipelines do not backfill.
```

---

## Trigger Rule Quick-Reference Card

```yaml
# all_success (default) — omit condition
condition: null

# all_done — upstream failures treated as warnings
# Set on upstream task:
treat_failure_as_warning: true
# Then downstream has no condition

# one_failed — run if any upstream group failed
condition: "${{ task_groups['upstream-stage'].any().status == 'FAILED' }}"

# none_failed — run unless something failed
condition: "${{ task_groups['upstream-stage'].all().status != 'FAILED' }}"

# input-driven branch
condition: "${{ inputs.run_mode == 'full' }}"

# output-driven branch
condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['decide-task'].OUTPUTS['proceed'] == True }}"

# always run (equivalent to all_done without treat_failure_as_warning)
condition: "${{ True }}"
```

---

## Gotchas

- **`condition:` is ANDed with group-level condition**: if a `TaskGroupModel` has a `condition:` and its child `TaskModel` also has one, both must be true for the task to run.
- **`trigger_rule` is per-task in Airflow but `condition:` is on the group in Orchestra**: put the condition on the `TaskGroupModel` (`stage-xxx:`) not on the individual task unless you need per-task granularity.
- **`BranchPythonOperator` has no direct equivalent**: the branching logic must either be driven by `inputs:` (static at trigger time) or by a preceding PYTHON task's output (dynamic at runtime).
- **`ShortCircuitOperator` requires Orchestra SDK in the script**: instantiate `OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))` and call `.set_output()` on it to expose its decision — `set_output` is a method on the client, not a bare importable function. If the original callable is simple (returns a boolean), extract it into a small wrapper script.
- **Skipped tasks propagate**: in Airflow, `trigger_rule='none_skipped'` guards against this. In Orchestra, if a group's condition is false, it is SKIPPED — and any group with `depends_on` pointing to it will also be evaluated; ensure downstream conditions account for SKIPPED status if needed.

## References

- Orchestra condition expressions: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Orchestra outputs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema#taskmodel
