"""Prefect Automation exported from the UI.

Trigger: the `load_orders` task run inside the `nightly-elt` deployment enters Completed.
Action:  run the `revenue-report` deployment.

The automation deliberately watches a single task run rather than the flow run, because
nightly-elt keeps going for another two hours after load_orders finishes.
"""

AUTOMATION = {
    "name": "revenue-report-after-orders-loaded",
    "trigger": {
        "type": "event",
        "expect": ["prefect.task-run.Completed"],
        "match_related": {
            "prefect.resource.role": "task-run",
            "prefect.resource.name": "load_orders",
            "prefect.deployment.name": "nightly-elt",
        },
    },
    "actions": [
        {"type": "run-deployment", "deployment": "revenue-report/prod"},
    ],
}
