# Orchestra pipeline YAML authoring

Schema reference for creating and editing Orchestra pipeline definitions (`version: v1`).
Use with the `create-orchestra-pipeline` skill and the tooling in [Validation](#validation).

Official docs: [docs.getorchestra.io](https://docs.getorchestra.io).

## File layout

- Default directory in Git-backed repos: `orchestra/<descriptive-name>.yml`
- Orchestra accepts `.oml`, `.yaml` and `.yml` definitions — match the repo, and see [OML](#oml-oml) below
- If the repo uses another convention (`pipelines/`, `.orchestra/`), match existing files
- Derive a short kebab-case filename from the pipeline purpose when the user does not specify one

Before writing, list existing pipeline YAML in the repo and read one or two files that use
similar integrations (task group IDs, connection naming, schedules).

## Git-backed pipelines: how a change goes live

A committed file is not automatically a deployed pipeline. Orchestra only picks a change up
when it lands on **that pipeline's default branch**: the provider sends a push webhook,
Orchestra matches the changed files to pipelines, then fetches, validates and updates the
pipeline ([GitBridge sync](https://docs.getorchestra.io/docs/git-control-and-ci-cd/supported-git-providers/github#how-does-gitbridge-sync-pipeline-files-from-github)).

- **A push to any other branch changes nothing.** The live pipeline keeps the default
  branch's definition until the PR merges — which is what makes a branch run a safe way to
  prove a change before review.
- **A run against a branch uses that branch's version of the file**, so `start_pipeline`
  with `branch=<fix-branch>` exercises the committed-but-unmerged definition.
- **Saving in the Orchestra editor commits for you**, through the editing user's own Git
  connection, to the working branch (created from the default branch if it is new), so the
  commit is attributed to that person. The workspace connection only ever reads
  ([what happens when you save](https://docs.getorchestra.io/docs/git-control-and-ci-cd#what-happens-when-you-save-a-git-backed-pipeline)).
- **Deleting a Git-backed pipeline is two steps.** Deleting it in Orchestra leaves the
  definition file in the repository; removing the file through normal git-flow is a separate
  action ([Git control](https://docs.getorchestra.io/docs/git-control-and-ci-cd/git-control)).
- **Which provider the repo is on doesn't change any of the above.** GitBridge works the same
  across [the supported providers](https://docs.getorchestra.io/docs/git-control-and-ci-cd/supported-git-providers):
  GitHub, GitHub Enterprise Cloud, GitLab, Azure DevOps and Bitbucket. A repo on a **GHE.com
  tenant** is a supported home for Git-backed pipelines — the workspace connects through a
  GitHub App that the customer's own organisation owns on that tenant, one App per GitHub
  organisation, so setup needs an owner of that organisation rather than only an Orchestra
  admin ([Connect GitHub Enterprise Cloud](https://docs.getorchestra.io/docs/git-control-and-ci-cd/supported-git-providers/github-enterprise)).
  **GitHub Enterprise *Server* is not supported** — don't plan a Git-backed migration around a
  self-hosted GHES instance. If the tenant IP-restricts access, Orchestra's IPs have to be on
  the allow list before any of this syncs.
- **Disconnecting the workspace Git connection is not a local undo.** For GitHub, every
  workspace shares one App installation, and disconnecting in Orchestra uninstalls that App —
  the same blast radius as removing it from the GitHub organisation, so it takes Git-backed
  pipelines offline in **every** workspace on that installation, not just this one. Treat it as
  an org-wide change and confirm before suggesting it
  ([Connect GitHub](https://docs.getorchestra.io/docs/git-control-and-ci-cd/supported-git-providers/github)).

## Document structure

```yaml
version: v1
name: '<descriptive name> #tag1 #tag2'
pipeline:
  <task_group_id>:           # descriptive name or uuid4
    tasks:
      <task_id>:             # descriptive name or uuid4
        integration: <INTEGRATION>
        integration_job: <JOB_TYPE>
        parameters:
          # integration-specific params
        depends_on: []       # other task IDs within this group
        name: <Human readable task name>
        # tags: omit entirely if no tags — do NOT include tags: []
        connection: <connection_id or ${{ ENV.VAR }}>  # omit if not needed
    depends_on: []           # list of task_group_ids this group waits for
    name: '<Stage Name>'
```

### Required fields

- `version: v1`
- `name:` — include `#tags` for discoverability when useful
- Each task: `integration`, `integration_job`, `parameters`, `depends_on`, `name`
- Omit `tags` when unused — never write `tags: []`

## Integration reference

| Integration | integration_job | Key parameters |
|---|---|---|
| FIVETRAN | FIVETRAN_SYNC_ALL | `connector_id` |
| DBT_CORE | DBT_CORE_EXECUTE | `commands`, `package_manager` (PIP\|POETRY\|UV), `python_version` (3.11\|3.12\|3.13, default 3.12), `project_dir`, `shallow_clone_dirs` |
| PYTHON | PYTHON_EXECUTE_SCRIPT | `command`, `package_manager` (PIP\|POETRY\|UV), `python_version` (3.11\|3.12\|3.13\|3.14, default 3.12), `build_command`, `source: GIT`, `project_dir`, `environment_variables`, `set_outputs` |
| SNOWFLAKE | SNOWFLAKE_RUN_QUERY | `statement`, `role`, `database`, `schema` |
| SNOWFLAKE | SNOWFLAKE_RUN_TEST | `statement`, `error_threshold_expression`, `warn_threshold_expression` |
| GCP_BIG_QUERY | GCP_BQ_RUN_QUERY_JOB | `query` |
| GCP_CLOUD_RUN | GCP_CLOUD_RUN_EXECUTE_JOB | `job_name` |
| TABLEAU_CLOUD | TABLEAU_REFRESH_EXTRACT | `project_name`, `datasource_name` |
| POWER_BI | POWER_BI_REFRESH_DATASET | `dataset_id` |
| HTTP | HTTP_REQUEST | `path`, `method`, `body`, `custom_headers` |
| MARIADB | MARIADB_RUN_QUERY | `statement` |
| GCP_CLOUD_STORAGE | GCP_CLOUD_STORAGE_GET_FILE / GCP_CLOUD_STORAGE_PUT_FILE | `bucket`, file paths |
| ORCHESTRA | APPROVAL | `message_integration`, `message_connection_id`, `message_destination` |
| ORCHESTRA | RUN_AGENT | `agent_id`, `prompt`, `set_outputs`, `model_id`, `effort`, `llm_integration`, `llm_connection_id` |
| OPEN_AI | OPEN_AI_CHAT | `prompt`, `model`, `context`, `instructions`, `set_outputs` |
| AWS_LAMBDA | AWS_LAMBDA_EXECUTE_ASYNC_FUNCTION | `function_name` |
| AWS_BATCH | AWS_BATCH_SUBMIT_JOB | `job_queue`, `job_definition`, `job_name`, `parameters`, `container_overrides`, `timeout_seconds` |
| ESTUARY | ESTUARY_CHECK_FLOW | `task`, `error_threshold`, `warn_threshold` |
| LIGHTDASH | LIGHTDASH_REFRESH_DASHBOARD | `dashboard_id`, `invalidate_cache` |

Parameters that hold a JSON object — `body` and `custom_headers` on HTTP, `arguments` on AWS
Glue, `environment_variables` on Python and dbt Core — are **strings**, not YAML mappings.
Write them quoted (`environment_variables: '{}'`, `body: '{"id": 1}'`). A bare `{}` or a nested
YAML block is the wrong type and the schema rejects it; this is an easy one to get wrong when
porting a dict straight out of Airflow or Dagster, where it really is a mapping.

AWS Batch is the exception: `parameters` and `container_overrides` on `AWS_BATCH_SUBMIT_JOB`
really are YAML mappings, not quoted strings. Check the schema for the specific parameter
rather than applying either habit across the board.

`AWS_BATCH_SUBMIT_JOB` submits one job to a queue and waits for it. Single-container jobs on
EC2 or Fargate only — array jobs and multi-node parallel jobs aren't supported. A
`job_definition` without `:<revision>` resolves to the latest active revision. `timeout_seconds`
is a per-attempt limit with a minimum of 60, enforced by Batch. A task that hits its own
`configuration.timeout` fails **without terminating the job** — a running job keeps running and
a queued one can still start later — so bound queue waits with a job state time limit action on
the queue rather than relying on the task timeout; cancelling the task does terminate the job.
Orchestra injects `ORCHESTRA_ACCOUNT_ID`, `ORCHESTRA_PIPELINE_RUN_ID`, `ORCHESTRA_TASK_RUN_ID`
and `ORCHESTRA_WEBHOOK_URL` into the container's environment, so `container_overrides.environment`
adds to that rather than replacing it. The integration is in beta and may not be enabled on an
account. See [AWS Batch](https://docs.getorchestra.io/docs/integrations/aws_batch) and
[Submit Job](https://docs.getorchestra.io/docs/integrations/aws_batch/aws_batch_submit_job).

`AWS_SECRETS_MANAGER` and `AZURE_KEY_VAULT` are in `IntegrationsEnum` but have no
`integration_job`: they are credential stores a connection reads its own credentials from, not
task types. There is no task that fetches a secret mid-run for a later task to consume, so a
pipeline that needs one is really a connection that should name the store as its **Credential
Store**. Both are in beta. See [Azure Key Vault](https://docs.getorchestra.io/docs/integrations/azure_key_vault)
and [AWS Secrets Manager](https://docs.getorchestra.io/docs/integrations/aws_secrets_manager).

`RUN_AGENT` creates an agent session from `prompt` and waits for it. Only `agent_id` and
`prompt` are required: `model_id`, `effort`, `llm_integration` and `llm_connection_id` each fall
back to the agent's own setting when omitted, so leave them out unless the run needs to differ
from the agent. `llm_connection_id` names a connection the account already holds — naming one it
doesn't fails the run — and never an API key written into the YAML. Nothing can prompt the
session again once it is created, so everything the agent needs goes in that first `prompt`. See
[Run Agent](https://docs.getorchestra.io/docs/integrations/orchestra/run_agent).

## Connection format

```yaml
connection: my_snowflake_12345   # descriptive-name_XXXXX — 5-digit suffix assigned by Orchestra
connection: ${{ ENV.SNOWFLAKE_CONNECTION_NAME }}   # environment-specific, set per Environment in the UI
connection: null                 # no distinct connection needed — Orchestra uses the workspace default
```

`null` is valid and often preferable when nothing in the source distinguishes a specific
credential — never invent a placeholder suffix or a fake `${{ ENV.VAR }}` just to fill the field.
The same rule applies to any parameter that duplicates connection-level scope (e.g. a Power BI
`workspace_id`): leave it unset and let the connection's own configured value apply unless a task
genuinely needs to override it. If a required value truly can't be determined statically (an ID
only resolvable by calling a live API), use a placeholder and flag it with a `# MANUAL:` comment
rather than shipping a fabricated literal or GUID.

### Repo-backed connections: Git connection or token

Python, dbt Core and Bauplan connections point at a Git repository, and now choose **how** they
reach it: the workspace's **Git connection** (the default) or a **Token**. A personal access token
is only required on the token path, so a workspace that already connects to that provider needs no
new secret to add one of these connections — check before asking a user to mint a PAT
([Python](https://docs.getorchestra.io/docs/integrations/python),
[dbt Core](https://docs.getorchestra.io/docs/integrations/dbt_core)). Reach for a token only when
the repo sits outside the connected organisation or App installation, or the provider has no
workspace Git connection.

- **GitHub Enterprise URL** is the GHE field on these connections (previously labelled "Self hosted
  URL"). Leave it empty for github.com **and** on the Git-connection path; fill it only for a token
  against GHE — a GHE.com tenant URL, or a GitHub Enterprise *Server* API URL ending in `/api/v3`.
  Note the asymmetry with Git-backed pipelines above: GHES is a fine home for a *task's* repo even
  though Git control itself doesn't support it
  ([tasks on GHE.com](https://docs.getorchestra.io/docs/git-control-and-ci-cd/supported-git-providers/github-enterprise)).
- **GitHub Actions is the exception.** It has no Git-connection option, still requires a personal
  access token, and has its own GitHub Enterprise URL field (empty for github.com). Where the
  organisation enforces SAML SSO, that token must be authorised for the organisation or workflow
  runs fail with 403
  ([GitHub Actions](https://docs.getorchestra.io/docs/integrations/github_actions)).

## Optional `configuration:` block (retries/timeout/concurrency)

```yaml
configuration:          # pipeline-level default; a task's own configuration: overrides it
  retries: 2             # integer
  retry_delay: 5         # integer MINUTES — not seconds, not a timedelta string. Max 120
  timeout: 3600           # integer seconds, 0..259200 (3 days)
  concurrency:
    max_active: 1          # integer >= 0, or ${{ ENV.VAR }}; null/omit = no limit
    on_limit: SKIP         # SKIP (default) | QUEUE | QUEUE_LATEST — only meaningful with max_active
```

`timeout` is counted from when the task run is **queued**, not from when it starts executing,
so queue time eats into it. Omitting it falls back to the organisation's own task timeout
limit — 6 hours by default. A task's own `timeout` can only bring that forward: the schema
accepts up to 259200 seconds, but a value above the organisation's limit won't extend it, and
raising the limit itself (up to 3 days) is an account-manager request. Convert a source
orchestrator's execution timeout and set it explicitly rather than relying on the default.
See [task timeouts](https://docs.getorchestra.io/docs/core-concepts/tasks#task-timeouts).

`max_active` can reference an environment variable (`${{ ENV.PIPELINE_CONCURRENCY }}`) so one
pipeline gets a different limit per environment — e.g. several parallel Slim CI runs in staging,
one at a time in production. See [pipeline concurrency](https://docs.getorchestra.io/docs/core-concepts/pipelines/pipeline-runs).

`on_limit` decides what happens to a run that arrives while the pipeline is already at
`max_active`. Orchestra never cancels an in-progress run to make room, whichever mode is set:

| `on_limit` | What happens to the waiting run |
|------------|---------------------------------|
| `SKIP` (default) | Created as `SKIPPED` and never starts. |
| `QUEUE` | Held as `QUEUED`; waiting runs start in arrival order as slots free. |
| `QUEUE_LATEST` | Only the newest waiting run is held; an already-waiting run is marked `SKIPPED` when a newer one arrives. |

Pick the mode from whether a delayed run still has work to do, not from how the source
orchestrator happened to behave. `QUEUE` fits one-run-per-event triggers (a sensor or webhook per
file landed), where every trigger does distinct work. `QUEUE_LATEST` fits refreshes where only the
latest state matters, and is the safer choice on a frequent cron: if runs outlast the interval,
`QUEUE` grows an unbounded backlog while `QUEUE_LATEST` keeps at most one run waiting. `SKIP` fits
a run that is pointless once it can't start immediately.

Queueing adds a `QUEUED` pipeline-run status, so anything that enumerates or asserts on run
statuses needs to allow for it. Other queue behaviour worth knowing before recommending `QUEUE`:

- Each environment — and, for Git-backed pipelines, each branch — has its own queue, the same
  scope `max_active` is counted over.
- A run that waits 24 hours without starting expires and is marked `SKIPPED`.
- Pausing a pipeline marks its waiting scheduled, sensor, trigger-event and webhook runs `SKIPPED`.
- A queued run uses the pipeline version current when it *starts*, not when it was queued, unless
  the trigger pinned a version or Git commit. Don't queue behind a deploy and expect the old
  definition.
- When a pipeline trigger task starts a child run that queues, the child's wait counts against the
  parent task's `timeout`, so the parent needs a timeout that covers the wait.
- A pipeline that triggers *itself* is skipped rather than queued at the limit, since the child
  would wait on a slot its own parent holds. Longer cycles (A triggers B triggers A) aren't
  detected — the run sits `QUEUED` until the 24-hour expiry skips it, which then fails the parent
  task. Don't convert a cyclic trigger graph to `QUEUE`.

See [what happens when the concurrency limit is reached](https://docs.getorchestra.io/docs/core-concepts/pipelines/pipeline-runs#what-happens-when-the-concurrency-limit-is-reached).

`retry_delay` is minutes despite sources like Dagster/Airflow/Prefect typically expressing retry
delay in seconds — convert and round up, and clamp to 120 if the source value is larger.

## Variable syntax

- Environment / connection refs: `${{ ENV.VAR_NAME }}`. `LIST` and `DICT` environment variables
  also take `${{ ENV.TARGETS.eu }}` / `${{ ENV.TARGETS['eu'] }}` and `${{ ENV.REGIONS[0] }}`; the bare
  reference renders the whole value as JSON ([environments](https://docs.getorchestra.io/docs/core-concepts/environments))
- Pipeline inputs: `${{ inputs.param_name }}`
- Matrix vars: `${{ MATRIX.key }}`
- Orchestra system: `${{ ORCHESTRA.TASK_RUN_ID }}`, `${{ ORCHESTRA.CURRENT_TIME }}`
- Task outputs: `${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-name'].OUTPUTS['results'] }}`

## Optional top-level sections

**Schedule (six-field cron, minute-first — not standard seconds-first Quartz):**
`minute hour day-of-month month day-of-week [year]`, e.g. `0 8 ? * * *` = 8:00am daily. Confirmed
empirically against `validate_pipeline` — an out-of-range value in field 1 errors as "Invalid
minute value," field 2 as "Invalid hour value," not seconds/minutes as a literal Quartz reading
would suggest.

```yaml
schedule:
- name: Daily 8am
  cron: 0 8 ? * * *
  timezone: UTC
  environment: null
  branch: null
```

**Inputs:**

```yaml
inputs:
  param_name:
    type: string            # string | number | boolean | dict | list
    default: 'default value'
    options: ['default value', 'other']   # optional, string inputs only
```

`options` gives a dropdown of values in the run dialogue and trigger panels. It is a suggestion,
not a constraint: unlisted values still run. Validation requires at least one unique option, and a
literal `default` must be one of them (an expression default like `${{ ENV.X }}` is exempt). See
[inputs](https://docs.getorchestra.io/docs/core-concepts/variables/inputs).

**Webhook:**

```yaml
webhook:
  enabled: false
```

The webhook endpoint accepts **any** JSON body, so a third-party event you can't reshape is a
valid trigger. A body that doesn't match Orchestra's start-pipeline format doesn't fail — the
run starts with default options (default environment, branch, commit, all tasks, default
inputs) and the mismatch is reported in the response's `requestBodyMessage` /
`requestBodyErrors`. That silent fallback is the trap worth warning a user about: a mistyped
option such as `env` instead of `environment` starts a run that quietly ignores it, so check
`requestBodyErrors` when a run didn't use the options that were sent. Invalid JSON is the one
hard failure (`422`, no run). A body over 64 KiB still runs but isn't stored.

Either way the whole body is available as `${{ outputs.payload }}` in the webhook trigger's run
inputs, so map it to pipeline `inputs` to use it — `${{ outputs.payload }}` for the whole body,
`${{ outputs.payload['event'] }}` for one field, `${{ outputs.payload['meta']['rows'] }}` for a
nested one. Mapped inputs are then read as `${{ inputs.event_name }}` anywhere an input works,
including task conditions. `${{ outputs.payload }}` is **only** valid in that trigger's run
input mapping — there is no way to read the payload from a task parameter directly. See
[webhook triggers](https://docs.getorchestra.io/docs/core-concepts/triggers/webhook#mapping-the-payload-to-run-inputs).

**Alerts:**

```yaml
alerts:
- name: On Failure
  statuses: [FAILED, RUNNING_TIMEOUT]
  destinations:
  - integration: SLACK
    destination: '#data-alerts'
```

`max_live_alerts` (integer 1–50, default 1) on an alert raises how many in-flight dbt Core
model-failure alerts each Slack channel gets per task run. It doesn't cap alerts sent when a task or
pipeline finishes ([alerting](https://docs.getorchestra.io/docs/core-concepts/alerting)).

A live alert carries the level dbt gave that result, so dbt's `warn-error` setting changes both the
alert and the task outcome: a warning dbt escalates to an error -- a source past its `warn_after`
threshold, say -- is sent as a failure and fails the dbt Core Task. Don't treat a warn-level
threshold as non-breaking without checking whether the project runs with `warn-error`
([live alerts during a dbt Core task run](https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup#live-alerts-during-a-dbt-core-task-run)).

**Pausing:**

`paused: true` on a task or task group keeps it in the pipeline without running it. Downstream tasks
run as if it weren't there. A condition never sees `"PAUSED"`: a paused task reports `"SUCCEEDED"`
(or `"SKIPPED"` if it wouldn't have run), and `validate_pipeline` rejects a condition that compares
against `"PAUSED"` ([pausing tasks](https://docs.getorchestra.io/docs/core-concepts/tasks/pausing-tasks)).

**Anomaly detection:**

Flags a pipeline, task, or dbt operation whose duration deviates from its own historical
baseline (median of its last up-to-100 successful/warning runs, same environment, last 30
days -- at least 10 qualifying runs are required before any baseline exists, and no anomaly
can fire before then). No UI control -- git-backed YAML only.

```yaml
anomalies:                                   # pipeline level
- type: pipeline_duration_above_baseline     # default if `type` omitted -- see warning below
  percentage_above_baseline: 20              # 1-1000, default 20
  destinations:                              # optional, same shape as `alerts` destinations
  - integration: SLACK
    destination: '#data-alerts'
```

```yaml
tasks:
  <task_id>:
    anomalies:                               # task level, nested under the task
    - type: task_duration_below_baseline     # 1-99, default 75; explicit `type` required
      percentage_below_baseline: 75
```

```yaml
tasks:
  <task_id>:
    anomalies:                               # operation level (a dbt node), also nested under the task
    - type: operation_duration_above_baseline
      percentage_above_baseline: 20
      operation_types: [MATERIALISATION]     # TEST nodes are excluded unless added here
      operation_names: ["fct_*", "dim_*"]
      max_anomalies: 20
```

- Six `type` values: `pipeline_duration_above_baseline` / `pipeline_duration_below_baseline`
  (pipeline level only); `task_duration_above_baseline` / `task_duration_below_baseline`;
  `operation_duration_above_baseline` / `operation_duration_below_baseline` (dbt Cloud/Core
  tasks only -- an "operation" is a dbt node).
- `type` defaults to the above-baseline variant when omitted, so a below-baseline block must
  set `type` explicitly or it silently behaves as above-baseline instead.
- `min_baseline_seconds` (default `0`) floors the baseline -- no anomaly fires if the computed
  median comes in below it.
- Best suited to runs over ~10 minutes; short/fast tasks are too noisy run-to-run to be a
  useful signal in either direction.
- Operation-level detection also needs each dbt model opted in via `meta`
  (`orchestra_anomaly_detection: true`, with optional `orchestra_anomaly_percentage_above_baseline` /
  `_percentage_below_baseline` / `_min_baseline_seconds` / `channel` overrides) -- see the dbt Cloud
  / dbt Core integration docs. Don't add an `operation_*` block unless the user also wants (or
  already has) that dbt-side opt-in.
- Operation blocks take no `destinations` of their own -- they notify through the task's `alerts`
  block instead.

**Matrix (parallel tasks):**

```yaml
matrix:
  inputs:
    connectors:
    - conn_1
    - conn_2
```

Reference matrix values in task parameters as `${{ MATRIX.connectors }}`. Matrix tasks run in
parallel by default; add `sequential: true` under `matrix` to run them one after another instead
(e.g. to chain repeated linear flows without hand-writing a task per repetition).

## OML (`.oml`)

[OML](https://docs.getorchestra.io/docs/core-concepts/pipelines/oml) is Orchestra's recommended
format for pipelines authored in an editor rather than the UI. It describes the same `version` /
`name` / `pipeline` model as YAML, so everything above applies unchanged. What differs is the
tooling: the editor extension and `orchestra-lang` also check task dependencies, expressions,
sensor expressions, anomaly thresholds, cron and per-job parameters, which a JSON Schema can't.

Match whatever the repo already uses. Write `.oml` when the user asks for it or the repo already
has `.oml` pipelines. Existing YAML pipelines keep working, so don't convert them unprompted.

Syntax differences to know before editing an `.oml` file:

| Syntax | Meaning |
|---|---|
| `.` | Closes the current block — optional, but emitted by the formatter and by Orchestra |
| `=` | Closes the current list |
| `<>` | Empty list, where YAML uses `[]` |
| `%sql` … `%%` | Embed block holding code in the named language (also `%python`, `%bash`, `%json`, `%yaml`) |

The trap is quoting: OML is a superset of JSON, not of YAML, so an unquoted string must start with
a letter or `_`. Values YAML lets you leave bare — cron expressions, UUID-shaped task IDs, dbt
commands, URLs — have to be quoted. Whitespace isn't structural, so a stray indent can't silently
re-parent a task the way it can in YAML.

## Validation

After writing or editing a file, validate it with the tool that matches its extension.

For `.yml` / `.yaml`:

```bash
orchestra-cli pipeline validate <path/to/pipeline.yml>
```

For `.oml`, use the `orchestra-lang` package (imported as `oml_lang`). It runs the same checks as
the editor extension and needs no API key or network access:

```bash
pip install orchestra-lang
```

Report each entry of `oml_lang.analyze(source).errors()` with its line and column. Don't run
`orchestra-cli pipeline validate` on an `.oml` file: the CLI accepts the `.oml` extension but
reads it as YAML, so OML block terminators (`.`) and embeds (`%sql ... %%`) fail with an
`Invalid YAML` error. See
[Pipeline Validation](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/validation).

CLI commands are `noun verb` (`orchestra pipeline validate`, `orchestra pipeline import`,
`orchestra pipeline run`). The old flat names (`orchestra validate`, `orchestra import`,
`orchestra run`, `orchestra create-pipeline`, `orchestra update-pipeline`,
`orchestra delete-pipeline`, `orchestra fetch-pipelines`) still work as hidden aliases, so
existing scripts keep running — but write the noun/verb form in anything new, and don't
"fix" a legacy name you find in a working CI config. See the
[Orchestra CLI](https://docs.getorchestra.io/docs/git-control-and-ci-cd/orchestra-cli).

Prefer MCP `validate_pipeline` when the Orchestra MCP server is connected and you need to
validate without a local CLI install. It takes the definition as JSON, so convert an `.oml` file
with `oml_lang.to_json` first.

With the `orchestra` plugin installed, YAML validation happens on its own: a `PostToolUse` hook
validates any `.yml` / `.yaml` pipeline you write against `/pipelines/schema` and reports the
errors back immediately. Neither an API key nor a CLI install is required. Set `ORCHESTRA_API_KEY`
to also have integration connection references checked. The hook doesn't cover `.oml`, so
validate those yourself with `orchestra-lang`.

### Common validation errors

| Error type | Fix |
|---|---|
| Missing required field | Add the field with a sensible value or placeholder |
| Invalid integration name | Correct spelling (all caps); see integration table |
| Invalid job type | Match `integration_job` to the integration |
| Unknown parameter | Remove or rename to match the integration schema |
| Invalid `depends_on` reference | Referenced ID must exist at the correct level (task vs task group) |
| YAML syntax error | Fix indentation, quoting, or structure |
| Invalid cron expression | Six fields, minute-first: `0 8 ? * * *` (not seconds-first Quartz) |
| `tags` on a task group (`extra_forbidden`) | `TaskGroupModel` has no `tags` field — confirmed live against `/pipelines/schema`. Put `tags:` on each task, never on the stage wrapping it |
| `environment_variables` as a YAML mapping (`Input should be a valid string`) | On `DBT_CORE_EXECUTE`, `PYTHON_EXECUTE_SCRIPT` and other tasks that take it, `parameters.environment_variables` must be a JSON string, not a mapping — confirmed live against `validate_pipeline`. Write `environment_variables: '{"KEY": "${{ inputs.x }}"}'` |
| Invalid threshold expression (e.g. on `SNOWFLAKE_RUN_TEST`) | `error_threshold_expression` / `warn_threshold_expression` need a single-character comparator (`=`, `>`, `<`, `>=`, `<=`, `!=`) + a non-negative integer — confirmed live: `'== 0'` is rejected, `'= 0'` is accepted. Python-style `==` doesn't work here |

Re-run validation after each fix. Cap remediation at around 5 attempts — patch only what the
latest errors report rather than regenerating from scratch each time; if still failing after 5,
present the YAML with the remaining errors listed instead of continuing indefinitely.

### Runtime substitution gotcha

`${{ ... }}` substitutions (`${{ inputs.x }}`, `${{ ORCHESTRA.PIPELINE_RUN_TASKS[...].OUTPUTS[...] }}`)
are inserted as raw text with no escaping for whatever syntax surrounds them. A JSON-shaped output
substituted into a quoted string breaks on the first internal `"`. When a substituted value could
itself contain the quote character wrapping it (JSON-shaped values are the common case), wrap it in
Python triple-quotes instead — `json.loads("""${{ ... }}""")` — rather than single/double quotes.
There's no triple-quote equivalent for JSON-typed parameters like `environment_variables`; avoid
routing a quote-containing value through those, and substitute it directly in a `code:`/`command:`
block instead.

## User handoff

Report: file path, stage → task structure, connections or env vars to configure in the
Orchestra UI, and any placeholder values (for example `your_connector_id`) still to replace.
