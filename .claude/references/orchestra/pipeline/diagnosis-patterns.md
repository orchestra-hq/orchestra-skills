# Diagnosis Patterns

Error pattern reference for Orchestra pipeline failures, organised by integration type.
Use this to classify errors in Step 4 of the fix workflow.

## Table of contents

1. [Universal patterns](#universal-patterns) — errors common across all integrations
2. [dbt / dbt Core](#dbt--dbt-core)
3. [Snowflake](#snowflake)
4. [Python](#python)
5. [HTTP / Webhook](#http--webhook)
6. [Fivetran](#fivetran)
7. [Airbyte](#airbyte)
8. [AWS services](#aws-services) — Lambda, Glue, ECS, S3, Redshift
9. [Azure services](#azure-services) — ADF, Synapse, Container Apps
10. [GCP services](#gcp-services) — BigQuery, Cloud Run, Dataflow
11. [Sync job conflicts](#sync-job-conflicts)

---

## Universal patterns

These apply regardless of integration type.

### FEATURE_BRANCH_RUN — check before escalating

**Signals to check first, before diagnosing the error:**
- `taskParameters.branch` is set to something other than `main` / `master`
- `triggeredBy` is `MANUAL` or `RESTART_FROM_SELECTED` (never `SCHEDULED`)
- The same pipeline has recent SUCCEEDED runs with no explicit branch (defaulting to main)
- The pipeline has no schedule configured (`schedule: []`)

**How to identify:** Pull all recent runs for the pipeline and check the `branch` field on
their task parameters. If failures cluster on a named feature branch and successes have no
branch set (or use `main`), this is a feature branch issue, not a production incident.

**Action:** Confirm with the user before investing in a fix. Ask: "This failure is on the
`{branch}` feature branch — do you want me to investigate, or is main working fine?" Check
whether main/scheduled runs are succeeding before treating it as urgent.

**Do not auto-retry** feature branch runs — the developer may be mid-iteration and a retry
could interfere with their work.

---

### AUTH_FAILURE
**Log signals:**
- `401`, `403`, `Unauthorized`, `Forbidden`, `Access Denied`
- `token expired`, `invalid credentials`, `authentication failed`
- `could not assume role`, `insufficient permissions`
- Orchestra message: "Request timed out" (often indicates firewall, but can also mean expired creds)

**Diagnosis:** Credentials configured in the Orchestra connection have expired, been rotated,
or lack the required permissions. Check `connectionId` on the task run to identify which connection.

### TIMEOUT
**Log signals:**
- `timeout`, `timed out`, `deadline exceeded`, `execution time limit`
- Orchestra task `numberOfAttempts` > 1 (retries exhausted)
- Task ran for close to or exactly the configured `timeout` value in seconds

**Diagnosis:** The underlying operation took longer than allowed. Could be a slow query,
a large data load, or a platform-side delay. Check if the data volume has grown recently.

### NETWORK_ERROR
**Log signals:**
- `connection refused`, `ECONNREFUSED`, `DNS resolution failed`
- `could not connect`, `network unreachable`, `host not found`
- Orchestra message: "Request timed out" (common for VPN/firewall issues)

**Diagnosis:** The Orchestra engine cannot reach the target platform. Common with platforms
deployed in private networks (VPNs, VPCs). The user may need to whitelist Orchestra IPs or
configure a private connection.

### RESOURCE_CONFLICT
**Log signals:**
- `already running`, `resource is busy`, `lock timeout`, `concurrent modification`
- Orchestra message about sync job already in Running state

**Diagnosis:** For sync-type integrations (Fivetran, Airbyte, etc.), Orchestra detected the
underlying object was already running and refused to start a duplicate. This happens when
pipeline schedules are more frequent than the sync duration. Solution: increase schedule
interval or check why the sync is slow.

---

## dbt / dbt Core

Integration values: `DBT` (dbt Cloud), `DBT_CORE` (self-hosted via Orchestra).

### Compilation failure
**Log signals:**
- `Compilation Error`, `parsing error`, `YML error`
- `Could not find model`, `Undefined variable`
- In `run_results.json`: status `error` with `message` containing "Compilation"

**Diagnosis:** The dbt project has a syntax or reference error. The model name, file path,
and exact error line are in the log. This requires a code fix in the dbt repository.

### Test failure
**Log signals:**
- `WARN` or `FAIL` in `run_results.json` with `unique_id` starting with `test.`
- `error_threshold_expression` or `warn_threshold_expression` triggered
- dbt test result: `failures: N` where N exceeds threshold

**Diagnosis:** Data quality tests failed. Check whether this is a legitimate data issue
(new nulls, duplicates, referential integrity violation) or an overly strict threshold.
The `run_results.json` artifact contains the exact test names and failure counts.

### Missing source / stale source
**Log signals:**
- `Source has become stale`, `source freshness`
- `Relation does not exist`, `Table not found`

**Diagnosis:** An upstream source table is missing, renamed, or hasn't been refreshed.
Check if the ingestion pipeline that feeds this source ran successfully.

### Profile / connection error
**Log signals:**
- `Could not connect to database`, `Invalid credentials`
- `profiles.yml` error, `target not found`
- Environment variable not set

**Diagnosis:** The dbt profiles.yml in the git repo doesn't match the Orchestra environment
configuration. Check that secrets/env vars are set correctly on the Orchestra connection.

### Warehouse permission error
**Log signals:**
- `Permission denied`, `Insufficient privileges`
- `CREATE TABLE` or `INSERT` permission missing
- `GRANT` required on schema or database

**Diagnosis:** The service account used by dbt lacks write permissions on the target schema
or database. Provide the exact GRANT statement needed.

---

## Snowflake

Integration: `SNOWFLAKE`. Jobs: `SNOWFLAKE_RUN_QUERY`, `SNOWFLAKE_RUN_TEST`.

### Query syntax error
**Log signals:**
- `SQL compilation error`, `syntax error`, `unexpected`
- Error code in `externalStatus`
- The failing SQL statement is usually in `taskParameters.statement`

**Diagnosis:** SQL syntax issue. The exact statement and error position are in the logs.

### Object not found
**Log signals:**
- `Object does not exist`, `Table ... does not exist`
- `Schema ... does not exist`, `Database ... does not exist`

**Diagnosis:** A referenced object was dropped, renamed, or is in a different
database/schema than expected. Check if a migration ran or if the environment
variables point to the wrong database.

### Warehouse suspended / resource error
**Log signals:**
- `Warehouse ... is suspended`, `Cannot perform operation`
- `warehouse is being resumed`
- `Statement reached its statement or warehouse timeout`

**Diagnosis:** The Snowflake warehouse is auto-suspended and taking too long to resume,
or the warehouse is too small for the query. Check warehouse auto-resume settings and
consider sizing up for the query.

### Role / permission error
**Log signals:**
- `Insufficient privileges`, `access denied`
- `Current role does not have privileges`

**Diagnosis:** The Snowflake role in the Orchestra connection lacks required grants.

---

## Python

Integration: `PYTHON`. Executed via Orchestra's serverless Python runtime.

### Import / dependency error
**Log signals:**
- `ModuleNotFoundError`, `ImportError`, `No module named`
- `pip install` failure in build phase

**Diagnosis:** A required Python package is missing or has a version conflict. Check the
`requirements.txt` or `pyproject.toml` in the git repository. Ensure the package is
compatible with Python 3.x and the Orchestra runtime.

### Script execution error
**Log signals:**
- `Traceback`, `Exception`, `Error`
- `NameError`, `TypeError`, `ValueError`, `KeyError`
- Non-zero exit code

**Diagnosis:** The Python script itself has a bug. The full traceback is in the logs with
file, line number, and exception type. This requires a code fix in the repository.

### Secret / environment variable missing
**Log signals:**
- `KeyError: 'SOME_ENV_VAR'`, `os.environ` errors
- `Environment variable not set`

**Diagnosis:** The script expects an environment variable or secret that isn't configured
in the Orchestra connection's Secret JSON field. List the expected variables and which
ones are missing.

### AWS IAM role assumption failure
**Log signals:**
- `AccessDenied`, `is not authorized to assume role`
- `Trust relationship` error
- `The security token included in the request is expired`

**Diagnosis:** The Python task is configured to assume an AWS IAM role, but either the
trust relationship is misconfigured, the role ARN is wrong, or the task hasn't been
run at least once (Orchestra's IAM role doesn't exist until first run). Also check if
the script runs longer than 1 hour (role assumption expires).

---

## HTTP / Webhook

Integration: `HTTP`. Job: `HTTP_REQUEST`.

### Non-2xx response
**Log signals:**
- `externalStatus` shows HTTP status code (400, 401, 403, 404, 500, 502, 503)
- `externalMessage` contains the response body or status text

**Diagnosis by status code:**
- `400` — bad request parameters. Check `taskParameters` (path, method, body)
- `401/403` — authentication issue with the target API
- `404` — endpoint not found. Check URL and path
- `429` — rate limited. Need to add delays or reduce frequency
- `500/502/503` — target service is down. Transient — retry may work

### Connection error
**Log signals:**
- `ECONNREFUSED`, `ETIMEDOUT`, `DNS lookup failed`

**Diagnosis:** The target URL is unreachable from Orchestra's network. Firewall or DNS issue.

---

## Fivetran

Integration: `FIVETRAN`. Job: `FIVETRAN_SYNC`.

### Sync already running
**Log signals:**
- Orchestra message about object already in Running state
- `RESOURCE_CONFLICT` category

**Diagnosis:** The Fivetran connector is still syncing from a previous trigger. Increase
the Orchestra schedule interval or check why the sync is slow (data volume increase,
API throttling at the source).

### Connector error
**Log signals:**
- Fivetran-specific error codes in artifacts
- `connector is broken`, `setup incomplete`, `authentication failed`

**Diagnosis:** The Fivetran connector itself needs fixing in the Fivetran dashboard.
Provide the Fivetran connector ID and link.

---

## Airbyte

Integration: `AIRBYTE_CLOUD` or `AIRBYTE_SERVER`. Similar patterns to Fivetran.

### Sync failure
**Log signals:**
- `Connection failed`, `Sync failed`
- Source or destination error in Airbyte logs

**Diagnosis:** Check whether the issue is on the source side (API rate limits,
credential expiry) or destination side (warehouse permissions, schema drift).

---

## AWS services

### Lambda — LAMBDA_EXECUTE_ASYNC_FUNCTION
- `Task timed out` — Lambda max execution time exceeded (15 min ceiling)
- `Runtime.ImportModuleError` — missing dependency in deployment package
- `AccessDeniedException` — Lambda execution role lacks permissions

### Glue — AWS_GLUE_RUN_JOB
- `EntityNotFoundException` — Glue job doesn't exist (wrong name or region)
- `ConcurrentRunsExceededException` — too many concurrent runs
- `InternalServiceException` — AWS-side issue, retry

### ECS — AWS_ECS_RUN_TASK
- `STOPPED (Essential container exited)` — application crash, check container logs
- `CannotPullContainerError` — Docker image not found or ECR auth issue
- `ResourceNotFoundException` — cluster or task definition doesn't exist

### S3 (sensor)
- `AccessDenied` — bucket policy or IAM permissions
- `NoSuchBucket`, `NoSuchKey` — wrong bucket/path

---

## Azure services

### ADF — ADF_PIPELINE_RUN
- `PipelineFailedError` — check ADF activity-level errors
- `InvalidParameterValue` — wrong parameters passed from Orchestra

### Synapse
- Similar to Snowflake patterns. Check for serverless SQL pool cold-start timeouts.

### Container Apps — ACA_RUN_JOB
- `ContainerAppJobExecutionFailed` — application error, check container logs
- `ProvisioningFailed` — infrastructure issue

---

## GCP services

### BigQuery — GCP_BIG_QUERY
- `notFound` — dataset or table doesn't exist
- `accessDenied` — service account permissions
- `quotaExceeded` — BigQuery slot or query size limits

### Cloud Run — GCP_CLOUD_RUN
- `Container failed to start` — application error or missing env vars
- `DEADLINE_EXCEEDED` — request timeout

---

## Sync job conflicts

This is a cross-cutting concern documented in Orchestra's integration overview. Some
integration jobs are "sync" jobs where the underlying platform has no discrete "run" object.
If Orchestra tries to trigger a sync while the previous one is still running, Orchestra
will **fail the task** rather than create duplicate runs. This is intentional protective
behaviour.

**How to identify:**
- Orchestra message mentions the object is "already running"
- Task status is FAILED but the underlying sync eventually succeeds
- Pattern repeats on a schedule

**Fix:** Either increase the schedule interval so syncs complete between triggers, or
investigate why the sync duration increased (data volume growth, API throttling).
