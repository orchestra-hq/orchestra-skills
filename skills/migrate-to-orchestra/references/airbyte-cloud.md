# Orchestra Airbyte Cloud task — shared reference

Canonical Orchestra-side syntax for the `AIRBYTE_CLOUD` integration, shared by
`airbyte-cloud-airflow-to-orchestra`, `airbyte-cloud-dagster-to-orchestra`, and
`airbyte-cloud-prefect-to-orchestra`. Each of those skills covers the source-specific mapping
(which Airflow operator / Dagster resource / Prefect block produces the task, and how to recognize
one pointed at Airbyte Cloud in source); this file is the Orchestra side only — the part that's
identical regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the parameter mapping tables
(Airflow's `airbyte_conn_id`/`asynchronous` vs Dagster's `AirbyteCloudResource`/asset specs vs
Prefect's `AirbyteConnection` block), since the source vocabulary genuinely differs per
orchestrator; the per-source "how do I tell this is Airbyte Cloud and not Airbyte Server"
recognition test (Dagster's `AirbyteCloudResource` vs `AirbyteResource`, Prefect's
`api.airbyte.com` host check, Airflow's `airbyte_conn_id` target); the "Adding Alerts" sections,
which differ in depth per skill and point to sibling alert skills; and any sentence that names
another orchestrator or a sibling skill (e.g. `airbyte-server-*-to-orchestra`).

## AIRBYTE_CLOUD task schema

```yaml
pipeline:
  <stage-id>:
    tasks:
      <task-id>:
        integration: AIRBYTE_CLOUD
        integration_job: AIRBYTE_CLOUD_JOB   # the only job type for this integration
        name: <descriptive task name>
        connection: null  # MANUAL: create the Orchestra Airbyte Cloud connection, then replace with its name_XXXXX — see below
        parameters:
          connection_id: <airbyte-connection-uuid>   # Airbyte Cloud connection UUID — copy verbatim
          job_type: sync          # required: "sync" or "reset"
        depends_on: []
        condition: null
        tags: []
```

## job_type values

| Value | Behavior |
|---|---|
| `sync` | Normal sync — runs the connection per its configured Airbyte sync mode |
| `reset` | Full reload — resets/clears the connection's destination data instead of syncing |

`job_type` is required; omitting it fails schema validation.

## Orchestra polls internally

Orchestra's `AIRBYTE_CLOUD_JOB` task always waits for the sync (or reset) to finish before marking
the task complete — polling is built into the task itself. There is no separate sensor, wait step,
or async/polling flag to configure; if the source pattern used one (a sensor task, an
`asynchronous=True` flag, an explicit "wait for completion" call), it collapses into this single
Orchestra task.

## connection: field vs parameters.connection_id

These are two different identifiers and are easy to conflate:

- `connection:` — the **Orchestra connection** name (with its 5-digit suffix, e.g.
  `airbyte_cloud_prod_12345`). This is the credential Orchestra uses to call the Airbyte Cloud API.
  The source never shows this real name — it's assigned when the connection is created in the
  Orchestra UI. When you can't point to a real one, use `connection: null` with a `# MANUAL:`
  comment; never invent a plausible-looking name.
- `parameters.connection_id` — the **Airbyte-side** connection UUID (e.g.
  `a1b2c3d4-e5f6-7890-abcd-ef1234567890`) identifying which Airbyte connection to sync. Copy it
  verbatim from source; it is unrelated to the Orchestra connection name.

## AIRBYTE_CLOUD vs AIRBYTE_SERVER

`AIRBYTE_CLOUD` targets Airbyte's managed SaaS product. Self-hosted/open-source Airbyte
deployments use the separate `AIRBYTE_SERVER` integration instead — a different Orchestra
connection type and, in each source orchestrator, a different construct entirely. How to tell
which one a given piece of source code is targeting is source-specific and stays in each skill.

## References

- Orchestra Airbyte Cloud integration: https://docs.getorchestra.io/docs/integrations/airbyte_cloud
