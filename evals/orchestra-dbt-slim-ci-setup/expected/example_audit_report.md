## Slim CI audit — 7 gaps, 1 conflict

**Fix first:** `dbt_slim_ci` is a separate pipeline with its own dbt task, so its `latest_production` has never been populated. That's why every run fails with "Could not find manifest.json" or selects 0 nodes. It also builds with `--target prod`, so a working run would write PR code into production schemas.

| Component | Status | Evidence → consequence |
|-----------|--------|------------------------|
| One pipeline + dbt task for prod and CI | 🔀 | `dbt_slim_ci` alongside `dbt_production` → CI never has a production state to compare against |
| Parametrised `dbt_command` / `dbt_branch` | ❌ | `dbt_production.run_dbt` hard-codes `dbt build --target prod` and `main` → can't run PR branches |
| `ci` target | ❌ | `profiles.yml` only has `prod` → CI has nowhere safe to build |
| Per-PR schema | ❌ | No `generate_schema_name` override → concurrent PRs would collide |
| Per-environment concurrency | ⚠️ | `max_active: 1` → PR runs come back `SKIPPED` while prod runs, and the check still passes |
| PR workflow | ⚠️ | `run-pipeline@v1`, no `environment`, no `cancel_on_exit` → superseded runs keep building |
| Deploy on merge | ❌ | Merge job only triggers the manifest save |
| CI schema clean-up | ❌ | Nothing drops CI schemas on PR close |

Also present: `save_manifest` Python task + `run_type == 'CI'` + `PreProd` environment. This is the manual manifest pattern, which `latest_production` replaces. It's harmless to keep, but nothing reads that S3 manifest any more.

Already in place: `ORCHESTRA_API_KEY` secret, daily production schedule. (`fivetran_hourly` is unrelated.)

### Plan
1. [manual] Add a `ci` target (`schema: ci`) to `profiles.yml` on `dbt_core_prod_10001` — CI builds into `ci_<PR number>`, never `analytics`.
2. [agent, approval] Parametrise `dbt_production`: `dbt_branch`, `dbt_command`, `dbt_ci_schema_suffix` inputs, and `max_active: ${{ ENV.DBT_PIPELINE_CONCURRENCY }}` — one pipeline, one `latest_production`.
3. [agent, approval] Add `generate_schema_name` and `drop_ci_schema` macros — per-PR schemas and clean-up.
4. [manual] Create a `CI` environment; set `DBT_TARGET` (`ci` / `prod`) and `DBT_PIPELINE_CONCURRENCY` (`5` / `1`) on `CI` / `Production` — parallel PR runs, prod stays serial.
5. [agent, approval] Replace `dbt_ci.yml` with PR, deploy-on-merge and clean-up jobs on `run-pipeline@v1.7.0`, pointed at `dbt_production` with `task_ids: run_dbt` — PR checks run against production state.
6. [agent, approval] Pause `dbt_slim_ci` once step 5 has passed on a PR.
7. Optional [agent, approval] Remove `save_manifest`, its `run_type` input, and the `PreProd` merge job — fewer moving parts. Your call.

Proceed with step 2?
