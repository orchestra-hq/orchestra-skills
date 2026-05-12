# Orchestra MCP — tools quick reference

Tool map for Orchestra pipeline skills (`fix-orchestra-pipeline`, `triage-orchestra-pipeline`,
`create-orchestra-pipeline`).
Use these MCP tools for all operations unless the allowed REST read-only fallback applies — see
`../api/rest-pipeline-yaml.md`.

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
- For the **only** permitted direct HTTP call (fetch pipeline YAML when MCP lacks it), see `../api/rest-pipeline-yaml.md`. No other REST usage in these skills.
