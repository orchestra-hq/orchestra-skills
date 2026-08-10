# Orchestra Python task — shared reference

Canonical Orchestra-side syntax for the `PYTHON` / `PYTHON_EXECUTE_SCRIPT` task, shared by
`python-airflow-to-orchestra`, `python-dagster-to-orchestra`, and `python-prefect-to-orchestra`.
Each of those skills covers the source-specific mapping (how to recognize a plain Python
task in Airflow/Dagster/Prefect source, and how that source's specific constructs — op
resources, `Config`, Prefect blocks, `op_kwargs`, TaskFlow, etc. — map onto Orchestra fields);
this file is the Orchestra side only — the part that's identical regardless of source
orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the parameter-mapping
tables (source vocabulary genuinely differs per orchestrator); the per-source "how do I
recognize this is a plain Python task and not a dedicated integration" test; the "check it
isn't actually a Slack task" carve-out and its sibling-skill pointers
(`slack-airflow-to-orchestra` / `slack-dagster-to-orchestra` / `slack-prefect-to-orchestra`);
output/data-passing mechanics beyond the substitution-syntax gotcha below, which live in
`airflow-xcoms-to-orchestra` / `dagster-io-managers-to-orchestra` /
`prefect-data-passing-to-orchestra`; and the `alerts:` block, which is covered by
[`alerts.md`](alerts.md), not this file.

## INLINE vs GIT execution modes

Orchestra's Python integration (**Execute Script**) has two modes:

- `source: INLINE` — runs code pasted directly into `parameters.code`.
- `source: GIT` — runs a file checked out from a Git repo, referenced via `parameters.command`.

**Default to `INLINE`.** A source task's Python body already lives inline wherever it's
defined (a DAG file, an op/asset function, a flow's `@task`) — pasting that body into
`parameters.code` is a direct match, needs no Git repo or connection wiring, and skips a
whole conversion step. Only reach for `GIT` when the source task itself checks out and runs
a script that already lives in a separate Git repo — not by default just because Orchestra
supports it.

## Task YAML skeleton

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: <task name>
        connection: null                          # usually null for INLINE — set only if the code needs a specific connection's secrets
        parameters:
          source: INLINE                           # default — code already lives in the source task, no Git repo involved
          code: |
            <task body, copied verbatim>
          build_command: 'pip install pandas'      # optional — only for non-stdlib imports
          python_version: '3.12'
        depends_on: []
        condition: null
        tags: []
```

## python_version is a fixed enum

`parameters.python_version` only accepts `'3.11'` or `'3.12'` (live-verified; any other value is
rejected). If the source pins a different Python version, round to the nearest supported one rather
than copying the source value verbatim.

## environment_variables is a JSON string

`parameters.environment_variables` is a single string field holding JSON, not a nested YAML
mapping — e.g. `'{"KEY": "value"}'`, read in `code` with `os.environ["KEY"]`. A YAML mapping
under that key is invalid.

## connection: null is the default

`connection: null` is the norm for `INLINE` tasks with no external credentials. Only set a
specific connection if the code needs secrets injected from one (e.g. a boto3/Snowflake
client reading connection-provided env vars) — never invent a placeholder like
`${{ ENV.PYTHON_CONNECTION }}` just to fill the field.

## Secrets handling

Never hardcode credentials in `code` or YAML. If the code needs secrets, use an Orchestra
connection's injected environment variables instead.

## GIT mode for real Git-backed scripts

`source: GIT` still exists for genuine Git-backed scripts: if the source task checks out and
runs a script from a separate repo, use `GIT` + `parameters.command` (referencing the script
by its relative path), and create/verify a Python connection pointing at that repo (URL,
branch, credentials). Orchestra supports sparse checkout for large monorepos, configurable on
the connection.

## Consuming a JSON-shaped upstream output

When `code` reads an upstream output via `${{ ...OUTPUTS[...] }}`, wrap the substitution in
Python **triple-quotes** before calling `json.loads()`, not single/double quotes — the
substitution is raw text with no escaping, so a single/double-quoted string breaks the moment
the JSON value itself contains a quote character.

```python
import json
data = json.loads("""${{ TASKS.upstream_task.OUTPUTS.result }}""")
```

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/python
- Orchestra Execute Script: https://docs.getorchestra.io/docs/integrations/utility/python/execute-script/
