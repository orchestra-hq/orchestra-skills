# Remediation Playbooks

Action plans for each error category. Consult this in Step 5 of the fix workflow.
Each playbook specifies whether Claude can fix it directly or needs user action.

## Table of contents

1. [AUTH_FAILURE](#auth_failure)
2. [TIMEOUT](#timeout)
3. [QUERY_ERROR](#query_error)
4. [RESOURCE_CONFLICT](#resource_conflict)
5. [NETWORK_ERROR](#network_error)
6. [CONFIG_ERROR](#config_error)
7. [DEPENDENCY_FAILURE](#dependency_failure)
8. [PLATFORM_ERROR](#platform_error)
9. [CODE_ERROR](#code_error)
10. [RATE_LIMIT](#rate_limit)
11. [DATA_ERROR](#data_error)

---

## AUTH_FAILURE

**Can Claude fix directly?** No — credentials cannot be updated via MCP pipeline tools.

**Playbook:**
1. Identify the `connectionId` from the failed task run
2. Tell the user which connection needs updating
3. Provide specific instructions based on integration:
   - **Snowflake:** "Go to Orchestra → Integrations → Snowflake → [connection name]. Update
     the password/key pair. If using key pair auth, ensure the public key is registered in
     Snowflake with `ALTER USER ... SET RSA_PUBLIC_KEY = '...'`"
   - **dbt Core:** "Check the Secret JSON on the dbt Core connection. Ensure all environment
     variables for database credentials are current."
   - **AWS:** "The IAM role trust relationship may need updating. Ensure Orchestra's role ARN
     is in the trust policy. If using access keys, rotate them in IAM and update the connection."
   - **HTTP:** "Update the API key or bearer token in the HTTP connection settings."
4. After user confirms the credential is updated, retry the pipeline

**Prevention tip:** Suggest setting up credential expiry alerts or using service accounts
with long-lived credentials where possible.

---

## TIMEOUT

**Can Claude fix directly?** Partially — can retry, and can update timeout config on
Orchestra-backed pipelines.

**Playbook:**
1. Check the configured `timeout` value in the pipeline YAML/configuration
2. Check how long the task actually ran (compare `startedAt` to `completedAt`)
3. Determine if this is a transient or structural timeout:
   - **Transient** (task usually succeeds, this is an outlier): Retry the pipeline.
     If Orchestra-backed, consider increasing `configuration.timeout` via `update_pipeline`.
   - **Structural** (task consistently runs close to timeout): The underlying query/process
     needs optimisation. Advise the user on specifics:
     - Snowflake: suggest warehouse sizing up, query optimisation, or clustering
     - dbt: suggest incremental models instead of full refresh
     - Python: suggest chunking large operations
     - Lambda: note the 15-minute hard ceiling
4. For Orchestra-backed pipelines, update timeout via `update_pipeline`:
   ```json
   { "configuration": { "timeout": 600 } }
   ```
5. Retry after adjustment

---

## QUERY_ERROR

**Can Claude fix directly?** Only on Orchestra-backed pipelines with inline SQL. Git-backed
pipelines require a code change.

**Playbook:**
1. Extract the failing SQL statement from `taskParameters.statement` or logs
2. Identify the specific error (missing column, syntax error, type mismatch)
3. **If Orchestra-backed with inline SQL:**
   - Fix the SQL in the task parameters
   - Update via `update_pipeline` with the corrected statement
   - Retry
4. **If Git-backed (dbt, Python, etc.):**
   - Show the user the exact file, line, and correction needed
   - For dbt: identify the model file path from the manifest
   - Explain: "This pipeline is Git-backed, so the fix needs to be committed to
     `[repository]` on branch `[branch]`. Here's the change needed: ..."
5. For missing tables/columns, check if this is a schema drift issue and advise
   on schema evolution strategy

---

## RESOURCE_CONFLICT

**Can Claude fix directly?** Yes — by adjusting timing or waiting.

**Playbook:**
1. Identify which external resource is conflicting (Fivetran connector, Airbyte sync, etc.)
2. Check the schedule frequency vs typical sync duration
3. Options:
   - **Wait and retry:** If the previous sync is about to finish, just wait and retry
   - **Adjust schedule:** If Orchestra-backed, update the cron schedule to be less frequent:
     ```json
     { "schedule": [{ "cron": "0 */2 * * *" }] }
     ```
   - **Add a sensor:** Suggest adding a sensor that checks if the sync is complete before
     triggering dependent tasks
4. If the sync duration has grown unexpectedly, advise investigating the root cause
   in the upstream platform (data volume growth, API throttling)

---

## NETWORK_ERROR

**Can Claude fix directly?** No — requires infrastructure changes.

**Playbook:**
1. Determine whether the target is public or private:
   - **Public endpoint:** Likely a temporary DNS or connectivity issue. Retry first.
   - **Private network:** Orchestra needs network access configured.
2. For private network targets:
   - Provide Orchestra's IP ranges for firewall whitelisting
   - Suggest Orchestra's Private Connections feature for VPC peering
   - Reference: https://docs.getorchestra.io/docs/deployment-options/private-connections
3. For DNS issues, verify the hostname in the connection settings is correct
4. For intermittent connectivity, suggest adding retries to the task configuration:
   ```json
   { "configuration": { "retries": 2 } }
   ```

---

## CONFIG_ERROR

**Can Claude fix directly?** Yes, for Orchestra-backed pipelines.

**Playbook:**
1. Identify what's misconfigured from the error message and task parameters
2. Common misconfigurations:
   - **Wrong environment:** Task is running against the wrong database/schema. Fix by
     updating environment variables or running in the correct Orchestra environment.
   - **Missing parameters:** Required task parameters are empty or null. Fill them in.
   - **Invalid parameter format:** e.g. wrong date format, invalid JSON in body.
   - **Wrong connection:** Task is using the wrong integration connection.
3. For Orchestra-backed pipelines, fix via `update_pipeline` with corrected
   task parameters
4. For Git-backed pipelines, show the YAML change needed
5. Validate the fix using `validate_pipeline` before applying
6. Retry after the fix

---

## DEPENDENCY_FAILURE

**Can Claude fix directly?** Partially — can fix the upstream issue if it's within the
same pipeline.

**Playbook:**
1. Identify which upstream task failed (check `depends_on` in the pipeline YAML)
2. If the upstream task is in the same pipeline:
   - Diagnose the upstream failure first (go back to Step 4 for that task)
   - Fix the upstream, then the downstream will run on retry
3. If the upstream is in a different pipeline:
   - Find the upstream pipeline run and diagnose it separately
   - Advise on cross-pipeline dependency management (sensors, trigger events)
4. If the dependency is external data that hasn't arrived:
   - Check if there's a sensor configured. If not, suggest adding one.
   - Advise on using Orchestra's pipeline event triggers to chain pipelines

---

## PLATFORM_ERROR

**Can Claude fix directly?** Yes — retry is usually the right action.

**Playbook:**
1. Confirm the error is platform-side (internal server error, service unavailable,
   platform outage)
2. Check the platform's status page if applicable (status.snowflake.com, status.dbt.com, etc.)
3. If the platform is recovering or has recovered: retry the pipeline
4. If the platform is still down: inform the user and suggest monitoring the status page
5. If this is a recurring platform issue, suggest adding retries to the task:
   ```json
   { "configuration": { "retries": 3 } }
   ```
   Note: Orchestra's YAML schema supports `retries` in the task configuration.

---

## CODE_ERROR

**Can Claude fix directly?** Yes — open a PR with the fix. Do not ask the user to make
the change themselves.

**Playbook:**
1. Extract the full error from logs — identify the file, line, and exception type
2. Determine the exact change needed:
   - **Missing file** (e.g. `pyproject.toml`, `requirements.txt`) — create it with the
     correct content
   - **Python error** — fix the script at the identified line
   - **dbt compilation error** — fix the model file or YAML definition
   - **dbt missing ref/source** — add the missing node or correct the reference
3. Clone the repository and check out the failing branch
4. Apply the fix in a new branch off the failing branch
   (e.g. `fix/missing-pyproject-toml`, `fix/dbt-ref-error`)
5. Commit with a clear message: `fix: <one-line description of what was broken>`
6. Push and open a PR targeting the **failing branch** (not main) via `gh pr create`
7. Share the PR URL
8. After the user merges, offer to retry the pipeline:
   ```json
   { "branch": "<failing-branch>", "commit": "<merged-sha>" }
   ```

**Do not** tell the user "you need to commit X to branch Y." Open the PR for them.

---

## RATE_LIMIT

**Can Claude fix directly?** Yes — retry with backoff.

**Playbook:**
1. Identify which API or service is rate limiting (from error message)
2. Wait an appropriate amount before retrying:
   - API rate limits: usually 1-5 minutes
   - Cloud warehouse concurrency limits: may need longer
3. If rate limits are frequent:
   - Reduce schedule frequency
   - Batch operations where possible
   - Request limit increases from the platform provider
4. Retry the pipeline after the backoff period

---

## DATA_ERROR

**Can Claude fix directly?** Depends on the error type.

**Playbook:**
1. Identify the data quality issue from test results or error messages
2. For dbt test failures:
   - Show which tests failed and the failure counts from `run_results.json`
   - Determine if this is a legitimate data issue or an overly strict test
   - For `not_null` (or similar generic tests) failing on known-bad source NULLs: prefer
     lowering severity to `warn` with `warn_if: ">= {failure_count}"` over deleting the test
   - For threshold-based tests: suggest adjusting `error_threshold_expression` or
     `warn_threshold_expression` if the threshold is too tight
   - For legitimate data issues: advise investigating the source data
3. For Snowflake test tasks (`SNOWFLAKE_RUN_TEST`):
   - Check the test query and threshold expressions
   - Adjust thresholds if needed via pipeline YAML update
4. For schema drift:
   - Identify which columns changed
   - Update the pipeline/model to accommodate the new schema
5. Retry after the data or configuration is corrected

---

## General retry strategy

When retrying a pipeline:
1. Use `start_pipeline` with `alias_or_pipeline_id` (pipeline UUID or alias)
2. Optionally specify:
   - `environment` — to test in a non-production environment first
   - `branch` — overrides the Git branch for the entire run (validation on a fix branch)
   - `run_inputs` — to override input values
3. If the pipeline is paused in Orchestra, `start_pipeline` may return HTTP 400 — ask the user
   to unpause in the UI, then retry
4. Monitor with `get_pipeline_run_status`
4. If the retry succeeds, record the fix in the knowledge store
5. If the retry fails with the same error, revisit the diagnosis
6. If the retry fails with a new error, start a fresh diagnosis

## When to escalate to the user

Always escalate (don't auto-retry) when:
- The pipeline writes data to production (ingestion, materialisation, reverse ETL)
- The error involves data corruption or data loss risk
- The fix requires credential rotation or permission changes
- The pipeline is Git-backed and needs a code change
- You're not confident in the diagnosis (confidence: low)
- The same fix has been tried and failed before
