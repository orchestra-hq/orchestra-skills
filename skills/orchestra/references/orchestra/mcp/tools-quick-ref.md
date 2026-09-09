# Orchestra MCP — tools quick reference

Tool map for Orchestra pipeline skills (`fix-orchestra-pipeline`, `triage-orchestra-pipeline`,
`create-orchestra-pipeline`).
Use these Orchestra MCP tools for all operations.

## Reach for these first

Three composite tools each answer a whole triage question in one call, joining the
endpoints below and paging internally. Prefer them over hand-assembling the same answer
from the granular tools — that costs five or six round trips and the joining is on you.
The granular tools stay available for anything the composites do not cover.

### `whats_broken`
Arguments (both optional):
- `window_hours` (default 24; anything wider than 168 is clamped to 168, the widest the API serves)
- `environment` (environment name or ID)

Returns every FAILED and WARNING pipeline run in the window, each already joined to the
task runs that failed inside it, with `message`, `externalMessage`, `platformLink`,
duration-vs-baseline `anomalies`, and a lineage URL. Retried attempts are excluded.

Use for:
- "what's broken", "why did last night's run fail", any triage with no ID to start from
- a workspace-wide sweep before picking which failure to chase
- `truncated: true` means the digest is partial — narrow the window or the environment

Replaces: `list_pipeline_runs` → `list_task_runs` → group-by-run, done by hand.

### `diagnose`
Required arguments:
- `task_run_id`

Returns the task run's status and messages, its `taskParameters` and `runParameters`, the
statuses of the upstream tasks in `dependsOn`, the tail of its newest log, and its
artifact filenames. Task runs are queryable for 7 days only.

Use for:
- the deep dive on one failure, straight after `whats_broken`
- deciding whether you need the full log or an artifact at all

Replaces: `list_task_runs` → `list_task_run_logs` → `download_task_run_log` →
`list_task_run_artifacts`, done by hand. When the log tail comes back
`truncated: true`, follow up with `download_task_run_log`.

### `pipeline_context`
Required arguments:
- `pipeline_id_or_alias`

Returns the pipeline's metadata, its **full definition** (the YAML structure as JSON), the
integrations its tasks use, its recent run outcomes and the median duration of its
succeeded runs. Run history covers the last 7 days.

Use for:
- reading a pipeline before editing it, instead of guessing at YAML structure
- judging whether a failure is new or chronic, from the recent-outcome list
- a duration baseline to compare a slow run against

Replaces: `get_pipeline` + `get_pipeline_data` + `list_pipeline_runs`, done by hand.

## Querying failures

### `list_pipeline_runs`
Arguments:
- `status` (`FAILED`, `RUNNING`, etc.)
- `time_from`, `time_to` (ISO 8601)
- `pipeline_run_ids` (comma-separated IDs)

Use for:
- finding recent failed runs
- validating whether a UUID is a pipeline run ID

### `list_task_runs`
Arguments:
- `status` (`FAILED`, `WARNING`, etc.)
- `pipeline_ids` (comma-separated IDs)
- `integration`, `task_run_ids`, `time_from`, `time_to`

Use for:
- finding failed tasks inside one or more pipelines
- pulling integration-level context and retry history

### `list_operations`
Arguments:
- `task_run_id`
- optional filters: `status`, `operation_type`, `integration`, `time_from`, `time_to`

Use for:
- seeing sub-operations (dbt models, SQL statements, sync steps)

## Fetching diagnostics

### `list_task_run_logs`
Required arguments:
- `pipeline_run_id`
- `task_run_id`

### `download_task_run_log`
Required arguments:
- `pipeline_run_id`
- `task_run_id`
- `filename`

Optional arguments:
- `range_header` (for large logs, use `bytes=-262144` for the tail)

### `list_task_run_artifacts`
Required arguments:
- `pipeline_run_id`
- `task_run_id`

### `download_task_run_artifact`
Required arguments:
- `pipeline_run_id`
- `task_run_id`
- `filename`

## Taking action

### `list_pipelines`
No arguments.

Use for:
- matching by pipeline name/alias
- checking pipeline metadata including `storageProvider`

### `get_pipeline`
Read-only. Fetch a single pipeline's full definition by selector. Provide exactly one selector:
- `pipeline_id`, **or**
- `alias`, **or**
- `repository` + `yaml_path` (both required together)

Optional: `version`, `branch`, `commit`.

Use for reading the full stored pipeline definition (e.g. when `list_pipelines` metadata is not enough). For Git-backed pipelines, the repo YAML remains the source of truth for edits.

### `start_pipeline`
Required arguments:
- `alias_or_pipeline_id`

Optional arguments:
- `branch`
- `commit`
- `environment`
- `run_inputs`

### `get_pipeline_run_status`
Required arguments:
- `pipeline_run_id`

### `cancel_pipeline_run`
Required arguments:
- `pipeline_run_id`

### `validate_pipeline`
Required arguments:
- `pipeline_definition`

### `create_pipeline`
Use for creating Orchestra-backed pipelines.

### `update_pipeline`
Arguments:
- `alias` (required)
- `data` (required)
- `published` (optional, defaults false)
- `storage_provider` (optional, defaults `ORCHESTRA`)

Use for updating Orchestra-backed pipelines only.

## Useful supporting tools

### `list_assets`
Filterable by asset type/integration. Useful when diagnosing missing tables or lineage gaps.

### `get_pipeline_run_lineage_url`
Returns the Orchestra lineage URL for a pipeline run.

## Constraints and behavior notes

- Time window constraints still apply (typically 7-day metadata windows in practice).
- Prefer batching calls (`list_*`) before deep downloads.
- Git-backed pipelines cannot be edited with `update_pipeline`; provide a repo-level fix instead.
- `list_task_runs` and `list_task_runs_for_pipeline_run` include superseded attempts by
  default, so a retried task appears more than once. Pass `include_superseded=false` for a
  failure list. The composite tools already do.
- A 403 means the Metadata API is not enabled for the workspace, not a bad key. Say so and
  ask the user to have a workspace admin enable it, rather than retrying.
