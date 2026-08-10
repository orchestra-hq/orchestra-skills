# Orchestra Fivetran task — shared reference

Canonical Orchestra-side syntax for the `FIVETRAN` task, shared by `fivetran-airflow-to-orchestra`,
`fivetran-dagster-to-orchestra`, and `fivetran-prefect-to-orchestra`. Each of those skills covers the
source-specific mapping (which Airflow/Dagster/Prefect Fivetran construct produces which Orchestra
field, and how to recognize one in source); this file is the Orchestra side only — the part that's
identical regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the parameter-mapping tables
(they map a specific `FivetranOperator`/`FivetranResource`/`FivetranConnector` mechanism to this
shape, which is genuinely source-specific vocabulary); the "how do I recognize this pattern in
source" test for each orchestrator; the Before/After worked examples (each is paired with that
skill's own "before" source snippet); and the Conversion Steps/Checklist and Gotchas sections, since
their wording and specifics differ per source and are not byte-identical across all three skills.
The `alerts:` block shown in each skill's "Adding Alerts" section is also out of scope here — that's
already covered by the shared [`alerts.md`](alerts.md) reference, not this one.

The shape below (`FivetranParametersModel` / `IntegrationJobsEnum`) is live-verified against the
real Orchestra backend via the `validate_pipeline` MCP tool — not a cached schema file or docs-page
rendering, both of which can drift or be mis-rendered. Re-verify the same way if this ever needs
updating.

## FIVETRAN task schema

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: FIVETRAN
        integration_job: FIVETRAN_SYNC_ALL
        name: <task-name>
        connection: <orchestra-fivetran-connection-name>
        parameters:
          connector_id: <fivetran-connector-id>
        depends_on: []
        condition: null
        tags: []
```

`FIVETRAN_SYNC_ALL` is the only `integration_job` value for the `FIVETRAN` integration — there is no
separate "trigger" vs. "wait" job type. A single task always triggers the connector sync and blocks
until it finishes; there is no parameter to fire-and-forget instead.

## References

- Orchestra Fivetran docs: https://docs.getorchestra.io/docs/integrations/fivetran
