from dagster import asset, Definitions
from dagster_pipes import PipesECSClient

ecs_client = PipesECSClient()


@asset
def run_tagged_enrichment(context, pipes_ecs_client: PipesECSClient):
    return pipes_ecs_client.run(
        context=context.op_execution_context,
        run_task_params={
            "cluster": "data-platform-cluster",
            "taskDefinition": "enrichment-task:14",
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": ["subnet-0a1b2c3d"],
                    "securityGroups": ["sg-0f1e2d3c"],
                    "assignPublicIp": "DISABLED",
                }
            },
            # Finance splits the AWS bill on these.
            "tags": [
                {"key": "team", "value": "data"},
                {"key": "cost-centre", "value": "1234"},
            ],
        },
    ).get_results()


defs = Definitions(
    assets=[run_tagged_enrichment],
    resources={"pipes_ecs_client": ecs_client},
)
