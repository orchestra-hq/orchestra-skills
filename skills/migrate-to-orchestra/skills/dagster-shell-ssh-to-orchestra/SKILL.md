---
name: dagster-shell-ssh-to-orchestra
description: "Use this skill when a Dagster project shells out or runs containers (non-dbt): PipesSubprocessClient / open_pipes_session, dagster-shell (execute_shell_command / create_shell_command_op), SSHResource (dagster-ssh) running remote commands, k8s_job_op / PipesK8sClient, PipesECSClient, or PipesDatabricksClient. Triggers: any op running a subprocess/shell command that is not dbt, any SSHResource remote command, any Kubernetes/ECS Pipes execution. Note: dbt is handled by dbt-core-dagster-to-orchestra."
---

# Dagster Shell / SSH / Pipes -> Orchestra

## Overview

Dagster runs external and shell workloads through several mechanisms: **Dagster Pipes** (`PipesSubprocessClient`, `PipesK8sClient`, `PipesECSClient`, `PipesDatabricksClient`, `PipesGlueClient`, `PipesLambdaClient`), **dagster-shell** (`execute_shell_command`), and **`SSHResource`** (`dagster-ssh`). Orchestra has no local shell execution model; map each to a purpose-built integration:

- **Remote shell commands** -> `LINUX_SSH` + `LINUX_SSH_EXECUTE_COMMAND` or `WINDOWS_SSH` + `WINDOWS_SSH_COMMAND`
- **Subprocess running a Python script** -> `PYTHON` + `PYTHON_EXECUTE_SCRIPT` (the better pattern)
- **Containerised workloads** -> `AWS_ECS`, `GKE`, `AZURE_CONTAINER_APPS`, or `AWS_EKS`/`AKS`
- **Managed compute Pipes** -> the matching integration (`PipesGlueClient` -> `AWS_GLUE`, `PipesLambdaClient` -> `AWS_LAMBDA`, `PipesDatabricksClient` -> `DATABRICKS`)
- **Pure local glue** (echo, mkdir, env checks) -> fold into adjacent tasks or drop

---

## Decision Tree

```
Is it dbt?
  -> YES: use dbt-core-dagster-to-orchestra
  -> NO: continue

Does it run a Python script via subprocess/Pipes?
  -> YES: PYTHON + PYTHON_EXECUTE_SCRIPT

Does it SSH to a remote server (SSHResource)?
  -> Linux: LINUX_SSH + LINUX_SSH_EXECUTE_COMMAND
  -> Windows: WINDOWS_SSH + WINDOWS_SSH_COMMAND

Is it a Kubernetes job (PipesK8sClient / k8s_job_op)?
  -> AWS: AWS_EKS + AWS_EKS_RUN_JOB
  -> GCP: GKE + GKE_RUN_JOB
  -> Azure: AZURE_KUBERNETES_SERVICE + AKS_RUN_JOB

Is it a container (PipesECSClient / Cloud Run)?
  -> AWS: AWS_ECS + AWS_ECS_RUN_TASK
  -> GCP: GCP_CLOUD_RUN + GCP_CLOUD_RUN_EXECUTE_JOB

Managed-compute Pipes?
  -> PipesGlueClient -> AWS_GLUE_RUN_JOB
  -> PipesLambdaClient -> AWS_LAMBDA_EXECUTE_ASYNC_FUNCTION
  -> PipesDatabricksClient -> DATABRICKS_RUN_WORKFLOW

Pure local glue (echo, mkdir)?
  -> Assess whether it can be dropped or folded into an adjacent task
```

---

## PipesSubprocessClient (Python script) -> PYTHON

```python
# Dagster
@asset
def process(context, pipes_subprocess_client: PipesSubprocessClient):
    return pipes_subprocess_client.run(
        command=["python", "scripts/etl.py", "--env", "prod"],
        context=context.op_execution_context,
    ).get_results()
```

```yaml
# Orchestra
task-001:
  integration: PYTHON
  integration_job: PYTHON_EXECUTE_SCRIPT
  name: process
  connection: my_python_git_conn_12345
  parameters:
    command: 'python scripts/etl.py --env prod'
    python_version: '3.12'
    package_manager: PIP
  depends_on: []
  condition: null
  tags: []
```

---

## SSHResource -> LINUX_SSH

```python
# Dagster
@op
def run_remote(context, ssh: SSHResource):
    ssh.execute_remote_command("cd /data && ./process.sh --date 2024-01-01")
```

```yaml
# Orchestra
task-001:
  integration: LINUX_SSH
  integration_job: LINUX_SSH_EXECUTE_COMMAND
  name: run_remote
  connection: my_linux_server_12345
  parameters:
    command: 'cd /data && ./process.sh --date 2024-01-01'
  depends_on: []
  condition: null
  tags: []
```

