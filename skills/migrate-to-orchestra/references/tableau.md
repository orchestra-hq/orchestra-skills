# Orchestra Tableau task — shared reference

Canonical Orchestra-side syntax for the `TABLEAU_CLOUD` task shape, shared by `tableau-airflow-to-orchestra`,
`tableau-dagster-to-orchestra`, and `tableau-prefect-to-orchestra`. Each of those skills covers the
source-specific mapping (which Airflow operator / Dagster asset / Prefect TSC call produces the task, and how
to recognize that pattern in source); this file is the Orchestra side only — the part that's identical
regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the parameter mapping tables (the
source-construct column is inherently different per orchestrator); the "how do I recognize this pattern in
source" test (a different operator/resource/library shape per orchestrator); the Before/After worked examples
(paired one-to-one with source-specific code); the Conversion Steps / checklist (different shape and
granularity per skill — Airflow/Dagster use a numbered list, Prefect a checkbox list with extra steps); the
Gotchas sections (every bullet mixes in a source-specific comparison — e.g. "unlike Airflow where `site_id`
is a task parameter" or "Dagster specs may key by LUID" — so none of them are byte-identical enough to lift
out cleanly); and the Adding Alerts section (that's covered by the alert skills and `alerts.md`, not this
file).

## Task YAML shape

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: TABLEAU_CLOUD
        integration_job: TABLEAU_REFRESH_WORKBOOK
        name: <descriptive task name>
        connection: null  # MANUAL: create the Orchestra Tableau Cloud connection (server URL, site, PAT), then replace with its name_XXXXX
        parameters:
          project_name: <tableau-project-name>     # required
          workbook_name: <tableau-workbook-name>    # required
        depends_on: []
        condition: null
        tags: []
```

`project_name` and `workbook_name` are both required — Orchestra rejects the task without a project name
even in Tableau sites where the workbook name alone would be unambiguous.

**Never invent `connection:`.** The source never shows the real Orchestra connection name — it's
assigned when the connection is created in the Orchestra UI. When you can't point to a real one, use
`connection: null` with a `# MANUAL:` comment; never a plausible-looking invented name.

## Datasource extract refresh

To refresh a published datasource (extract) instead of a workbook, swap the job type and parameter:

```yaml
integration_job: TABLEAU_REFRESH_EXTRACT
parameters:
  project_name: <tableau-project-name>        # required
  datasource_name: <tableau-datasource-name>  # required, replaces workbook_name
```

## Connection and job completion

The Orchestra Tableau Cloud connection stores the server URL, site, and Personal Access Token (PAT) together
— site is not a per-task parameter, so route refreshes across multiple Tableau sites through one Orchestra
connection per site. Once triggered, the Orchestra task always waits for the refresh job to finish; there's
no separate polling step or sensor to configure.

## References

- Orchestra Tableau Cloud integration: https://docs.getorchestra.io/docs/integrations/tableau_cloud
