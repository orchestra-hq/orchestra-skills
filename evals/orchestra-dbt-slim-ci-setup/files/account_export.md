# Orchestra account export (acme-data)

Environments: `Production`, `PreProd`. No environment variables defined on either.
dbt repo: `acme/analytics-dbt`, default branch `main`. All pipelines are Git-backed in `acme/analytics-dbt` under `orchestra/`.

## Pipelines

### dbt_production (id 6f1c2a90-0d1e-4b7a-9a51-2f3c8e1d4b10)
Scheduled daily 05:00 UTC. Last 30 runs: all SUCCEEDED, branch `main`, environment `Production`.

```yaml
version: v1
name: dbt_production
pipeline:
  dbt:
    tasks:
      run_dbt:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        parameters:
          commands: dbt build --target prod
          branch: main
          package_manager: PIP
          python_version: "3.12"
        depends_on: []
        name: dbt build
        connection: dbt_core_prod_10001
    depends_on: []
    name: dbt
  save_manifest:
    tasks:
      upload_manifest:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          command: python scripts/save_manifest.py
          package_manager: PIP
          python_version: "3.12"
        depends_on: []
        name: upload manifest.json to s3
        connection: python_s3_10003
    depends_on: [dbt]
    condition: ${{ inputs.run_type }} == 'CI'
    name: save manifest
inputs:
  run_type:
    type: string
    default: SCHEDULED
schedule:
  - name: Daily 5am
    cron: 0 5 ? * * *
    timezone: UTC
configuration:
  concurrency:
    max_active: 1
```

### dbt_slim_ci (id 0b7e4d21-55aa-4c1f-8e2b-91d0c6a7f3e2)
No schedule. Last 12 runs: all FAILED, the most recent 41 days ago. Every failure log contains
`Could not find manifest.json in latest_production` or `state:modified selected 0 nodes`.

```yaml
version: v1
name: dbt_slim_ci
pipeline:
  dbt:
    tasks:
      slim_ci:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        parameters:
          commands: dbt build -s state:modified+ --defer --state latest_production --target prod
          branch: ${{ inputs.dbt_branch }}
          package_manager: PIP
          python_version: "3.12"
        depends_on: []
        name: slim ci
        connection: dbt_core_prod_10001
    depends_on: []
    name: dbt
inputs:
  dbt_branch:
    type: string
    default: main
```

### fivetran_hourly (id 3c9a8b70-1f2e-4d6c-b5a4-7e8f9a0b1c2d)
Scheduled hourly. Syncs Fivetran connectors; no dbt task. Last 30 runs SUCCEEDED.
