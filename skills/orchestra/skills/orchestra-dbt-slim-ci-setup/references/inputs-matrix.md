# Input matrix

Collect before retrofit. Group: **must-have** (ask if missing), **discoverable** (read from workspace), **manual** (UI only; document for user).

## Must-have

| Input | Why |
|-------|-----|
| Orchestra workspace + API key | MCP validation and optional smoke trigger |
| Production pipeline id and/or alias | Retrofit target |
| dbt task id | When using `task_ids` on `run-pipeline` in a multi-task pipeline |
| dbt Git repo `org/repo` + default branch | `latest_production` baseline |
| CI provider (default GitHub Actions) + PR base branch | Workflow triggers |
| Orchestra environment names for PR vs merge (case-sensitive) | Maps GHA `environment` to Orchestra |
| Slim CI dbt command body | Default: `build -s state:modified+ --defer --state latest_production --target ci`; incremental variant adds `dbt clone` + `modified_incremental` selector |
| dbt `--target` for CI (and prod if in command) | Must exist in Orchestra dbt connection `profiles.yml` / task env |
| Path filters for workflow `paths` | e.g. `models/**`, `macros/**`, `seeds/**`, `dbt_project.yml` |
| CI schema prefix | `schema` on the `ci` target, e.g. `ci` → `ci_<PR number>` |
| Deploy-on-merge behaviour | Rebuild modified models (template default), full refresh, or none (leave to the schedule) |

## Discoverable in a dbt workspace

| Source | What to infer |
|--------|----------------|
| `dbt_project.yml` | Profile name, tags to exclude, incremental patterns |
| `profiles.yml` | Targets; flag mismatch if workflow uses `ci`/`prod` but file only has `dev` |
| `macros/**` | Existing `generate_schema_name` override to merge the `ci` branch into; existing `drop_ci_schema` |
| `selectors.yml` | Existing selectors; whether `modified_incremental` is present |
| `models/**` incremental configs | Whether the incremental variant is needed |
| `orchestra/*.yml` | Existing inputs, task ids |
| `.github/workflows/*` | Existing Slim CI, secrets names, pipeline id |
| Repo layout | Pipeline YAML in dbt repo vs separate pipeline repo |

## Manual (no API automation)

| Item | Notes |
|------|--------|
| Git provider → Orchestra | https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup |
| dbt Core connection | Upload `profiles.yml`, Secret JSON for `env_var`, optional Validate |
| Warehouse `operation_metadata` on dbt tasks | Per adapter docs |
| GitHub secrets | `ORCHESTRA_API_KEY`; optional `ORCHESTRA_DBT_PIPELINE_ID` (secret or repo variable) |
| Orchestra environment variables | `DBT_TARGET`, `DBT_PIPELINE_CONCURRENCY` per environment (CI vs Production) |
| Duplicate PreProd environment | Only if using manifest-save extensions on merge to main |

## Questionnaire (agent)

Ask in one batch when not discoverable:

1. Pipeline id (and alias if known)? dbt task id for Slim CI?
2. dbt repo and default branch? Pipeline YAML path and repo (same as dbt or separate)?
3. Orchestra environment names for PR vs merge?
4. Slim command (default ok?) and `--target` for CI? Excludes (e.g. `tag:metadata`)?
5. Workflow path filters? Include local SQLFluff job?
6. Incremental models in the project (use the clone + `modified_incremental` variant)?
7. On merge: rebuild modified models, full refresh, or leave to the schedule?
8. Per-PR schema prefix (default `ci`) and drop it on PR close (default yes)?

Do not proceed to warehouse-touching `start_pipeline` without explicit approval.
