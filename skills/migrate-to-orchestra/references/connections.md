# Orchestra connections — shared reference

Canonical Orchestra-side syntax for the `connection:` field, shared by `airflow-connections-to-orchestra`,
`dagster-connections-to-orchestra`, and `prefect-connections-to-orchestra`. Each of those skills covers the
source-specific mapping (which Airflow conn_id / Dagster resource / Prefect block produces which Orchestra
connection type, and how to recognize one in source); this file is the Orchestra side only — the part
that's identical regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the connection-type mapping tables
(Databases / Data Integration / Notifications / Infrastructure), since the source vocabulary genuinely
differs per orchestrator; the per-source "how do I tell there's no credential in this task" recognition
test; and any sentence that names the other two orchestrators or a sibling skill.

## Connection name format

```yaml
connection: my_snowflake_12345   # format: descriptive-name_XXXXX (5-digit suffix from UI)
```

The 5-digit suffix is assigned by Orchestra when the connection is created — copy it from the UI; never
invent it.

## No credential in source → `connection: null`

If a task genuinely has no distinct credential behind it — pure computation, no external client, no
secrets — don't invent a connection name or a fake env var placeholder just to fill the field:

```yaml
connection: null   # no distinct credential in the source; Orchestra uses the workspace default for this integration
```

Only set a specific `name_XXXXX` or `${{ ENV.VAR }}` when the source code actually references a distinct
credential.

## Don't duplicate connection-level scope into task parameters

This extends to task parameters that duplicate connection-level scope, too — e.g. Airbyte's optional
`parameters.workspace_id` (metadata only; the connection itself already scopes which Airbyte workspace is
used), or any other parameter whose value is also stored on the Orchestra connection itself. If the source
code just reads the same single value everywhere (one env var, one resource/block-level config field)
rather than genuinely varying it per task, leave that parameter `null`/omitted and let the connection's own
configured value apply. Only carry an explicit value through (literal, input, or `${{ ENV.VAR }}`) when a
specific task truly needs to override it.

**Not every integration has a task-level override at all.** Some integrations scope a resource (a
workspace, a site) entirely on the connection with no matching task parameter to null out — e.g. Power BI:
there is no `workspace_id` on either `POWER_BI_REFRESH_DATASET` or `POWER_BI_REFRESH_DATAFLOW`
(`additionalProperties: false` on both — see `skills/orchestra/references/orchestra/schemas/pipeline_schema.json`).
If the source targets more than one such scope, that requires a separate Orchestra connection per scope, not
a task-level parameter. Check the actual parameter model for the integration in question before assuming an
override field exists.

## Environment-specific connections

```yaml
connection: ${{ ENV.SNOWFLAKE_CONNECTION_NAME }}
```

Set `SNOWFLAKE_CONNECTION_NAME=my_snowflake_12345` in Orchestra's environment settings.

The same pattern applies inside a full task definition:

```yaml
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        connection: ${{ ENV.SNOWFLAKE_CONN }}
        parameters:
          statement: 'SELECT * FROM orders LIMIT 10'
```

In Orchestra: Settings -> Environments -> set `SNOWFLAKE_CONN=snowflake_dev_11111` in dev and
`snowflake_prod_22222` in prod.

## Secrets handling

**Never hardcode credentials in YAML.** All credentials go in the Orchestra connection — the YAML
references only the connection name.

```yaml
# Correct
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_QUERY
  connection: snowflake_prod_12345
  parameters:
    statement: 'SELECT 1'
```

## References

- Orchestra connections: https://docs.getorchestra.io/docs/core-concepts/connections
- Orchestra environments: https://docs.getorchestra.io/docs/core-concepts/environments
