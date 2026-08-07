---
name: airflow-bash-ssh-to-orchestra
description: "Use this skill when an Airflow DAG contains BashOperator (non-dbt), SSHOperator (non-dbt), WinRMOperator, or KubernetesPodOperator. Triggers: any task using bash_command= that isn't running dbt, any task using ssh_conn_id= that isn't running dbt, any KubernetesPodOperator or DockerOperator. Note: BashOperator or SSHOperator tasks running dbt CLI commands (dbt run/build/test/seed/snapshot) are handled by dbt-core-airflow-to-orchestra instead, even though they SSH into a remote server."
---

# Airflow Bash/SSH Operators → Orchestra

## Overview

Airflow's `BashOperator`, `SSHOperator`, and `WinRMOperator` run shell commands — locally or on remote hosts. Orchestra doesn't have a local shell execution model; instead:

- **Remote shell commands** → `LINUX_SSH` + `LINUX_SSH_EXECUTE_COMMAND` or `WINDOWS_SSH` + `WINDOWS_SSH_COMMAND` — for mapping `ssh_conn_id=`/`winrm_conn_id=` to the right Orchestra connection, see `airflow-connections-to-orchestra`
- **Python scripts via bash** → `PYTHON` + `PYTHON_EXECUTE_SCRIPT` (the better pattern)
- **Containerised workloads** → `AWS_ECS`, `GKE`, `AZURE_CONTAINER_APPS`, or `AKS` depending on cloud
- **Pure local glue** (echo, mkdir, env checks) → fold into adjacent tasks or drop

---

## Decision Tree

```
Is it a dbt command (dbt run/build/test/seed/snapshot)?
  → YES: use dbt-core-airflow-to-orchestra skill instead — DBT_CORE_EXECUTE,
         even if it arrived via SSHOperator against a remote dbt server.
         Do NOT convert it to LINUX_SSH.
  → NO: continue

Does it run a Python script?
  → YES: PYTHON + PYTHON_EXECUTE_SCRIPT

Does it SSH to a remote server to run commands?
  → Linux: LINUX_SSH + LINUX_SSH_EXECUTE_COMMAND
  → Windows: WINDOWS_SSH + WINDOWS_SSH_COMMAND

Is it a Kubernetes pod?
  → AWS: AWS_EKS + AWS_EKS_RUN_JOB
  → GCP: GKE + GKE_RUN_JOB
  → Azure: AZURE_KUBERNETES_SERVICE + AKS_RUN_JOB

Is it a Docker container (ECS/Cloud Run/Container Apps)?
  → AWS: AWS_ECS + AWS_ECS_RUN_TASK
  → GCP: GCP_CLOUD_RUN + GCP_CLOUD_RUN_EXECUTE_JOB
  → Azure: AZURE_CONTAINER_APPS + ACA_RUN_JOB

Is it purely local glue (echo, mkdir, env check)?
  → Assess whether it can be dropped or folded into adjacent task
```

---

## BashOperator (Python script) → PYTHON

The most common pattern: `BashOperator(bash_command="python scripts/my_script.py")` maps directly to `PYTHON_EXECUTE_SCRIPT`.

```python
# Airflow
run_script = BashOperator(
    task_id="run_etl_script",
    bash_command="cd /opt/airflow && python scripts/etl.py --env prod",
)
```

```yaml
# Orchestra
task-001:
  integration: PYTHON
  integration_job: PYTHON_EXECUTE_SCRIPT
  name: run_etl_script
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

## SSHOperator → LINUX_SSH

```python
# Airflow
run_remote = SSHOperator(
    task_id="run_remote_command",
    ssh_conn_id="my_linux_server",
    command="cd /data && ./process.sh --date {{ ds }}",
)
```

```yaml
# Orchestra
task-001:
  integration: LINUX_SSH
  integration_job: LINUX_SSH_EXECUTE_COMMAND
  name: run_remote_command
  connection: my_linux_server_12345
  parameters:
    command: 'cd /data && ./process.sh --date 2024-01-01'
  depends_on: []
  condition: null
  tags: []
