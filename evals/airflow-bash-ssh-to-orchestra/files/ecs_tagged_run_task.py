from airflow import DAG
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator

with DAG("enrichment") as dag:
    run_enrichment = EcsRunTaskOperator(
        task_id="run_enrichment",
        cluster="data-platform-cluster",
        task_definition="enrichment-task:14",
        launch_type="FARGATE",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": ["subnet-0a1b2c3d"],
                "securityGroups": ["sg-0f1e2d3c"],
                "assignPublicIp": "DISABLED",
            }
        },
        # Finance splits the AWS bill on these.
        tags={"team": "data", "cost-centre": "1234"},
    )
