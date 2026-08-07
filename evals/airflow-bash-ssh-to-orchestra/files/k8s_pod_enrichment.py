from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

with DAG("enrichment_pipeline", schedule_interval="@daily", catchup=False) as dag:
    run_k8s_enrichment = KubernetesPodOperator(
        task_id="run_k8s_enrichment",
        name="enrichment-job",
        image="123456789012.dkr.ecr.us-east-1.amazonaws.com/enrichment:latest",
        namespace="data-team",
        env_vars={"ENV": "prod"},
        cluster_context="arn:aws:eks:us-east-1:123456789012:cluster/data-platform",
    )
