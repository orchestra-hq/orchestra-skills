# Orchestra Airbyte Server task — shared reference

Canonical Orchestra-side syntax for the `AIRBYTE_SERVER` integration task, shared by
`airbyte-server-airflow-to-orchestra`, `airbyte-server-dagster-to-orchestra`, and
`airbyte-server-prefect-to-orchestra`. Each of those skills covers the source-specific mapping
(which Airflow/Dagster/Prefect construct produces which field, and how to recognize a self-hosted
Airbyte target in that orchestrator's code); this file is the Orchestra side only — the part
that's identical regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the parameter mapping tables
(they pair source-specific constructs — `AirbyteTriggerSyncOperator`/`AirbyteSensor` kwargs,
`AirbyteResource(host=, port=)` + `build_airbyte_assets`, `AirbyteConnection` blocks — with
Orchestra fields, and that source vocabulary genuinely differs per orchestrator); the per-source
"how do I tell this is self-hosted, not Cloud" recognition test (a different code shape in each
orchestrator); any sentence naming another orchestrator or a sibling skill (e.g. "see
`airbyte-cloud-dagster-to-orchestra`"); the full Before/After worked examples (each pairs
source-specific code with its own Orchestra YAML); and the Conversion Steps/Checklist and Gotchas
sections, since none of those are byte-identical across all three skills — each mixes in a
genuine per-source distinction.

## Task shape

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: AIRBYTE_SERVER
        integration_job: AIRBYTE_SERVER_JOB
        name: <descriptive task name>
        connection: null  # MANUAL: create the Orchestra Airbyte Server connection (host + API credentials), then replace with its name_XXXXX
        parameters:
          connection_id: <airbyte-connection-uuid>   # Airbyte's own connection UUID, copied verbatim
          job_type: sync                              # required — "sync" or "reset"
        depends_on: []
        condition: null
        tags: []
```

`integration_job` is always `AIRBYTE_SERVER_JOB` — there is only one job type for the Airbyte
Server integration.

## Fields

- **`connection:`** — the Orchestra connection name (Settings -> Connections, *Airbyte Server*
  type), which stores the server's host URL and API credentials. This is an Orchestra-side name
  (e.g. `airbyte_server_prod_12345`) and is **not** the same value as `parameters.connection_id`.
  The source never shows this real name — it's assigned when the connection is created in the
  Orchestra UI. When you can't point to a real one, use `connection: null` with a `# MANUAL:`
  comment; never invent a plausible-looking name.
- **`parameters.connection_id`** — Airbyte's own connection UUID (the sync pairing configured
  inside Airbyte itself, between a source and a destination). Copy it verbatim from the source
  code/config — never invent it.
- **`parameters.job_type`** — required. `sync` runs a normal/incremental sync; `reset` fully
  reloads the connection (clears and resyncs all data). Omitting it fails validation.
- **`depends_on:` / `condition:` / `tags:`** — standard TaskModel scaffolding, populated the same
  way as for any other Orchestra task type.

## References

- Orchestra Airbyte Server integration: https://docs.getorchestra.io/docs/integrations/airbyte_server
