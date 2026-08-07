from dagster import asset_check, AssetCheckResult, AssetCheckSeverity
import great_expectations as ge


@asset_check(asset="customer_events", severity=AssetCheckSeverity.ERROR)
def customer_events_ge_checkpoint():
    """Runs a Great Expectations checkpoint over the customer_events table and
    surfaces its pass/fail result as this asset check's outcome."""
    context = ge.get_context()
    result = context.run_checkpoint(checkpoint_name="customer_events_checkpoint")
    return AssetCheckResult(
        passed=result.success,
        metadata={"validation_result": str(result.list_validation_result_identifiers())},
    )
