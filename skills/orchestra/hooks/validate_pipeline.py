#!/usr/bin/env python3
"""Validate an edited Orchestra pipeline definition against the public schema endpoint.

Runs as a PostToolUse hook. Exits 0 and stays silent unless the file is an
Orchestra pipeline that the API rejects, in which case it exits 2 so the
validation errors reach the agent. Every failure mode other than "the API says
this document is invalid" is treated as a pass: a hook that blocks edits when
the network is down is worse than no hook.
"""

import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = os.environ.get(
    "ORCHESTRA_API_URL", "https://app.getorchestra.io/api/engine/public"
) + "/pipelines/schema"
TIMEOUT_SECONDS = 3

# An enum rejection lists every accepted value -- 130+ integration names for a
# single typo. The location and the first line are what the agent needs.
MAX_MESSAGE_CHARS = 200

# The only statuses that mean "Orchestra rejected this document". Anything else
# -- auth, rate limiting, a gateway blip, the Metadata API being disabled -- is
# our problem, not the pipeline's, and must not be reported as invalid YAML.
REJECTION_STATUSES = frozenset((400, 422))

# PipelineModel's own required properties. The schema sets additionalProperties
# false, so a document carrying all three is an Orchestra pipeline and nothing
# else -- dbt_project.yml is the near miss and it has no `pipeline` key.
REQUIRED_KEYS = frozenset(("version", "name", "pipeline"))


def is_pipeline(document) -> bool:
    return isinstance(document, dict) and REQUIRED_KEYS <= document.keys()


def validate(document) -> str | None:
    """Return why Orchestra rejected the document, or None to let the edit stand.

    None covers both "accepted" and "could not tell" -- the caller only ever
    blocks on a definite rejection.
    """
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(document).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    api_key = os.environ.get("ORCHESTRA_API_KEY")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):
            return None
    except urllib.error.HTTPError as error:
        if error.code not in REJECTION_STATUSES:
            return None
        return _summarise(error.read().decode(errors="replace"))
    except OSError:
        return None


def _summarise(body: str) -> str | None:
    """Reduce a rejection to one line per field, or None if it says nothing usable.

    `detail` is a list of per-field errors for a schema rejection, but a plain
    string for some framework-level errors, so neither shape can be assumed.
    """
    try:
        detail = json.loads(body)["detail"]
    except (ValueError, KeyError, TypeError):
        return body[:1000] or None

    if isinstance(detail, str):
        return detail[:1000]

    lines = []
    for item in detail[:20] if isinstance(detail, list) else ():
        if not isinstance(item, dict):
            continue
        where = ".".join(str(part) for part in item.get("loc", ()))
        message = str(item.get("msg", ""))
        if len(message) > MAX_MESSAGE_CHARS:
            message = message[:MAX_MESSAGE_CHARS] + "..."
        lines.append(f"  {where}: {message}")
    return "\n".join(lines) or None


def main() -> int:
    try:
        import yaml
    except ImportError:
        return 0

    try:
        file_path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    except (ValueError, AttributeError):
        return 0

    if not isinstance(file_path, str) or not file_path.endswith((".yml", ".yaml")):
        return 0

    try:
        with open(file_path) as handle:
            document = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return 0

    if not is_pipeline(document):
        return 0

    complaint = validate(document)
    if complaint is None:
        return 0

    print(
        f"{file_path} is not a valid Orchestra pipeline:\n{complaint}\n"
        "Fix the definition before starting a run.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
