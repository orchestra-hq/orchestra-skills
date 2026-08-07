---
name: airflow-dynamic-task-mapping-to-orchestra
description: "Use this skill when an Airflow DAG uses dynamic task mapping — task.expand(param=[...]), task.expand(param=XComArg(...)), task.partial(...).expand(...), or expand_kwargs() (Airflow 2.3+) — to create a variable number of task instances at runtime from a list, dict, or an upstream task's output. Triggers: any DAG using .expand(, .partial(, expand_kwargs(, map_index, or task mapping over a list of files/pages/config entries/API results. Orchestra's equivalent is a matrix task group (TaskGroupModel.matrix), not a plain loop — read this before converting any mapped Airflow task to Orchestra YAML."
---

# Airflow Dynamic Task Mapping → Orchestra Matrix Task Groups

## Overview

Airflow's dynamic task mapping (`task.expand()`, introduced 2.3+) creates N copies of a task at runtime from a list or dict — one task instance per file in a directory, per page of an API response, per row of a config table. The mapped values can be known statically at DAG-parse time (`expand(param=["a", "b", "c"])`) or come from an upstream task's return value via `XComArg` (`expand(param=some_task.output)`), in which case the fan-out count isn't known until that upstream task actually runs.

Orchestra's equivalent is a **matrix task group**: a `TaskGroupModel` (an entry under `pipeline:`) with a `matrix:` block. Each value in the matrix's input list creates one parallel execution of that entire stage — so a stage with a `matrix:` block behaves like Airflow's mapped-task fan-out, except the unit that repeats is **the whole stage**, not an individual task. Reference the current iteration's value in any task's `parameters:` via `${{ matrix.<input_name> }}`.

**Confirmed vs. inferred:** the `matrix`/`MatrixBlockModel` schema below was fetched directly from Orchestra's live JSONSchema on 2026-07-13 and is accurate as of that date. Unlike most of this skill set, though, there's no real customer DAG or `/api/convert` test run behind this skill yet — treat generated matrix YAML as needing extra review before trusting it in production (see the last Gotcha).

---

## MatrixBlockModel (confirmed schema)

```yaml
pipeline:
  <stage-id>:
    matrix:
      inputs:
        <input_name>: [value1, value2, value3]   # a static list, OR a string expression resolving to a list
      max_parallel: 4          # optional — cap concurrent iterations
      sequential: false        # optional — run iterations one at a time instead of in parallel
      continue_on_error: false # optional — keep running other iterations if one fails
    tasks:
      <task-id>:
        parameters:
          some_param: ${{ matrix.<input_name> }}   # reference this iteration's value
        ...
```

**`inputs` is currently limited to one input key** — confirmed in the schema's own field description. This matters: Airflow lets you `.expand()` on multiple parameters at once (computing their cross-product); Orchestra's matrix doesn't have a direct equivalent for that. See Gotchas for the workaround.

---

## Pattern Mapping

### 1. `task.expand(param=[static_list])` — list known at DAG-parse time

```python
# Airflow
@task
def process_file(filename: str):
    ...

process_file.expand(filename=["a.csv", "b.csv", "c.csv"])
```

```yaml
# Orchestra
pipeline:
  stage-process-file:
    matrix:
      inputs:
        filename: ["a.csv", "b.csv", "c.csv"]
    tasks:
      process-file:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: process_file
        connection: my_python_conn_12345
        parameters:
          command: 'python scripts/process_file.py'
          environment_variables: '{"FILENAME": "${{ matrix.filename }}"}'
        depends_on: []
    depends_on: []
```

### 2. `task.expand(param=XComArg(upstream_task))` — dynamic list from an upstream task's output

The harder case: the fan-out count isn't known until the upstream task runs. Orchestra's `matrix.inputs` accepts an expression resolving to a list, not just a literal — so point it at the upstream task's output. That upstream task must use `set_outputs: true` and return a JSON list (see `airflow-xcoms-to-orchestra` for the outputs mechanism itself).

```python
# Airflow
@task
def list_files() -> list[str]:
    return get_files_from_s3()

@task
def process_file(filename: str):
    ...

files = list_files()
process_file.expand(filename=files)
```

```yaml
# Orchestra
pipeline:
  stage-list-files:
    tasks:
      list-files:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: list_files
        connection: my_python_conn_12345
        parameters:
          command: 'python scripts/list_files.py'
          set_outputs: true   # required — see airflow-xcoms-to-orchestra
        depends_on: []

  stage-process-file:
    depends_on: [stage-list-files]
    matrix:
      inputs:
        filename: "${{ ORCHESTRA.PIPELINE_RUN_TASKS['list-files'].OUTPUTS['files'] }}"
    tasks:
      process-file:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: process_file
        connection: my_python_conn_12345
        parameters:
          command: 'python scripts/process_file.py'
          environment_variables: '{"FILENAME": "${{ matrix.filename }}"}'
        depends_on: []
```

