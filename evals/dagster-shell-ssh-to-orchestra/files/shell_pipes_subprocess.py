from dagster import asset, Definitions
from dagster_pipes import PipesSubprocessClient


@asset
def transform_orders(context, pipes_subprocess_client: PipesSubprocessClient):
    return pipes_subprocess_client.run(
        command=["python", "scripts/transform_orders.py", "--date", "{{ ds }}"],
        context=context.op_execution_context,
    ).get_results()


defs = Definitions(
    assets=[transform_orders],
    resources={"pipes_subprocess_client": PipesSubprocessClient()},
)
