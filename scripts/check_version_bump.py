"""Fail if a manifest's `version` field didn't move forward against a base ref.

Used by CI (validate-skills.yml, tessl-skill-checks.yml) to catch a forgotten
plugin/Tessl manifest version bump at PR time, instead of it surfacing later
as a `tessl plugin publish` "already exists" failure on merge (see AGENTS.md).

Usage:
    python scripts/check_version_bump.py --base <sha> [--scope <path>] <manifest> [<manifest> ...]

Without --scope, every manifest must have a higher version than at --base.
With --scope, that's only required if `git diff <base> HEAD -- <scope>` touches
something other than the manifests themselves — e.g. scope a plugin's own
directory so an unrelated plugin's changes don't require this plugin to bump.
"""

import argparse
import json
import subprocess
import sys


def read_version(path, ref=None):
    try:
        raw = (
            subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=True).stdout
            if ref
            else open(path).read()
        )
        return json.loads(raw)["version"]
    except Exception:
        return None


def parse(version):
    return tuple(int(x) for x in version.split("."))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="git ref to compare each manifest's version against")
    parser.add_argument("--scope", help="only require the bump if this path changed outside the manifests")
    parser.add_argument("manifests", nargs="+", help="manifest.json paths to check")
    args = parser.parse_args()

    if args.scope:
        changed = subprocess.run(
            ["git", "diff", "--name-only", args.base, "HEAD", "--", args.scope],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        if not [f for f in changed if f not in args.manifests]:
            return 0
        print(f"── {args.scope} changed:")
        for f in changed:
            print(f"    {f}")

    failed = False
    for manifest in args.manifests:
        base_version = read_version(manifest, args.base)
        head_version = read_version(manifest)
        if head_version is None:
            print(f"::error file={manifest}::couldn't read a 'version' field")
            failed = True
        elif base_version is not None and parse(head_version) <= parse(base_version):
            print(f"::error file={manifest}::version wasn't bumped forward ({base_version} -> {head_version})")
            failed = True
        else:
            print(f"{manifest}: {base_version} -> {head_version} OK")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
