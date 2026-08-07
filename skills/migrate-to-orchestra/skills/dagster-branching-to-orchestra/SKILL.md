---
name: dagster-branching-to-orchestra
description: "Use this skill when a Dagster job/graph contains conditional execution logic: ops with multiple Out/branching outputs that are conditionally yielded, @op functions that decide which downstream op runs, DynamicOut fan-out used for branching, or conditional asset materialization (AutomationCondition / skip logic). Triggers: any Dagster op that conditionally yields one of several Outs, any graph that runs different downstream ops based on an upstream result, any asset whose execution is gated on a condition."
---

# Dagster Branching / Conditional Execution -> Orchestra Condition Expressions

## Overview

Dagster expresses conditional execution through ops with multiple `Out` definitions (`is_required=False`) that conditionally `yield Output(value, "branch_name")`. Downstream ops wired to a branch only run when that branch is yielded. There is no `trigger_rule` and no dedicated branch operator — branching is data-flow driven.

Orchestra replaces this with `condition:` — a string expression evaluated per task or task group using `${{ expression }}` syntax. The expression must be truthy for the task/stage to run. The conversion question is always: **is the branch decided at trigger time (use `inputs:`) or at runtime (use an upstream task's `OUTPUTS`)?**

---

## Mapping Dagster patterns

| Dagster pattern | Orchestra equivalent |
|---|---|
| Op with multiple `Out(is_required=False)`, conditional `yield Output(..., "name")` | Mutually-exclusive `condition:` on each downstream stage |
| Branch decided by config | `condition: "${{ inputs.x == ... }}"` |
| Branch decided by upstream computation | Upstream PYTHON/SQL task with `set_outputs: true`, downstream `condition:` on its `OUTPUTS` |
| "run regardless of upstream status" | `treat_failure_as_warning: true` upstream + no downstream condition |
| `DynamicOut` fan-out | Orchestra **matrix** block (parallel mapping) — not a condition |
| Asset skip when no new data (AutomationCondition) | `condition:` gated on an upstream output, or a sensor (see dagster-sensors-to-orchestra) |

---

## Condition Expression Reference

### Variables available

| Variable | Type | Example |
|---|---|---|
| `task_groups['id'].all().status` | String | `== 'SUCCEEDED'` |
| `task_groups['id'].any().status` | String | `== 'FAILED'` |
| `inputs.my_input` | Any | `== 'prod'` |
| `ORCHESTRA.CURRENT_TIME` | Timestamp | `format_date(ORCHESTRA.CURRENT_TIME, '%H') == '04'` |
| `ORCHESTRA.PIPELINE_RUN_TASKS['task_id'].OUTPUTS['key']` | Any | `== 'expected_value'` |
| `matrix.input_name` | Any | Inside matrix task groups |

### Status values

`SUCCEEDED`, `FAILED`, `WARNING`, `SKIPPED`, `CANCELLED`, `RUNNING`, `CREATED`

### Built-in functions

`format_date(ts, fmt, tz?)`, `add_days(ts, delta)`, `len(list)`, `int(value)`, `str(value)`

---

## Pattern: config-driven branch (decided at trigger time)

```python
# Dagster
from dagster import op, job, Out, Output, Config

class EnvConfig(Config):
    env: str = "prod"

@op(out={"prod": Out(is_required=False), "staging": Out(is_required=False)})
def choose_env(config: EnvConfig):
    if config.env == "prod":
        yield Output(True, "prod")
    else:
        yield Output(True, "staging")

@op
def run_prod(_): ...
@op
def run_staging(_): ...

@job
def branching_job():
    prod, staging = choose_env()
    run_prod(prod)
    run_staging(staging)
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
        # ...

  stage-staging:
    condition: "${{ inputs.env == 'staging' }}"
    depends_on: []
    tasks:
      run-staging:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        # ...
```

---

## Pattern: runtime-driven branch (decided by an upstream op)

If the branch decision requires computation (e.g. a row count), run that logic as a task that sets an output, then condition downstream stages on it.

```python
# Dagster
@op(out={"has_data": Out(), "empty": Out()})
def check_new_data(context):
    count = get_count()
    if count > 0:
        yield Output(count, "has_data")
    else:
        yield Output(count, "empty")
```

```yaml
# Orchestra
pipeline:
  stage-decide:
    tasks:
      decide:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: 'python scripts/check_new_data.py'
          python_version: '3.12'
          set_outputs: true
        # script: OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY")).set_output("has_data", count > 0) — see python-dagster-to-orchestra for the full client setup
        depends_on: []

  stage-process:
    depends_on: [stage-decide]
    condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['decide'].OUTPUTS['has_data'] == True }}"
    tasks:
      process:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: 'python scripts/process.py'
          python_version: '3.12'
```

---

## DynamicOut is NOT a condition

`DynamicOut` produces N parallel copies of a downstream op (fan-out), not a branch. This maps to an Orchestra **matrix** block on the TaskGroupModel, where each matrix value runs the task once. Only the conditional-skip aspect of a graph maps to `condition:`.

---

## Quick-Reference Card

```yaml
# default (all upstream succeed) — omit
condition: null

# always run once deps done
treat_failure_as_warning: true   # on upstream
# downstream: no condition

# input branch
condition: "${{ inputs.run_mode == 'full' }}"

# output branch
condition: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['decide'].OUTPUTS['proceed'] == True }}"
```

---

## Gotchas

- **`condition:` is ANDed with the group-level condition** — if both a stage and its child task have conditions, both must be true.
- **Conditional `Out`s map to mutually-exclusive stage conditions** — there is no 'branch op' to port; model each branch as its own stage with a condition.
- **Trigger-time vs runtime** — config-driven choices become `inputs:`; computed choices become an upstream task `OUTPUTS` reference.
- **`DynamicOut` is fan-out, not branching** — map to an Orchestra matrix block.
- **AutomationCondition / eager asset materialization** — usually closer to sensors/`trigger_events`; only model as a condition when it is a simple skip-on-no-data gate.
- **Skipped stages propagate** — a false condition SKIPS the stage; downstream stages must account for SKIPPED status.

## References

- Orchestra condition expressions: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
- Orchestra outputs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema#taskmodel
- Dagster conditional branching: https://docs.dagster.io/concepts/ops-jobs-graphs/graphs#conditional-branching
- Dagster dynamic mapping: https://docs.dagster.io/concepts/ops-jobs-graphs/dynamic-graphs