```python
# scripts/list_files.py
import os
from orchestra_sdk.orchestra import OrchestraSDK

client = OrchestraSDK(api_key=os.environ.get("ORCHESTRA_API_KEY"))
files = get_files_from_s3()
client.set_output("files", files)   # must be a JSON-serialisable list
```

### 3. `task.partial(...).expand(...)` — shared static args + mapped args

Airflow's `.partial()` args are constant across every mapped instance; only the `.expand()` args vary. Orchestra has no partial/expand split — `.partial()` args are just ordinary static `parameters:`, alongside the one matrix-driven value:

```python
# Airflow
process_file.partial(bucket="my-bucket", dry_run=False).expand(filename=["a.csv", "b.csv"])
```

```yaml
# Orchestra
tasks:
  process-file:
    parameters:
      command: 'python scripts/process_file.py'
      environment_variables: '{"BUCKET": "my-bucket", "DRY_RUN": "false", "FILENAME": "${{ matrix.filename }}"}'
```

### 4. `max_active_tis_per_dag` / map-level concurrency → `matrix.max_parallel`

Airflow's cap on how many mapped task instances run concurrently maps directly to `matrix.max_parallel`.

```python
# Airflow — capped at 5 concurrent mapped instances
process_file.expand(filename=files)  # with max_active_tis_per_dag=5 set at the DAG or task level
```

```yaml
# Orchestra
matrix:
  inputs:
    filename: ...
  max_parallel: 5
```

---

## Cross-references

- **`airflow-conditions-to-orchestra`** mentions `matrix.input_name` in passing as a condition-expression variable available "inside matrix task groups" — that's the same construct documented here in full; the two skills describe one mechanism from two angles (condition expressions vs. the matrix block itself).
- **`airflow-xcoms-to-orchestra`** — required reading for pattern #2 above, since the mapped list comes from a task's `set_output()` call.

---

## Conversion Steps

1. Identify every `.expand()` / `.partial().expand()` / `expand_kwargs()` call; find the mapped parameter name(s) and where the mapped values come from (static list vs. upstream task output).
2. Static list → put it directly under `matrix.inputs.<name>`.
3. Upstream-task-driven list → confirm that task uses `set_outputs: true` and returns a JSON list, then reference it as the `matrix.inputs.<name>` expression.
4. Move any `.partial()` (shared, non-mapped) arguments into the task's regular `parameters:`, and reference the mapped value inline as `${{ matrix.<name> }}` wherever it's used.
5. Map `max_active_tis_per_dag` (or equivalent map-concurrency settings) to `matrix.max_parallel`.
6. Wire `depends_on:` from the matrix stage to whatever task produced the mapped list.

---

## Gotchas

- **Only one matrix input key is supported** (confirmed in the schema: "Currently limited to one input key"). Airflow DAGs that `.expand()` on multiple parameters at once (Airflow computes their cross-product) have no direct 1:1 equivalent. Workarounds: (a) if one of the mapped params is actually constant across the run, move it into `.partial()`-style static parameters instead of the matrix; (b) if a true cross-product is genuinely required, precompute it in a preceding Python task (e.g. `list(itertools.product(...))`, serialized as a single list of composite values) and expose that as the one matrix input, having the mapped task destructure the composite value in-script.
- **Matrix repeats the whole stage, not one task** — if the Airflow DAG only mapped one task among several unmapped siblings, give the mapped task its own dedicated stage rather than sharing a stage with tasks that shouldn't repeat.
- **`map_index` has no Orchestra equivalent** — Airflow exposes the numeric index of each mapped instance (`context["map_index"]`); Orchestra doesn't expose an iteration index. If task logic needs its own index (not just its value), it needs to derive whatever it needs from the value itself instead.
- **`expand_kwargs()`** (mapping over a list of kwarg dicts rather than a single param) uses the same matrix mechanism, but flag it as a manual review item — confirm every key is consistently present across the dicts, since Orchestra's matrix doesn't replicate Airflow's kwargs-merging semantics.
- **This corner of the schema is less battle-tested than most of this skill set** — confirmed against the live JSONSchema, but not yet validated against a real customer DAG or a live `/api/convert` run. Treat generated matrix YAML as needing extra review, and update this skill once a real dynamic-mapping conversion has been tried.

## References

- Orchestra pipeline schema (JSONSchema, no auth): https://orchestra-hq-public-production.s3.eu-west-2.amazonaws.com/jsonschemas/pipeline_model.json — `MatrixBlockModel` and `TaskGroupModel.matrix` confirmed directly against this on 2026-07-13
- Airflow dynamic task mapping: https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html
- Orchestra pipeline schema docs: https://docs.getorchestra.io/docs/core-concepts/pipelines/schema