```

**LINUX_SSH parameters:**
| Parameter | Required | Notes |
|---|---|---|
| `command` | ✅ | Shell command to execute on the remote server |

The SSH connection stores: host, port, username, private key (or password). The user must have read/write access to `/tmp/` on the target server.

---

## WinRMOperator → WINDOWS_SSH

```python
# Airflow
run_windows = WinRMOperator(
    task_id="run_windows_script",
    winrm_conn_id="my_windows_server",
    ps_path="C:\\Scripts\\process.ps1",
)
```

```yaml
# Orchestra
task-001:
  integration: WINDOWS_SSH
  integration_job: WINDOWS_SSH_COMMAND
  name: run_windows_script
  connection: my_windows_server_12345
  parameters:
    command: 'powershell.exe -File C:\Scripts\process.ps1'
  depends_on: []
  condition: null
  tags: []
```

---

## KubernetesPodOperator → EKS / GKE / AKS

```python
# Airflow
k8s_task = KubernetesPodOperator(
    task_id="run_k8s_job",
    name="my-etl-job",
    image="my-registry/etl:latest",
    namespace="data-team",
    env_vars={"ENV": "prod"},
)
```

```yaml
# AWS EKS
task-001:
  integration: AWS_EKS
  integration_job: AWS_EKS_RUN_JOB
  name: run_k8s_job
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
                env:
                  - name: ENV
                    value: prod
            restartPolicy: Never
  depends_on: []
```

```yaml
# GCP GKE
task-001:
  integration: GKE
  integration_job: GKE_RUN_JOB
  name: run_k8s_job
  connection: gke_prod_12345
  parameters:
    cluster_name: my-cluster
    job_name: my-etl-job
    location: us-central1   # optional override
  depends_on: []
```

---

## BashOperator (ECS / Cloud Run) → AWS_ECS / GCP_CLOUD_RUN

```python
# Airflow — triggering ECS via BashOperator + AWS CLI
BashOperator(
    task_id="run_ecs_task",
    bash_command="aws ecs run-task --cluster my-cluster --task-definition my-task ...",
)
```

```yaml
# Orchestra — native ECS integration
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

### Airflow DAG (before)

```python
from airflow.providers.ssh.operators.ssh import SSHOperator
from airflow.operators.bash import BashOperator

with DAG("data_pipeline") as dag:
    fetch_data = SSHOperator(
        task_id="fetch_data",
        ssh_conn_id="data_server",
        command="cd /data && python fetch.py --date {{ ds }}",
    )
    process = BashOperator(
        task_id="process_data",
        bash_command="python /opt/scripts/process.py",
    )
    fetch_data >> process
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
        name: process_data
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

- **dbt via BashOperator or SSHOperator** — use the `dbt-core-airflow-to-orchestra` skill instead; `DBT_CORE_EXECUTE` is a dedicated integration. This applies even when the Airflow task SSHes into a remote box to run `dbt run`/`dbt build` — the SSH hop is an Airflow deployment detail, not something to preserve in Orchestra.
- **Jinja templating in bash_command** — `{{ ds }}`, `{{ tomorrow_ds }}` etc. are not available in Orchestra. Replace with `${{ inputs.date }}` or hardcoded values.
- **Local-only BashOperator tasks** — tasks that only run `echo`, set env vars, or do local filesystem operations often can be dropped entirely or replaced by PYTHON task logic.
- **KubernetesPodOperator image** — Orchestra K8s integrations use existing jobs/deployments rather than launching arbitrary images. Ensure the job/task definition exists in your cluster before converting.
- **SSH user permissions** — the SSH user in the Orchestra connection must have read/write access to `/tmp/` on the target server (required by Orchestra's execution model).
- **command vs bash_command** — Orchestra uses `parameters.command` (a string), not `bash_command`. The command runs directly without a shell wrapper.

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
