#!/usr/bin/env python3
"""Static lint for every evals/<suite>/evals.json — no tokens spent, no `claude` invocation.

Checks, for every suite:
  - evals.json is valid JSON and matches the canonical shape (skill_name, evals[])
  - every case has id/prompt/expected_output/assertions
  - every assertions_ref resolves to a real file under _shared_assertions/
  - every coded `check` (inline or inside a referenced shared-assertions file) is a name
    grade.py's CHECKS dict actually implements
  - the suite's SKILL.md resolves via the same multi-plugin lookup runner.py uses

This is what would have caught this repo's three independently-invented evals.json
schemas (assertions vs. expectations, name vs. id, ...) at PR time instead of leaving
them silently unrunnable.

Usage:
    python3 evals/lint_evals.py [suite ...]   # default: every suite under evals/
Exit code is nonzero if any suite fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS_DIR))
import grade  # noqa: E402
import runner  # noqa: E402

REQUIRED_CASE_KEYS = {"id", "prompt", "expected_output", "assertions"}


def lint_suite(suite_dir: Path) -> list[str]:
    errors = []
    suite = suite_dir.name
    evals_path = suite_dir / "evals.json"

    try:
        data = json.loads(evals_path.read_text())
    except json.JSONDecodeError as e:
        return [f"{suite}: invalid JSON — {e}"]

    if "skill_name" not in data:
        errors.append(f"{suite}: missing top-level 'skill_name'")
    if "evals" not in data or not isinstance(data["evals"], list) or not data["evals"]:
        errors.append(f"{suite}: 'evals' must be a non-empty array")
        return errors

    try:
        runner.resolve_skill_dir(suite, None, None)
    except SystemExit as e:
        errors.append(f"{suite}: {e}")

    seen_ids = set()
    for case in data["evals"]:
        cid = case.get("id", "<missing id>")
        missing = REQUIRED_CASE_KEYS - case.keys()
        if missing:
            errors.append(f"{suite}/{cid}: missing required key(s) {sorted(missing)}")
        if not isinstance(case.get("id"), str):
            errors.append(f"{suite}/{cid}: 'id' must be a string, not {type(case.get('id')).__name__}")
        elif case["id"] in seen_ids:
            errors.append(f"{suite}/{cid}: duplicate eval id within this suite")
        else:
            seen_ids.add(case["id"])

        for ref in case.get("assertions_ref", []):
            ref_path = grade.SHARED_ASSERTIONS_DIR / f"{ref}.json"
            if not ref_path.exists():
                errors.append(f"{suite}/{cid}: assertions_ref '{ref}' has no file at {ref_path}")

        try:
            assertions = grade.resolve_assertions(case)
        except SystemExit as e:
            errors.append(f"{suite}/{cid}: {e}")
            continue

        for a in assertions:
            if "text" not in a:
                errors.append(f"{suite}/{cid}: an assertion is missing 'text'")
            check = a.get("check")
            if check and check not in grade.CHECKS:
                errors.append(f"{suite}/{cid}: unknown check '{check}' "
                              f"(known: {sorted(grade.CHECKS)})")

    return errors


def lint_shared_assertions() -> list[str]:
    errors = []
    for path in sorted(grade.SHARED_ASSERTIONS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"_shared_assertions/{path.name}: invalid JSON — {e}")
            continue
        if "category" not in data or "assertions" not in data:
            errors.append(f"_shared_assertions/{path.name}: must have 'category' and 'assertions'")
            continue
        for a in data["assertions"]:
            if "text" not in a:
                errors.append(f"_shared_assertions/{path.name}: an assertion is missing 'text'")
            check = a.get("check")
            if check and check not in grade.CHECKS:
                errors.append(f"_shared_assertions/{path.name}: unknown check '{check}'")
    return errors


def main():
    requested = sys.argv[1:]
    if requested:
        suite_dirs = [EVALS_DIR / s for s in requested]
    else:
        suite_dirs = sorted(
            p.parent for p in EVALS_DIR.glob("*/evals.json")
        )

    all_errors = lint_shared_assertions()
    for suite_dir in suite_dirs:
        if not (suite_dir / "evals.json").exists():
            all_errors.append(f"{suite_dir.name}: no evals.json found at {suite_dir}")
            continue
        all_errors += lint_suite(suite_dir)

    if all_errors:
        print(f"✗ {len(all_errors)} problem(s):")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)

    print(f"✓ {len(suite_dirs)} suite(s) OK")


if __name__ == "__main__":
    main()