The SSH user must have read/write access to `/tmp/` on the target server.

---

## PipesK8sClient -> EKS / GKE / AKS

```python
# Dagster
@asset
def k8s_job(context, pipes_k8s_client: PipesK8sClient):
    return pipes_k8s_client.run(
        context=context.op_execution_context,
        image="my-registry/etl:latest",
        namespace="data-team",
    ).get_results()
```

```yaml
# AWS EKS
task-001:
  integration: AWS_EKS
  integration_job: AWS_EKS_RUN_JOB
  name: k8s_job
  connection: aws_eks_prod_12345
  parameters:
    job_manifest: |
      apiVersion: batch/v1
      kind: Job
      metadata:
        name: my-etl-job
      spec:
        template:
          spec:
            containers:
              - name: etl
                image: my-registry/etl:latest
            restartPolicy: Never
  depends_on: []
```

---

## PipesECSClient -> AWS_ECS

```yaml
task-001:
  integration: AWS_ECS
  integration_job: AWS_ECS_RUN_TASK
  name: run_ecs_task
  connection: aws_default_12345
  parameters:
    cluster: my-cluster
    task_definition: my-task
    subnet_ids: subnet-abc123,subnet-def456
    security_group_ids: sg-abc123
    assign_public_ip: false
  depends_on: []
```

---

## Before / After Example

### Dagster (before)

```python
from dagster import op, asset, job, Definitions
from dagster_ssh import SSHResource
from dagster_pipes import PipesSubprocessClient

@op
def fetch_data(context, ssh: SSHResource):
    ssh.execute_remote_command("cd /data && python fetch.py --date 2024-01-01")

@asset
def process(context, pipes_subprocess_client: PipesSubprocessClient):
    return pipes_subprocess_client.run(
        command=["python", "/opt/scripts/process.py"], context=context.op_execution_context,
    ).get_results()

@job
def data_pipeline():
    fetch_data()

defs = Definitions(jobs=[data_pipeline], assets=[process],
                   resources={"ssh": SSHResource(remote_host="data_server"),
                              "pipes_subprocess_client": PipesSubprocessClient()})
```

### Orchestra YAML (after)

```yaml
version: v1
name: data-pipeline

pipeline:
  stage-fetch:
    tasks:
      fetch-data:
        integration: LINUX_SSH
        integration_job: LINUX_SSH_EXECUTE_COMMAND
        name: fetch_data
        connection: data_server_12345
        parameters:
          command: 'cd /data && python fetch.py --date 2024-01-01'
        depends_on: []
        condition: null
        tags: []
    depends_on: []

  stage-process:
    tasks:
      process-data:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        name: process
        connection: my_python_git_conn_12345
        parameters:
          command: 'python scripts/process.py'
          python_version: '3.12'
          package_manager: PIP
        depends_on: []
        condition: null
        tags: []
    depends_on: [stage-fetch]
```

---

## Gotchas

- **dbt via shell/Pipes** — use `dbt-core-dagster-to-orchestra`; `DBT_CORE_EXECUTE` is dedicated.
- **`PipesSubprocessClient` (Python) -> PYTHON** — the command list `["python","scripts/x.py"]` becomes `command: 'python scripts/x.py'`.
- **`SSHResource.execute_remote_command` -> LINUX_SSH** — `parameters.command`.
- **command vs list** — Orchestra uses a string `command`, not a list; join the Pipes command list.
- **`PipesK8sClient` / `k8s_job_op` -> EKS/GKE/AKS** — Orchestra uses existing jobs/manifests, not arbitrary image launches.
- **`PipesECSClient` -> AWS_ECS; `PipesDatabricksClient` -> DATABRICKS_RUN_WORKFLOW**.
- **Pipes context/messages** — Orchestra captures logs natively; for downstream values use `set_outputs`.
- **SSH user permissions** — needs read/write to `/tmp/` on the target server.
- **Local-only glue** — often droppable or foldable.

## Adding Alerts

```yaml
alerts:
  - name: on-failure
    statuses: [FAILED]
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
```

## References

- LINUX_SSH: https://docs.getorchestra.io/docs/integrations/linux_ssh
- WINDOWS_SSH: https://docs.getorchestra.io/docs/integrations/windows_ssh
- AWS ECS: https://docs.getorchestra.io/docs/integrations/aws_ecs
- GKE: https://docs.getorchestra.io/docs/integrations/gke
- Dagster Pipes: https://docs.dagster.io/concepts/dagster-pipes
- dagster-ssh: https://docs.dagster.io/integrations/libraries/ssh
